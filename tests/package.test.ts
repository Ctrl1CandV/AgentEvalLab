import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, rm, access } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createHash } from "node:crypto";
import type { JsonObject } from "@earendil-works/pi-ai";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import { createPiRunner } from "../src/harness/pi.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { preflightPlan } from "../src/evaluation/preflight.js";
import { defaultBudget } from "../src/config.js";
import { emptyExecution } from "../src/types.js";
import { workspaceTools } from "../src/harness/tools.js";
import { command } from "../src/command.js";
import type { EvaluationPlan, WorkspaceInput } from "../src/evaluation/types.js";
import { inspectPackage } from "../src/evaluation/manifest.js";
import { runTaskGrader } from "../src/evaluation/grader.js";
import type { TaskPackageManifest } from "../src/evaluation/manifest.js";

function sha256(content: string): string {
  return createHash("sha256").update(content).digest("hex");
}

test("versioned package pins its manifest and projects only hashed public files", async () => {
  const root = await mkdtemp(join(tmpdir(), "manifest-test-"));
  try {
    const pkg = join(root, "package");
    const workspace = join(root, "workspace");
    const instruction = "Public task";
    const publicData = "visible data";
    await mkdir(join(pkg, "public"), { recursive: true });
    await mkdir(join(pkg, "private"));
    await mkdir(workspace);
    await writeFile(join(pkg, "instruction.md"), instruction);
    await writeFile(join(pkg, "public", "data.txt"), publicData);
    await writeFile(join(pkg, "private", "oracle.txt"), "trusted data");

    const manifest = {
      schemaVersion: 1,
      id: "sample-task",
      version: "1.0.0",
      familyId: "sample-family",
      capability: "engineering",
      usage: "development",
      source: { kind: "original-design", references: ["https://example.invalid/task-spec"] },
      license: { taskText: "original", thirdPartyContent: [] },
      entryPoint: { instruction: "instruction.md" },
      files: {
        public: [
          { path: "instruction.md", sha256: sha256(instruction) },
          { path: "public/data.txt", sha256: sha256(publicData) },
        ],
        trusted: [{ path: "private/oracle.txt", sha256: sha256("trusted data") }],
      },
      requirements: [{ id: "REQ-1", critical: true, introducedAt: "initial", checkIds: ["CHECK-1"] }],
      grader: { id: "sample-grader", version: "1.0.0", entryPoint: "private/oracle.txt", executable: "node", args: ["private/oracle.txt", "{request}", "{result}"] },
      environment: {
        runtime: "Node.js", dependencies: "none", network: false,
        runtimeCheck: { executable: process.execPath, args: ["--version"], expectedSubstring: "unavailable-version-marker" },
      },
    };
    const manifestBytes = JSON.stringify(manifest, null, 2);
    await writeFile(join(pkg, "manifest.json"), manifestBytes);

    const { projectPackage } = await import("../src/evaluation/manifest.js");
    const projection = await projectPackage(pkg, workspace, sha256(manifestBytes), true);
    assert.equal(projection.manifest?.id, "sample-task");
    assert.equal(projection.manifestSha256, sha256(manifestBytes));
    assert.equal(await readFile(join(workspace, "public", "data.txt"), "utf8"), publicData);
    await assert.rejects(access(join(workspace, "private")));
    await assert.rejects(access(join(workspace, "manifest.json")));
    await assert.rejects(projectPackage(pkg, workspace, "0".repeat(64), true), /PACKAGE_MANIFEST_HASH_MISMATCH/);
    await assert.rejects(preflightPlan({
      schemaVersion: 3,
      name: "runtime-preflight",
      models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }],
      budget: { ...defaultBudget },
      artifactLimits: { maxFiles: 10, maxFileBytes: 1000, maxTrialBytes: 10_000, graderResultMaxBytes: 1000, toolEvidenceMaxBytes: 10_000 },
      trustedLocalExecution: true,
      cases: [{
        id: "runtime", packagePath: pkg, packageManifestSha256: sha256(manifestBytes),
        input: { prompt: "Run only if runtime exists." }, evaluator: { kind: "task-package" },
      }],
    }), /PACKAGE_RUNTIME_UNSUPPORTED/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("versioned package rejects path traversal and files that differ from their hashes", async () => {
  const root = await mkdtemp(join(tmpdir(), "manifest-integrity-"));
  try {
    const pkg = join(root, "package");
    await mkdir(join(pkg, "public"), { recursive: true });
    await writeFile(join(pkg, "instruction.md"), "Public task");
    await writeFile(join(pkg, "public", "data.txt"), "visible data");
    const manifest = {
      schemaVersion: 1,
      id: "sample-task", version: "1.0.0", familyId: "sample-family",
      capability: "engineering", usage: "development",
      source: { kind: "original-design", references: ["https://example.invalid/task-spec"] },
      license: { taskText: "original", thirdPartyContent: [] },
      entryPoint: { instruction: "instruction.md" },
      files: { public: [
        { path: "instruction.md", sha256: sha256("Public task") },
        { path: "public/data.txt", sha256: sha256("visible data") },
      ], trusted: [{ path: "private/oracle.txt", sha256: sha256("trusted") }] },
      requirements: [{ id: "REQ-1", critical: true, introducedAt: "initial", checkIds: ["CHECK-1"] }],
      grader: { id: "sample-grader", version: "1.0.0", entryPoint: "private/oracle.txt", executable: "node", args: ["private/oracle.txt", "{request}", "{result}"] },
      environment: { runtime: "Node.js", dependencies: "none", network: false },
    };
    const { inspectPackage } = await import("../src/evaluation/manifest.js");
    manifest.files.public[1]!.path = "public/../private/oracle.txt";
    await writeFile(join(pkg, "manifest.json"), JSON.stringify(manifest));
    await assert.rejects(inspectPackage(pkg), /PACKAGE_PATH_DENIED/);

    manifest.files.public[1]!.path = "public/data.txt";
    await writeFile(join(pkg, "manifest.json"), JSON.stringify(manifest));
    await writeFile(join(pkg, "public", "data.txt"), "tampered data");
    await assert.rejects(inspectPackage(pkg), /PACKAGE_FILE_HASH_MISMATCH/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("task grader receives only a frozen submission and must return a verified result file", async () => {
  const root = await mkdtemp(join(tmpdir(), "grader-protocol-test-"));
  try {
    const pkg = join(root, "package");
    await mkdir(join(pkg, "public"), { recursive: true });
    await mkdir(join(pkg, "private"));
    const instruction = "Build the task solution.";
    const publicData = "sample";
    const graderSource = [
      'import { readFile, writeFile, mkdir } from "node:fs/promises";',
      'import { join } from "node:path";',
      'const arg = name => process.argv[process.argv.indexOf(name) + 1];',
      'const request = JSON.parse(await readFile(arg("--request"), "utf8"));',
      'if (request.submission.directory === request.evidenceRoot) process.exit(4);',
      'await mkdir(join(request.evidenceRoot, "checks"), { recursive: true });',
      'await writeFile(join(request.evidenceRoot, "checks", "result.json"), JSON.stringify({ snapshot: request.submission.snapshotId }));',
      'const result = { schemaVersion: 1, requestId: request.requestId, taskId: request.task.id, taskVersion: request.task.version, graderVersion: "1.0.0", gradingStatus: "completed", checks: [{ id: "CHECK-1", requirementId: "REQ-1", status: "pass", evidenceRefs: ["checks/result.json"] }], dimensions: [], unscoredCheckIds: [], reason: null, error: null };',
      'await writeFile(arg("--result"), JSON.stringify(result));',
    ].join("\n");
    await writeFile(join(pkg, "instruction.md"), instruction);
    await writeFile(join(pkg, "public", "data.txt"), publicData);
    await writeFile(join(pkg, "private", "grader.mjs"), graderSource);
    const manifest = {
      schemaVersion: 1,
      id: "grader-task", version: "1.0.0", familyId: "grader-family",
      capability: "engineering", usage: "development",
      source: { kind: "original-design", references: ["https://example.invalid/task-spec"] },
      license: { taskText: "original", thirdPartyContent: [] },
      entryPoint: { instruction: "instruction.md" },
      files: { public: [
        { path: "instruction.md", sha256: sha256(instruction) },
        { path: "public/data.txt", sha256: sha256(publicData) },
      ], trusted: [{ path: "private/grader.mjs", sha256: sha256(graderSource) }] },
      requirements: [{ id: "REQ-1", critical: true, introducedAt: "initial", checkIds: ["CHECK-1"] }],
      grader: { id: "grader", version: "1.0.0", entryPoint: "private/grader.mjs", executable: process.execPath, args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"] },
      environment: { runtime: "Node.js", dependencies: "none", network: false },
    };
    const manifestBytes = JSON.stringify(manifest);
    await writeFile(join(pkg, "manifest.json"), manifestBytes);
    const result = await runEvaluation({
      schemaVersion: 3,
      name: "versioned-task-grader",
      models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }],
      budget: { ...defaultBudget },
      artifactLimits: { maxFiles: 100, maxFileBytes: 100_000, maxTrialBytes: 1_000_000, graderResultMaxBytes: 10_000, toolEvidenceMaxBytes: 100_000 },
      trustedLocalExecution: true,
      cases: [{
        id: "sample",
        packagePath: pkg,
        packageManifestSha256: sha256(manifestBytes),
        input: { prompt: "Complete the sample task." },
        evaluator: { kind: "task-package" },
      }],
    }, { outputRoot: join(root, "results"), runner: async input => {
      assert.match(input.prompt, /Build the task solution/);
      assert.equal(await readFile(join(input.workspacePath, "public", "data.txt"), "utf8"), publicData);
      await assert.rejects(access(join(input.workspacePath, "private")));
      await writeFile(join(input.workspacePath, "solution.py"), "pass\n");
      return { ...emptyExecution() };
    } });
    assert.equal(result.report.summary.passed, 1, JSON.stringify(result.report.records[0]?.evaluation));
    assert.equal(result.report.summary.acceptedDeliveries, 1);
    assert.equal(result.report.byTask[0]!.passRate, 1);
    const record = result.report.records[0]!;
    const trialDirectory = join(result.directory, record.id);
    assert.ok(record.scoreRunId);
    const scoreRunDirectory = join(trialDirectory, "score-runs", record.scoreRunId!);
    const request = JSON.parse(await readFile(join(scoreRunDirectory, "grader", "request.json"), "utf8"));
    assert.equal(request.submission.directory, join(trialDirectory, "artifacts"));
    assert.equal(request.task.manifestSha256, sha256(manifestBytes));
    assert.equal(record.packageManifest?.sha256, sha256(manifestBytes));
    const scoreRun = JSON.parse(await readFile(join(scoreRunDirectory, "score.json"), "utf8"));
    assert.equal(scoreRun.submission.artifactManifestSha256, record.artifactManifest?.sha256);
    assert.equal(scoreRun.evaluation.status, "passed");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("eng-001 runs read, failed public check, repair, and grading through Pi offline", async t => {
  const root = await mkdtemp(join(tmpdir(), "eng001-pi-calibration-"));
  try {
    const packagePath = join(process.cwd(), "task-library", "calibration", "eng-001-import-validator");
    const manifestBytes = await readFile(join(packagePath, "manifest.json"), "utf8");
    const manifest = JSON.parse(manifestBytes) as { environment: { runtimeCheck?: { executable: string; args: string[]; expectedSubstring: string } } };
    const reference = await readFile(join(packagePath, "private", "ref_impl_a.py"), "utf8");
    const expectedPublicOutput = await readFile(join(packagePath, "public", "expected_dry_run_clean.jsonl"), "utf8");
    const python = manifest.environment.runtimeCheck?.executable;
    assert.ok(python);
    const plan: EvaluationPlan = {
      schemaVersion: 3,
      name: "eng-001-offline-pi-calibration",
      models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }],
      budget: { ...defaultBudget },
      artifactLimits: { maxFiles: 20, maxFileBytes: 100_000, maxTrialBytes: 500_000, graderResultMaxBytes: 100_000, toolEvidenceMaxBytes: 100_000 },
      trustedLocalExecution: true,
      cases: [{
        id: "eng001",
        packagePath,
        packageManifestSha256: sha256(manifestBytes),
        input: { prompt: "Implement the requested CSV validator using the available file tool." },
        evaluator: { kind: "task-package", timeoutMs: 180_000 },
      }],
    };
    try {
      await preflightPlan(plan);
    } catch (error) {
      if (error instanceof Error && error.message === "PACKAGE_RUNTIME_UNSUPPORTED") {
        t.skip("Python 3.13 task runtime is unavailable");
        return;
      }
      throw error;
    }

    let modelCalls = 0;
    let observedPublicRead = false;
    let observedFailedPublicCheck = false;
    let observedPassedPublicCheck = false;
    const runner = createPiRunner<WorkspaceInput>({
      apiKey: "offline-test-key",
      createTools: input => workspaceTools(input.workspacePath, { execute: true }),
      stream: (selectedModel, context) => {
        modelCalls++;
        const toolResultText = (name: string): string | undefined => {
          const message = [...context.messages].reverse().find(item => item.role === "toolResult" && item.toolName === name);
          return message?.role === "toolResult" ? message.content.find(block => block.type === "text")?.text : undefined;
        };
        if (modelCalls === 2) {
          observedPublicRead = toolResultText("read_file") === expectedPublicOutput;
        }
        if (modelCalls === 4) {
          const output = toolResultText("execute_command");
          const check = output ? JSON.parse(output) as { status: string; exitCode: number | null; stdout: string } : null;
          observedFailedPublicCheck = Boolean(check && check.status === "completed" && check.exitCode === 0 &&
            check.stdout.trimEnd() !== expectedPublicOutput.trimEnd());
        }
        if (modelCalls === 6) {
          const output = toolResultText("execute_command");
          const check = output ? JSON.parse(output) as { status: string; exitCode: number | null; stdout: string } : null;
          observedPassedPublicCheck = Boolean(check && check.status === "completed" && check.exitCode === 0 &&
            check.stdout.trimEnd() === expectedPublicOutput.trimEnd());
        }
        const checksArgs = {
          executable: python,
          args: ["import_validator.py", "--schema", "public/schema.json", "--input", "public/data_clean.csv", "--dry-run"],
        };
        const toolCalls: Array<{ name: string; arguments: JsonObject }> = [
          { name: "read_file", arguments: { path: "public/expected_dry_run_clean.jsonl" } },
          { name: "write_file", arguments: { path: "import_validator.py", content: "print('{}')\n" } },
          { name: "execute_command", arguments: checksArgs },
          { name: "write_file", arguments: { path: "import_validator.py", content: reference } },
          { name: "execute_command", arguments: checksArgs },
        ];
        const nextTool = toolCalls[modelCalls - 1];
        const content = nextTool
          ? [{ type: "toolCall" as const, id: "offline-call-" + modelCalls, name: nextTool.name, arguments: nextTool.arguments }]
          : [{ type: "text" as const, text: "Final submission is ready." }];
        const stopReason = nextTool ? "toolUse" as const : "stop" as const;
        const message = {
          role: "assistant" as const,
          content,
          api: selectedModel.api,
          provider: selectedModel.provider,
          model: selectedModel.id,
          usage: {
            input: 4, output: 4, cacheRead: 0, cacheWrite: 0, totalTokens: 8,
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
          },
          stopReason,
          timestamp: Date.now(),
        };
        const stream = new AssistantMessageEventStream();
        stream.push({ type: "start", partial: { ...message, content: [], stopReason: "pending" } });
        stream.push({ type: "done", reason: stopReason, message });
        return stream;
      },
    });

    const result = await runEvaluation(plan, { outputRoot: join(root, "results"), runner });
    const record = result.report.records[0]!;
    assert.equal(modelCalls, 6, JSON.stringify({ execution: record.execution, evaluation: record.evaluation }));
    assert.equal(observedPublicRead, true);
    assert.equal(observedFailedPublicCheck, true);
    assert.equal(observedPassedPublicCheck, true);
    assert.equal(record.execution.modelCalls, 6, JSON.stringify({ modelCalls, execution: record.execution, evaluation: record.evaluation }));
    assert.equal(record.execution.toolCalls, 5, JSON.stringify({ modelCalls, execution: record.execution, evaluation: record.evaluation }));
    assert.equal(record.execution.toolAttempts, 5);
    assert.equal(record.execution.toolIntercepts, 0);
    assert.equal(record.execution.toolExecutions, 5);
    assert.equal(record.execution.requestUsage.length, 6);
    assert.deepEqual(record.execution.requestUsage.map(request => request.totalTokens), [8, 8, 8, 8, 8, 8]);
    assert.deepEqual(record.execution.requestUsage.map(request => request.usageStatus), ["reported", "reported", "reported", "reported", "reported", "reported"]);
    assert.ok(record.execution.requestUsage.every(request => request.durationMs !== null && request.durationMs >= 0 && request.costUsd === null));
    assert.equal(record.interactionClass, "candidate");
    assert.equal(record.toolProfile, "workspace-basic");
    assert.equal(record.execution.status, "done");
    assert.equal(record.evaluation.status, "passed", JSON.stringify(record.evaluation));
    assert.equal(record.evaluation.checks.length, 22);
    const trialDirectory = join(result.directory, record.id);
    const artifactManifest = JSON.parse(await readFile(join(trialDirectory, "artifact-manifest.json"), "utf8"));
    const candidateArtifact = artifactManifest.files.find((file: { path: string }) => file.path === "import_validator.py");
    assert.equal(candidateArtifact?.sizeBytes, Buffer.byteLength(reference));
    assert.equal(candidateArtifact?.sha256, sha256(reference));
    assert.ok((record.artifactManifest?.totalBytes ?? 0) >= Buffer.byteLength(reference));
    const traceLines = (await readFile(join(trialDirectory, "tool-trace.jsonl"), "utf8")).trim().split("\n").map(line => JSON.parse(line));
    assert.equal(traceLines.filter(event => event.eventType === "tool_attempted").length, 5);
    assert.equal(traceLines.filter(event => event.eventType === "tool_authorized").length, 5);
    assert.equal(traceLines.filter(event => event.eventType === "execution_returned").length, 5);
    assert.ok(traceLines.some(event => {
      if (event.eventType !== "execution_returned") return false;
      const returned = event.result as { content?: Array<{ text?: string }> } | undefined;
      return returned?.content?.some(block => block.text?.includes(expectedPublicOutput.trim().slice(0, 20))) === true;
    }));
    assert.equal(record.toolTrace?.truncated, false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("malformed, empty and N/A grader judgments are rejected while valid unscored remains explicit", async () => {
  const root = await mkdtemp(join(tmpdir(), "grader-fault-test-"));
  try {
    const pkg = join(root, "package");
    const submissionDirectory = join(root, "trial", "artifacts");
    await mkdir(join(pkg, "private"), { recursive: true });
    await mkdir(submissionDirectory, { recursive: true });
    const manifest: TaskPackageManifest = {
      schemaVersion: 1,
      id: "fault-task", version: "1.0.0", familyId: "fault-family",
      capability: "engineering", usage: "development",
      source: { kind: "original-design", references: ["https://example.invalid/task-spec"] },
      license: { taskText: "original", thirdPartyContent: [] },
      entryPoint: { instruction: "instruction.md" },
      files: { public: [{ path: "instruction.md", sha256: "1".repeat(64) }], trusted: [{ path: "private/grader.mjs", sha256: "2".repeat(64) }] },
      requirements: [{ id: "REQ-1", critical: true, introducedAt: "initial", checkIds: ["CHECK-1"] }],
      grader: { id: "fault-grader", version: "1.0.0", entryPoint: "private/grader.mjs", executable: process.execPath, args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"] },
      environment: { runtime: "Node.js", dependencies: "none", network: false },
    };
    const descriptor = { root: pkg, instruction: "Task", manifest, manifestSha256: "a".repeat(64) };
    const submissionManifest = { schemaVersion: 1 as const, files: [], totalBytes: 0, sha256: "b".repeat(64) };
    const malformedSource = [
      'import { readFile, writeFile, mkdir } from "node:fs/promises";',
      'const arg = name => process.argv[process.argv.indexOf(name) + 1];',
      'const request = JSON.parse(await readFile(arg("--request"), "utf8"));',
      'const evidence = request.evidenceRoot + "/evidence.json";',
      'await writeFile(evidence, "{}");',
      'const result = { schemaVersion: 1, requestId: request.requestId, taskId: request.task.id, taskVersion: request.task.version, graderVersion: "1.0.0", gradingStatus: "completed", checks: [{ id: "CHECK-1", requirementId: "REQ-1", status: "pass", evidenceRefs: ["evidence.json"], unexpected: true }], dimensions: [], unscoredCheckIds: [], reason: null, error: null };',
      'await writeFile(arg("--result"), JSON.stringify(result));',
    ].join("\n");
    const graderPath = join(pkg, "private", "grader.mjs");
    let scoreIndex = 0;
    const runVariant = async (source: string, trialId: string) => {
      await writeFile(graderPath, source);
      const variantScoreDirectory = join(root, "trial", "score-runs", `score-${++scoreIndex}`);
      await mkdir(variantScoreDirectory, { recursive: true });
      return runTaskGrader({
        trialId, scoreRunDirectory: variantScoreDirectory, submissionDirectory, submissionManifest,
        packageDescriptor: descriptor, maxOutputBytes: 2_000, resultMaxBytes: 10_000, timeoutMs: 5_000,
      });
    };
    const malformed = await runVariant(malformedSource, "trial-1");
    assert.equal(malformed.status, "error");
    assert.equal(malformed.error, "GRADER_CHECK_INVALID");

    const resultSource = (status: string, checks: string, unscored: string, reason: string) => [
      'import { readFile, writeFile } from "node:fs/promises";',
      'const arg = name => process.argv[process.argv.indexOf(name) + 1];',
      'const request = JSON.parse(await readFile(arg("--request"), "utf8"));',
      `const result = { schemaVersion: 1, requestId: request.requestId, taskId: request.task.id, taskVersion: request.task.version, graderVersion: "1.0.0", gradingStatus: ${JSON.stringify(status)}, checks: ${checks}, dimensions: [], unscoredCheckIds: ${unscored}, reason: ${reason}, error: null };`,
      'await writeFile(arg("--result"), JSON.stringify(result));',
    ].join("\n");
    const empty = await runVariant(resultSource("completed", "[]", "[]", "null"), "trial-empty");
    assert.equal(empty.status, "error");
    assert.equal(empty.error, "GRADER_MISSING_CHECKS_INVALID");

    const na = await runVariant(resultSource("completed", '[{ id: "CHECK-1", requirementId: "REQ-1", status: "na", evidenceRefs: [] }]', "[]", "null"), "trial-na");
    assert.equal(na.status, "error");
    assert.equal(na.error, "GRADER_CHECK_INVALID");

    const unscored = await runVariant(resultSource("unscored", "[]", '["CHECK-1"]', '{ code: "INSUFFICIENT_EVIDENCE", message: "No valid judgment was produced." }'), "trial-unscored");
    assert.equal(unscored.status, "unscored");
    assert.equal(unscored.score, null);
    assert.deepEqual(unscored.checks, [{ id: "CHECK-1", passed: null }]);

    const timedOut = await runVariant("setInterval(() => {}, 1000);\n", "trial-timeout");
    assert.equal(timedOut.status, "error");
    assert.equal(timedOut.error, "GRADER_EXECUTION_FAILED");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("package projects public only, preserves artifacts and leaves human review pending", async () => {
  const root = await mkdtemp(join(tmpdir(), "package-test-"));
  try {
    const pkg = join(root, "package");
    await mkdir(join(pkg, "public"), { recursive: true });
    await mkdir(join(pkg, "private"));
    await writeFile(join(pkg, "instruction.md"), "Public instructions");
    await writeFile(join(pkg, "public", "data.txt"), "data");
    await writeFile(join(pkg, "private", "oracle.txt"), "hidden");
    const plan: EvaluationPlan = { name: "package", trustedLocalExecution: true, budget: { ...defaultBudget }, models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }], cases: [{ id: "human-review", packagePath: pkg, input: { prompt: "Review the requested dimensions." }, evaluator: { kind: "human", dimensions: ["clarity"] } }] };
    const result = await runEvaluation(plan, { outputRoot: join(root, "results"), runner: async input => {
      assert.match(input.prompt, /Public instructions/);
      await assert.rejects(access(join(input.workspacePath, "private")));
      assert.equal(await readFile(join(input.workspacePath, "public", "data.txt"), "utf8"), "data");
      await writeFile(join(input.workspacePath, "answer.txt"), "artifact");
      return { ...emptyExecution(), output: "answer" };
    } });
    assert.equal(result.report.summary.pendingReviews, 1);
    const record = result.report.records[0];
    assert.equal(await readFile(join(result.directory, record.id, "artifacts", "answer.txt"), "utf8"), "artifact");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("trusted execution tools expose stderr and read-only excludes mutations", async () => {
  const root = await mkdtemp(join(tmpdir(), "tools-test-"));
  try {
    assert.ok(!workspaceTools(root, { readOnly: true }).some(tool => tool.name === "write_file"));
    const tool = workspaceTools(root, { execute: true }).find(tool => tool.name === "execute_command")!;
    const result = await tool.execute("id", { executable: process.execPath, args: ["-e", "process.stderr.write('diagnostic')"] });
    assert.match(JSON.stringify(result.content), /diagnostic/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("command timeout returns a bounded result", async () => {
  const result = await command(process.execPath, ["-e", "setInterval(() => {}, 1000)"], process.cwd(), 30);
  assert.equal(result.status, "timeout");
});
