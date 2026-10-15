import test from "node:test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { defaultBudget } from "../src/config.js";
import { emptyExecution } from "../src/types.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { importHumanReview } from "../src/evaluation/regrade.js";
import { evaluationTools } from "../src/harness/profiles.js";
import { createPiRunner } from "../src/harness/pi.js";
import { scriptedToolStream, tool001Answer, tool001Calls } from "./support/tool001.js";
import type { EvaluationPlan, WorkspaceInput } from "../src/evaluation/types.js";

const artifactLimits = {
  maxFiles: 1_000, maxFileBytes: 10_000_000, maxTrialBytes: 50_000_000,
  graderResultMaxBytes: 1_000_000, toolEvidenceMaxBytes: 5_000_000,
};
const model = { provider: "anthropic", id: "claude-sonnet-4-6" };

async function packagePlan(taskId: string, caseId: string, prompt: string, root: string, options: {
  profile?: "workspace-basic" | "workspace-augmented" | "doc-evidence";
  repository?: { path: string; commit: string };
  readOnly?: boolean;
} = {}): Promise<EvaluationPlan> {
  const packagePath = resolve("task-library/calibration", taskId);
  const manifestBytes = await readFile(join(packagePath, "manifest.json"));
  const manifest = JSON.parse(manifestBytes.toString("utf8")) as { baseline?: { commit: string } };
  const item: EvaluationPlan["cases"][number] = {
    id: caseId,
    packagePath,
    packageManifestSha256: (await import("node:crypto")).createHash("sha256").update(manifestBytes).digest("hex"),
    input: { prompt },
    evaluator: { kind: "task-package", timeoutMs: 180_000 },
    ...(options.profile ? { toolProfile: options.profile } : {}),
    ...(options.repository ? { repository: options.repository } : {}),
    ...(options.readOnly !== undefined ? { readOnly: options.readOnly } : {}),
  };
  return {
    schemaVersion: 3,
    name: `${taskId}-offline-grader-test`,
    models: [model],
    budget: { ...defaultBudget },
    artifactLimits,
    trustedLocalExecution: true,
    cases: [item],
  };
}

test("rsn-001 task grader accepts a different valid schedule and conditional answer", async () => {
  const root = await mkdtemp(join(tmpdir(), "m2-rsn001-grader-"));
  try {
    const answer = {
      A: { feasible: false, conflict_set: ["availability", "per_person_max", "coverage"], reasoning: "Capacity is insufficient." },
      B: { gap: "daily_need", branches: { "1": { feasible: true }, "2": { feasible: false } }, reasoning: "Compare required and available person-days." },
      C: { feasible: true, schedule: { "0": ["Carol"], "1": ["Alice"], "2": ["Bob"], "3": ["Carol"], "4": ["Alice"] }, reasoning: "No person exceeds two days." },
    };
    const plan = await packagePlan("rsn-001-shift-scheduling", "rsn001", "Return the structured answer.", root);
    const run = await runEvaluation(plan, { outputRoot: join(root, "runs"), runner: async () => ({ ...emptyExecution(), output: JSON.stringify(answer) }) });
    const record = run.report.records[0]!;
    assert.equal(record.evaluation.status, "passed", JSON.stringify(record.evaluation));
    assert.deepEqual(record.evaluation.checks.map(check => [check.id, check.passed]), [["instance-A", true], ["instance-B", true], ["instance-C", true], ["answer-format", true]]);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("rsn-002 passes on critical certificates and records human review as an append-only score run", async () => {
  const root = await mkdtemp(join(tmpdir(), "m2-rsn002-grader-"));
  try {
    const samples = [
      { id: "s1", theta: 45, mu: 0.2, L: 2, g: 9.8 },
      { id: "s2", theta: 60, mu: 0.5, L: 1.5, g: 9.8 },
      { id: "s3", theta: 30, mu: 0.3, L: 3, g: 9.81 },
    ];
    const correct = (theta: number, mu: number, length: number, gravity: number) => Math.sqrt(2 * gravity * length * (Math.sin(theta * Math.PI / 180) - mu * Math.cos(theta * Math.PI / 180)));
    const student = (theta: number, mu: number, length: number, gravity: number) => Math.sqrt(2 * gravity * length * (Math.sin(theta * Math.PI / 180) - mu));
    const theta = 60, mu = 0.2, length = 2, gravity = 9.8;
    const limitMu = 0.2, limitLength = 2, limitGravity = 9.8;
    const answer = {
      errorStepId: "S1", correctFormula: "v = sqrt(2*g*L*(sin(theta)-mu*cos(theta)))",
      v: Object.fromEntries(samples.map(s => [s.id, correct(s.theta, s.mu, s.L, s.g)])),
      dimensionCertificate: { g: { m: 1, s: -2 }, L: { m: 1, s: 0 }, mu: { m: 0, s: 0 }, v: { m: 1, s: -1 } },
      counterexampleCertificate: { thetaDeg: theta, mu, L: length, g: gravity, correctV: correct(theta, mu, length, gravity), studentV: student(theta, mu, length, gravity) },
      limitCertificate: { mu: limitMu, L: limitLength, g: limitGravity,
        correctLimit: Math.sqrt(2 * limitGravity * limitLength),
        studentLimit: Math.sqrt(2 * limitGravity * limitLength * (1 - limitMu)) },
      explanation: "The normal force sets the friction magnitude.",
    };
    const plan = await packagePlan("rsn-002-derivation-check", "rsn002", "Return the requested numerical certificates.", root);
    const run = await runEvaluation(plan, { outputRoot: join(root, "runs"), runner: async () => ({ ...emptyExecution(), output: JSON.stringify(answer) }) });
    const record = run.report.records[0]!;
    // Critical certificates decide the verdict; the two human-review checks stay pending, not unscored.
    assert.equal(record.evaluation.status, "passed", JSON.stringify(record.evaluation));
    assert.deepEqual(record.evaluation.checks.slice(0, 5).map(check => check.passed), [true, true, true, true, true]);
    assert.deepEqual(record.evaluation.checks[5], { id: "answer-format", passed: true });
    assert.deepEqual(record.evaluation.checks.slice(6), [{ id: "explanation-quality-review", passed: null }, { id: "formula-equivalence-review", passed: null }]);
    assert.equal(record.evaluation.review?.status, "pending");
    assert.deepEqual(record.evaluation.review?.pendingCheckIds, ["explanation-quality-review", "formula-equivalence-review"]);
    assert.equal(run.report.summary.pendingHumanChecks, 1);

    const trialDirectory = join(run.directory, record.id);
    const originalRecord = await readFile(join(trialDirectory, "result.json"), "utf8");
    const reviewPath = join(root, "review.json");
    await writeFile(reviewPath, JSON.stringify({ schemaVersion: 1, reviewer: "test reviewer",
      checks: [{ id: "formula-equivalence-review", status: "pass" }, { id: "explanation-quality-review", status: "fail", note: "Too brief." }] }));
    await writeFile(join(root, "bad-review.json"), JSON.stringify({ schemaVersion: 1, reviewer: "test reviewer", checks: [{ id: "S-localization", status: "pass" }] }));
    await assert.rejects(importHumanReview(trialDirectory, plan, join(root, "bad-review.json"), "review"), /REVIEW_CHECK_NOT_PENDING/);

    const reviewed = await importHumanReview(trialDirectory, plan, reviewPath, "independent review completed");
    assert.equal(reviewed.evaluation.status, "passed", "a failed non-critical review does not change the objective verdict");
    assert.deepEqual(reviewed.evaluation.review, { status: "complete", pendingCheckIds: [], reason: null });
    assert.deepEqual(reviewed.evaluation.checks.slice(6), [{ id: "explanation-quality-review", passed: false }, { id: "formula-equivalence-review", passed: true }]);
    assert.equal(await readFile(join(trialDirectory, "result.json"), "utf8"), originalRecord, "the trial record stays immutable");
    const scoreRun = JSON.parse(await readFile(join(trialDirectory, "score-runs", reviewed.scoreRunId, "score.json"), "utf8")) as { scorer: { kind: string; reviewer: string }; previousScoreRunId: string };
    assert.equal(scoreRun.scorer.kind, "human-review");
    assert.equal(scoreRun.previousScoreRunId, record.scoreRunId);
    const report = JSON.parse(await readFile(join(run.directory, "report.json"), "utf8")) as { records: Array<{ scoreRunId: string }>; summary: { pendingHumanChecks: number } };
    assert.equal(report.records[0]!.scoreRunId, reviewed.scoreRunId);
    assert.equal(report.summary.pendingHumanChecks, 0);
    await assert.rejects(importHumanReview(trialDirectory, plan, reviewPath, "again"), /REVIEW_NOT_PENDING/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("eng-004 runs a pinned candidate clone through the hidden CLI grader", async () => {
  const root = await mkdtemp(join(tmpdir(), "m2-eng004-grader-"));
  try {
    const packageRoot = resolve("task-library/calibration/eng-004-resource-index");
    const baseline = join(packageRoot, "baseline");
    const commit = (await import("../src/command.js")).git(baseline, ["rev-parse", "HEAD"]).then(value => value.trim());
    const plan = await packagePlan("eng-004-resource-index", "eng004", "Implement the task contract.", root, {
      profile: "workspace-augmented", repository: { path: baseline, commit: await commit },
    });
    const result = await runEvaluation(plan, { outputRoot: join(root, "runs"), runner: async (input: WorkspaceInput) => {
      const referenceRoot = join(packageRoot, "private", "reference-variants", "ref-a");
      for (const path of ["src/cli.ts", "src/search.ts", "src/export.ts"]) {
        const target = join(input.workspacePath, path);
        await mkdir(dirname(target), { recursive: true });
        await writeFile(target, await readFile(join(referenceRoot, path)));
      }
      return { ...emptyExecution(), output: "Implemented and checked the CLI." };
    } });
    const record = result.report.records[0]!;
    assert.equal(record.baseline, await commit);
    assert.equal(record.evaluation.status, "passed", JSON.stringify(record.evaluation));
    assert.equal(record.evaluation.checks.length, 7);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("tool-001 runs production tools through evidence trace, task grader and trial report", async () => {
  const root = await mkdtemp(join(tmpdir(), "m2-tool001-grader-"));
  try {
    const packageRoot = resolve("task-library/calibration/tool-001-doc-evidence-recovery");
    const plan = await packagePlan("tool-001-doc-evidence-recovery", "tool001", "Answer all questions using tool evidence.", root,
      { profile: "doc-evidence", readOnly: true });
    // The Pi runner records the trace, so the grader sees the harness's real event shape.
    const calls = await tool001Calls(join(packageRoot, "public", "snapshot"));
    plan.budget = { ...plan.budget, maxTurns: calls.length + 1, maxModelCalls: calls.length + 1, maxToolCalls: calls.length };
    const runner = createPiRunner<WorkspaceInput>({ apiKey: "offline", stream: scriptedToolStream(calls, JSON.stringify(tool001Answer)) as never,
      toolProfile: "doc-evidence", createTools: input => evaluationTools(join(input.workspacePath, "public", "snapshot"), "doc-evidence") });
    const result = await runEvaluation(plan, { outputRoot: join(root, "runs"), runner });
    const record = result.report.records[0]!;
    assert.equal(record.evaluation.status, "passed", JSON.stringify(record.evaluation));
    assert.equal(record.toolProfile, "doc-evidence");
    assert.equal(record.execution.toolExecutions, calls.length);
    assert.equal(record.toolTrace?.truncated, false);
    const trace = (await readFile(join(result.directory, record.id, "tool-trace.jsonl"), "utf8")).trim().split(/\r?\n/).map(line => JSON.parse(line) as { eventType: string });
    assert.equal(trace.filter(event => event.eventType === "execution_returned").length, calls.length);
  } finally { await rm(root, { recursive: true, force: true }); }
});
