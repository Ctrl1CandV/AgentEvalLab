import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { defaultBudget } from "../src/config.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { rebuildReports, regradeTrial, restoreTrialSnapshot } from "../src/evaluation/regrade.js";
import type { TaskPackageManifest } from "../src/evaluation/manifest.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";
import { emptyExecution } from "../src/types.js";

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function graderSource(expected: string, graderVersion = "1.0.0"): string {
  return [
    'import { readFile, writeFile, mkdir } from "node:fs/promises";',
    'import { join } from "node:path";',
    'const arg = name => process.argv[process.argv.indexOf(name) + 1];',
    'const request = JSON.parse(await readFile(arg("--request"), "utf8"));',
    'const answer = await readFile(join(request.submission.directory, "answer.txt"), "utf8");',
    `const passed = answer === ${JSON.stringify(expected)};`,
    'await mkdir(join(request.evidenceRoot, "checks"), { recursive: true });',
    'await writeFile(join(request.evidenceRoot, "checks", "answer.json"), JSON.stringify({ passed }));',
    `const result = { schemaVersion: 1, requestId: request.requestId, taskId: request.task.id, taskVersion: request.task.version, graderVersion: ${JSON.stringify(graderVersion)}, gradingStatus: "completed", checks: [{ id: "CHECK-ANSWER", requirementId: "REQ-IMPLEMENTATION", status: passed ? "pass" : "fail", evidenceRefs: ["checks/answer.json"] }], dimensions: [], unscoredCheckIds: [], reason: null, error: null };`,
    'await writeFile(arg("--result"), JSON.stringify(result));',
  ].join("\n");
}

test("regrade appends a new score run and restores the exact frozen snapshot", async () => {
  const root = await mkdtemp(join(tmpdir(), "regrade-restore-"));
  try {
    const packagePath = join(root, "package");
    await mkdir(join(packagePath, "public"), { recursive: true });
    await mkdir(join(packagePath, "private"));
    await writeFile(join(packagePath, "instruction.md"), "Create answer.txt.");
    await writeFile(join(packagePath, "public", "data.txt"), "public");

    const manifest: TaskPackageManifest = {
      schemaVersion: 1,
      id: "regrade-task", version: "1.0.0", familyId: "regrade-family",
      capability: "engineering", usage: "development",
      source: { kind: "original-design", references: ["https://example.invalid/task"] },
      license: { taskText: "original", thirdPartyContent: [] },
      entryPoint: { instruction: "instruction.md" },
      files: {
        public: [
          { path: "instruction.md", sha256: sha256("Create answer.txt.") },
          { path: "public/data.txt", sha256: sha256("public") },
        ],
        trusted: [{ path: "private/grader.mjs", sha256: sha256(graderSource("old-answer")) }],
      },
      requirements: [{ id: "REQ-IMPLEMENTATION", critical: true, introducedAt: "1.0.0", checkIds: ["CHECK-ANSWER"] }],
      grader: {
        id: "regrade-grader", version: "1.0.0", entryPoint: "private/grader.mjs", executable: process.execPath,
        args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"],
      },
      environment: { runtime: "Node.js", dependencies: "none", network: false },
    };
    await writeFile(join(packagePath, "private", "grader.mjs"), graderSource("old-answer"));
    let manifestBytes = JSON.stringify(manifest);
    await writeFile(join(packagePath, "manifest.json"), manifestBytes);
    const plan: EvaluationPlan = {
      schemaVersion: 3,
      name: "regrade-restore",
      models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }],
      budget: { ...defaultBudget },
      artifactLimits: { maxFiles: 20, maxFileBytes: 100_000, maxTrialBytes: 500_000, graderResultMaxBytes: 20_000, toolEvidenceMaxBytes: 100_000 },
      trustedLocalExecution: true,
      cases: [{
        id: "sample", packagePath, packageManifestSha256: sha256(manifestBytes),
        input: { prompt: "Create the answer." }, evaluator: { kind: "task-package" },
      }],
    };

    let modelRuns = 0;
    const first = await runEvaluation(plan, { outputRoot: join(root, "results"), runner: async input => {
      modelRuns++;
      await writeFile(join(input.workspacePath, "answer.txt"), "expected-answer");
      await mkdir(join(input.workspacePath, "nested", "data"), { recursive: true });
      await writeFile(join(input.workspacePath, "nested", "data", "state.json"), '{"ready":true}\n');
      return emptyExecution();
    } });
    const trial = first.report.records[0]!;
    assert.equal(trial.evaluation.status, "failed");
    const trialDirectory = join(first.directory, trial.id);
    const originalRecord = await readFile(join(trialDirectory, "result.json"), "utf8");
    const initialScoreRunId = trial.scoreRunId!;

    const updatedSource = graderSource("expected-answer", "1.1.0");
    await writeFile(join(packagePath, "private", "grader.mjs"), updatedSource);
    manifest.files.trusted[0]!.sha256 = sha256(updatedSource);
    manifest.grader.version = "1.1.0";
    manifestBytes = JSON.stringify(manifest);
    await writeFile(join(packagePath, "manifest.json"), manifestBytes);
    plan.cases[0]!.packageManifestSha256 = sha256(manifestBytes);

    const regraded = await regradeTrial(trialDirectory, plan, "grader defect corrected");
    assert.equal(regraded.evaluation.status, "passed");
    assert.notEqual(regraded.scoreRunId, initialScoreRunId);
    assert.equal(modelRuns, 1, "regrade must not rerun the model");
    assert.equal(await readFile(join(trialDirectory, "result.json"), "utf8"), originalRecord, "original trial record stays immutable");

    const originalScore = JSON.parse(await readFile(join(trialDirectory, "score-runs", initialScoreRunId, "score.json"), "utf8")) as { evaluation: { status: string } };
    assert.equal(originalScore.evaluation.status, "failed");
    const newScore = JSON.parse(await readFile(join(trialDirectory, "score-runs", regraded.scoreRunId, "score.json"), "utf8")) as { reason: string; scorer: { graderVersion: string } };
    assert.equal(newScore.reason, "grader defect corrected");
    assert.equal(newScore.scorer.graderVersion, "1.1.0");

    const report = JSON.parse(await readFile(join(first.directory, "report.json"), "utf8")) as { records: Array<{ evaluation: { status: string }; scoreRunId: string }> };
    assert.equal(report.records[0]!.evaluation.status, "passed");
    assert.equal(report.records[0]!.scoreRunId, regraded.scoreRunId);
    await rebuildReports(first.directory);

    const restored = await restoreTrialSnapshot(trialDirectory, join(root, "restored", "submission"));
    assert.equal(restored.sha256, trial.artifactManifest?.sha256);
    assert.equal(await readFile(join(restored.destination, "answer.txt"), "utf8"), "expected-answer");
    assert.equal(await readFile(join(restored.destination, "nested", "data", "state.json"), "utf8"), '{"ready":true}\n');
    assert.equal(await readFile(join(restored.destination, "public", "data.txt"), "utf8"), "public");
    await assert.rejects(restoreTrialSnapshot(trialDirectory, restored.destination), /RESTORE_DESTINATION_EXISTS/);

    await writeFile(join(trialDirectory, "artifacts", "answer.txt"), "tampered-after-score");
    await assert.rejects(restoreTrialSnapshot(trialDirectory, join(root, "restored", "tampered")), /RESTORE_SNAPSHOT_HASH_MISMATCH/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
