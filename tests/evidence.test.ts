import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { defaultBudget } from "../src/config.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { regradeTrial } from "../src/evaluation/regrade.js";
import type { TaskPackageManifest } from "../src/evaluation/manifest.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";
import { emptyExecution } from "../src/types.js";
import { collectEvidence, markdownEvidence } from "../src/analysis/evidence.js";

const sha256 = (value: string) => createHash("sha256").update(value).digest("hex");

function graderSource(expected: string, graderVersion: string): string {
  return [
    'import { readFile, writeFile } from "node:fs/promises";',
    'import { join } from "node:path";',
    'const arg = name => process.argv[process.argv.indexOf(name) + 1];',
    'const request = JSON.parse(await readFile(arg("--request"), "utf8"));',
    'const answer = await readFile(join(request.submission.directory, "answer.txt"), "utf8").catch(() => "");',
    `const passed = answer === ${JSON.stringify(expected)};`,
    `await writeFile(arg("--result"), JSON.stringify({ schemaVersion: 1, requestId: request.requestId, taskId: request.task.id, taskVersion: request.task.version, graderVersion: ${JSON.stringify(graderVersion)}, gradingStatus: "completed", checks: [{ id: "CHECK-ANSWER", requirementId: "REQ-A", status: passed ? "pass" : "fail", evidenceRefs: [] }], dimensions: [], unscoredCheckIds: [], reason: null, error: null }));`,
  ].join("\n");
}

test("the evidence table keeps one row per grader version and never scores a dry run", async () => {
  const root = await mkdtemp(join(tmpdir(), "evidence-"));
  try {
    const packagePath = join(root, "task-library", "calibration", "evidence-task");
    await mkdir(join(packagePath, "private"), { recursive: true });
    await writeFile(join(packagePath, "instruction.md"), "Create answer.txt.");
    const manifest: TaskPackageManifest = {
      schemaVersion: 1, id: "t2-finance-desk", version: "0.3.0", familyId: "t2", capability: "tool", usage: "development",
      source: { kind: "original-design", references: [] }, license: { taskText: "original", thirdPartyContent: [] },
      entryPoint: { instruction: "instruction.md" },
      files: { public: [{ path: "instruction.md", sha256: sha256("Create answer.txt.") }], trusted: [{ path: "private/grader.mjs", sha256: sha256(graderSource("right", "1.0.0")) }] },
      requirements: [{ id: "REQ-A", critical: true, introducedAt: "0.1.0", checkIds: ["CHECK-ANSWER"] }],
      grader: { id: "g", version: "1.0.0", entryPoint: "private/grader.mjs", executable: process.execPath, args: ["{entryPoint}", "--request", "{request}", "--result", "{result}"] },
      environment: { runtime: "Node.js", dependencies: "none", network: false },
    };
    await writeFile(join(packagePath, "private", "grader.mjs"), graderSource("right", "1.0.0"));
    let manifestText = JSON.stringify(manifest);
    await writeFile(join(packagePath, "manifest.json"), manifestText);
    const plan: EvaluationPlan = {
      schemaVersion: 3, name: "evidence-fixture", models: [{ provider: "deepseek", id: "deepseek-flash", thinkingLevel: "high", temperature: 0 }],
      budget: { ...defaultBudget, maxTrialTokens: 6_000_000 }, trustedLocalExecution: true,
      artifactLimits: { maxFiles: 20, maxFileBytes: 100_000, maxTrialBytes: 500_000, graderResultMaxBytes: 20_000, toolEvidenceMaxBytes: 100_000 },
      cases: [{ id: "t2-finance-desk", packagePath, packageManifestSha256: sha256(manifestText), input: { prompt: "Answer." }, evaluator: { kind: "task-package" } }],
    };
    // The model writes an answer the first grader wrongly refuses; a later grader accepts it.
    const run = await runEvaluation(plan, { outputRoot: join(root, "runs"), runner: async input => {
      await writeFile(join(input.workspacePath, "answer.txt"), "accepted-later");
      return emptyExecution();
    } });
    const trial = run.report.records[0]!;
    assert.equal(trial.evaluation.status, "failed");
    const fixed = graderSource("accepted-later", "1.1.0");
    await writeFile(join(packagePath, "private", "grader.mjs"), fixed);
    manifest.files.trusted[0]!.sha256 = sha256(fixed);
    manifest.grader.version = "1.1.0";
    manifestText = JSON.stringify(manifest);
    await writeFile(join(packagePath, "manifest.json"), manifestText);
    plan.cases[0]!.packageManifestSha256 = sha256(manifestText);
    await regradeTrial(join(run.directory, trial.id), plan, "grader 1.1.0");

    // A dry-run suite: preflight and smoke only.
    const suiteDirectory = join(root, "runs", "suites", "20261024-000000-dev-abcd");
    await mkdir(suiteDirectory, { recursive: true });
    await writeFile(join(suiteDirectory, "suite.json"), JSON.stringify({
      schemaVersion: 1, id: "20261024-000000-dev-abcd", suitePath: "suites/dev.json",
      suite: { schemaVersion: 1, name: "dev", providerConcurrency: { "*": 1 }, families: [{ id: "T2", kind: "single", template: "x.eval.json" }] },
      models: plan.models, familyIds: ["T2"], dryRun: true, commit: "0".repeat(40), worktree: join(suiteDirectory, "worktree"), createdAt: "2026-10-24T00:00:00.000Z",
      phases: { freeze: "done", launch: "skipped (dry run)" }, plans: [], runs: [], smoke: { T2: { ok: true, detail: "null score 0" } },
    }));

    const evidence = await collectEvidence(root, []);
    const rows = evidence.rows.filter(row => row.family === "T2");
    assert.deepEqual(rows.map(row => [row.graderVersion, row.meanScore, row.resolved]), [["1.0.0", 0, 0], ["1.1.0", 1, 1]]);
    assert.equal(rows[0]!.budget.trial, 6_000_000);
    assert.equal(rows[0]!.label, "deepseek:deepseek-flash-high");
    assert.equal(rows[0]!.status, "completed");
    assert.equal(evidence.suites.length, 1);
    assert.equal(evidence.suites[0]!.status, "dry run");
    assert.ok(evidence.rows.every(row => row.suite === null), "a dry run contributes no rows");
    const markdown = markdownEvidence(evidence);
    assert.match(markdown, /20261024-000000-dev-abcd \(T2\): T2 smoke passed/);
    assert.match(markdown, /\| 1\.1\.0 \|/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
