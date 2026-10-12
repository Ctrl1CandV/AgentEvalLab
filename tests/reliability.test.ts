import test from "node:test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir, rm, symlink, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { validatePlan } from "../src/evaluation/validate.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { summarize } from "../src/evaluation/report.js";
import { defaultBudget } from "../src/config.js";
import { emptyExecution } from "../src/types.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";

const plan: EvaluationPlan = {
  name: "reliability", models: [{ provider: "anthropic", id: "claude-sonnet-4-6" }],
  budget: { ...defaultBudget }, trustedLocalExecution: false,
  cases: [{ id: "case", input: { prompt: "text" }, evaluator: { kind: "human", dimensions: ["clarity"] } }],
};

test("untrusted JSON structures and incorrectly typed flags fail before execution", () => {
  for (const value of [null, [], { ...plan, budget: null }, { ...plan, models: [null] }, { ...plan, cases: [null] }, { ...plan, trustedLocalExecution: "true" }, { ...plan, cases: [{ ...plan.cases[0], readOnly: "false" }] }]) {
    assert.throws(() => validatePlan(value));
  }
  validatePlan(plan);
  assert.throws(() => validatePlan({ ...plan, schemaVersion: 1 }), /UNSUPPORTED_PLAN_VERSION/);
  assert.throws(() => validatePlan({ ...plan, schemaVersion: 2, artifactLimits: { maxFiles: 1, maxFileBytes: 1, maxTrialBytes: 1, graderResultMaxBytes: 1, toolEvidenceMaxBytes: 1 }, trustedLocalExecution: true, cases: [{
    ...plan.cases[0], packagePath: "./task", packageManifestSha256: undefined,
  }] }), /PACKAGE_MANIFEST_PIN_REQUIRED/);
});

test("pending review is not a failed score and experiment completeness is explicit", async () => {
  const root = await mkdtemp(join(tmpdir(), "reliability-"));
  try {
    const result = await runEvaluation(plan, { outputRoot: root, runner: async () => emptyExecution() });
    assert.equal(result.report.completed, true);
    assert.equal(result.report.plannedRuns, 1);
    assert.equal(result.report.recordedRuns, 1);
    assert.equal(result.report.summary.successRate, null);
    assert.equal(result.report.summary.decidedSuccessRate, null);
    assert.equal(summarize([]).reportedTokens, null);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("artifact failure does not overwrite a completed zero-call execution", async () => {
  const root = await mkdtemp(join(tmpdir(), "artifact-failure-"));
  try {
    const result = await runEvaluation(plan, { outputRoot: root, runner: async input => {
      await symlink(root, join(input.workspacePath, "link"), "junction");
      return { ...emptyExecution(), output: "completed" };
    } });
    const record = result.report.records[0];
    assert.equal(record.execution.status, "done");
    assert.equal(record.execution.output, "completed");
    assert.equal(record.evaluation.status, "error");
    assert.equal(record.cleanup, "cleaned");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("artifact size limits preserve completed execution and report resource_limit", async () => {
  const root = await mkdtemp(join(tmpdir(), "artifact-limit-"));
  try {
    const limitedPlan: EvaluationPlan = {
      ...plan,
      artifactLimits: { maxFiles: 10, maxFileBytes: 4, maxTrialBytes: 10, graderResultMaxBytes: 1_000, toolEvidenceMaxBytes: 4_000 },
    };
    const result = await runEvaluation(limitedPlan, { outputRoot: root, runner: async input => {
      await writeFile(join(input.workspacePath, "oversized.txt"), "more than four bytes");
      return { ...emptyExecution(), output: "execution completed" };
    } });
    const record = result.report.records[0]!;
    assert.equal(record.execution.status, "done");
    assert.equal(record.execution.output, "execution completed");
    assert.equal(record.evaluation.status, "resource_limit");
    assert.equal(record.cleanup, "cleaned");
    assert.equal(result.report.summary.resourceLimitRuns, 1);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("event log write failure is explicit and does not rewrite a completed execution as failed", async () => {
  const root = await mkdtemp(join(tmpdir(), "event-log-failure-"));
  try {
    await assert.rejects(runEvaluation(plan, { outputRoot: root, runner: async (_input, _model, _budget, emit) => {
      await emit("test_barrier");
      const runId = (await readdir(root))[0]!;
      const eventPath = join(root, runId, "events.jsonl");
      await unlink(eventPath);
      await mkdir(eventPath);
      return { ...emptyExecution(), output: "execution completed" };
    } }), /EVENT_SINK_FAILED/);
    const runId = (await readdir(root))[0]!;
    const trial = (await readdir(join(root, runId), { withFileTypes: true })).find(entry => entry.isDirectory() && /^[0-9a-f-]{36}$/i.test(entry.name));
    assert.ok(trial);
    const result = JSON.parse(await readFile(join(root, runId, trial.name, "result.json"), "utf8")) as {
      execution: { status: string; output: string };
      evaluation: { status: string; error: string | null };
      cleanup: string;
    };
    assert.equal(result.execution.status, "done");
    assert.equal(result.execution.output, "execution completed");
    assert.equal(result.evaluation.status, "error");
    assert.equal(result.evaluation.error, "ARTIFACT_OR_EVENT_FAILED");
    assert.equal(result.cleanup, "cleaned");
  } finally { await rm(root, { recursive: true, force: true }); }
});
