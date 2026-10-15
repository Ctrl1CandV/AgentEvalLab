import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { defaultBudget } from "../src/config.js";
import { emptyExecution } from "../src/types.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { mergeRunReports } from "../src/evaluation/regrade.js";
import { validatePlan } from "../src/evaluation/validate.js";
import { pairedDifference, passAtK, passHatK, wilsonInterval } from "../src/evaluation/statistics.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";

const near = (actual: number | null | undefined, expected: number, message?: string) => {
  assert.ok(actual !== null && actual !== undefined && Math.abs(actual - expected) < 1e-3, `${message ?? ""} expected ${expected}, got ${actual}`);
};

test("estimators match hand-computed values", () => {
  assert.equal(wilsonInterval(0, 0), null);
  const interval = wilsonInterval(5, 10)!;
  near(interval[0], 0.2366); near(interval[1], 0.7634);
  near(passAtK(5, 2, 2), 0.7);
  near(passHatK(5, 2, 2), 0.1);
  assert.equal(passHatK(1, 1, 2), null, "k larger than the number of trials has no estimate");
  assert.deepEqual(pairedDifference([0.5]), { tasks: 1, mean: 0.5, interval: null });
  const paired = pairedDifference([0.2, 0.4]);
  near(paired.mean, 0.3); near(paired.interval![0], -0.9706); near(paired.interval![1], 1, "clipped to the range of a rate difference");
});

async function reasoningPlan(models: EvaluationPlan["models"], repetitions: number, seed?: number): Promise<EvaluationPlan> {
  const cases = await Promise.all(["rsn-001-shift-scheduling", "rsn-002-derivation-check"].map(async (task, index) => {
    const packagePath = resolve("task-library/calibration", task);
    const bytes = await readFile(join(packagePath, "manifest.json"));
    return { id: `rsn00${index + 1}`, packagePath, packageManifestSha256: createHash("sha256").update(bytes).digest("hex"),
      input: { prompt: "Answer." }, evaluator: { kind: "task-package" as const, timeoutMs: 60_000 } };
  }));
  return { schemaVersion: 3, name: "report-test", models, budget: { ...defaultBudget }, repetitions, ...(seed !== undefined ? { seed } : {}),
    artifactLimits: { maxFiles: 50, maxFileBytes: 1_000_000, maxTrialBytes: 5_000_000, graderResultMaxBytes: 1_000_000, toolEvidenceMaxBytes: 1_000_000 },
    trustedLocalExecution: true, cases };
}

const rsn001 = { A: { feasible: false, conflict_set: ["availability", "per_person_max", "coverage"], reasoning: "x" },
  B: { gap: "daily_need", branches: { "1": { feasible: true }, "2": { feasible: false } }, reasoning: "x" },
  C: { feasible: true, schedule: { "0": ["Carol"], "1": ["Alice"], "2": ["Bob"], "3": ["Carol"], "4": ["Alice"] }, reasoning: "x" } };

test("repetitions are interleaved by seed and reported per task with format failures and paired comparisons", async () => {
  const root = await mkdtemp(join(tmpdir(), "report-test-"));
  try {
    const models = [{ provider: "deepseek", id: "deepseek-flash", thinkingLevel: "high" as const }, { provider: "aliplan", id: "qwen3.8-flash" }];
    const plan = await reasoningPlan(models, 2, 7);
    // deepseek answers rsn-001 correctly once and in a Markdown fence once; qwen always answers plainly.
    let deepseekRsn001 = 0;
    const result = await runEvaluation(plan, { outputRoot: root, runner: async (input, model) => {
      if (!input.prompt.includes("scheduling") && !input.prompt.includes("instances")) return { ...emptyExecution(), output: "{}" };
      const plain = JSON.stringify(rsn001);
      const fenced = model.provider === "deepseek" && ++deepseekRsn001 === 2;
      return { ...emptyExecution(), output: fenced ? "```json\n" + plain + "\n```" : plain };
    } });
    const { report } = result;
    assert.equal(report.plannedRuns, 8);
    assert.equal(report.recordedRuns, 8);
    const experiment = JSON.parse(await readFile(join(result.directory, "experiment.json"), "utf8")) as { seed: number; schedule: string[]; repetitions: number };
    assert.equal(experiment.seed, 7);
    assert.equal(experiment.repetitions, 2);
    for (let block = 0; block < 4; block++) {
      const pair = experiment.schedule.slice(block * 2, block * 2 + 2).map(key => key.split("#")[0]).sort();
      assert.deepEqual(pair, ["aliplan:qwen3.8-flash", "deepseek:deepseek-flash"], "each repetition-and-case block runs every model once");
    }
    const again = await runEvaluation(plan, { outputRoot: root, runner: async () => ({ ...emptyExecution(), output: "{}" }) });
    const repeated = JSON.parse(await readFile(join(again.directory, "experiment.json"), "utf8")) as { schedule: string[] };
    assert.deepEqual(repeated.schedule, experiment.schedule, "the same seed yields the same order");

    const deepseek = report.byTask.find(row => row.caseId === "rsn001" && row.model === "deepseek:deepseek-flash")!;
    assert.equal(deepseek.trials, 2);
    assert.equal(deepseek.label, "deepseek:deepseek-flash-high", "labels append the thinking level");
    assert.equal(deepseek.passes, 1);
    assert.equal(deepseek.malformedAnswers, 1);
    assert.deepEqual(deepseek.executionOutcomes, { done: 2 });
    assert.equal(deepseek.usage.totalTokens.unknown, 2, "trials without reported usage are unknown, not zero");
    assert.match(await readFile(join(result.directory, "report.md"), "utf8"), /## Usage by task/);
    near(deepseek.passHatK, 0, "pass^2 with one of two passes");
    near(deepseek.passAtK, 1, "pass@2 with one of two passes");
    const qwen = report.byTask.find(row => row.caseId === "rsn001" && row.model === "aliplan:qwen3.8-flash")!;
    assert.equal(qwen.passes, 2);
    assert.equal(qwen.capability, "reasoning");
    const comparison = report.pairedComparisons.find(row => row.capability === "reasoning")!;
    assert.equal(comparison.tasks, 2);
    assert.equal("successRate" in report.summary, false);
    const markdown = await readFile(join(result.directory, "report.md"), "utf8");
    assert.match(markdown, /## Results by task/);
    assert.match(markdown, /\| aliplan:qwen3\.8-flash-off \| aliplan:qwen3\.8-flash \| off \| 0 \|/, "the model table lists each condition");
    assert.equal(comparison.labelA, "deepseek:deepseek-flash-high");

    const merged = await mergeRunReports([result.directory, again.directory], root);
    assert.equal(merged.report.recordedRuns, 16);
    assert.equal(merged.report.byTask.find(row => row.caseId === "rsn001" && row.model === "deepseek:deepseek-flash")!.trials, 4);
    const other = await runEvaluation(await reasoningPlan(models, 1), { outputRoot: root, runner: async () => ({ ...emptyExecution(), output: "{}" }) });
    await assert.rejects(mergeRunReports([result.directory, other.directory], root), /MERGE_FINGERPRINT_MISMATCH/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("usage by task reports output, all processed input, cache reads and peak context in fixed tokens", async () => {
  const root = await mkdtemp(join(tmpdir(), "report-tokens-"));
  try {
    const plan = await reasoningPlan([{ provider: "deepseek", id: "deepseek-flash" }], 1);
    const request = { requestId: "r", interactionClass: "candidate" as const, status: "completed" as const, usageStatus: "reported" as const,
      durationMs: 1, inputTokens: 10, outputTokens: 5, cacheReadTokens: 90, cacheWriteTokens: 0, reasoningTokens: null, totalTokens: 105,
      costUsd: null, attempts: 1, failureClass: null };
    const larger = { ...request, inputTokens: 30, cacheReadTokens: 170, totalTokens: 205 };
    const result = await runEvaluation(plan, { outputRoot: root, runner: async () => ({ ...emptyExecution(), output: "{}", modelCalls: 2, requestUsage: [request, larger] }) });
    const row = result.report.byTask[0]!;
    assert.equal(row.usage.totalTokens.median, 310);
    assert.equal(row.usage.outputTokens.median, 10);
    assert.equal(row.usage.inputTokens.median, 300, "input counts cached and uncached context alike");
    assert.equal(row.usage.cacheReadTokens.median, 260);
    assert.equal(row.usage.peakContextTokens.median, 200);
    const markdown = await readFile(join(result.directory, "report.md"), "utf8");
    assert.match(markdown, /\| Output \| Input \| of which cache reads \| Peak context \| Total \|/);
    assert.match(markdown, /## Token use by model/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("repetitions and seeds are validated", async () => {
  const plan = await reasoningPlan([{ provider: "deepseek", id: "deepseek-flash" }], 1);
  validatePlan({ ...plan, repetitions: 50, seed: 0 });
  assert.throws(() => validatePlan({ ...plan, repetitions: 0 }), /INVALID_REPETITIONS/);
  assert.throws(() => validatePlan({ ...plan, repetitions: 51 }), /INVALID_REPETITIONS/);
  assert.throws(() => validatePlan({ ...plan, seed: -1 }), /INVALID_SEED/);
});
