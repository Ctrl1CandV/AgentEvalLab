import test from "node:test";
import assert from "node:assert/strict";
import { emptyExecution } from "../src/types.js";
import { normalise } from "../src/scoring/anchors.js";
import { buildOutcome, stopOf, type ScoreModel } from "../src/scoring/model.js";
import { capabilityMean, familyMean, saturation, taskScores, taskWeights, type TaskScore } from "../src/scoring/aggregate.js";
import { familyInterval, pairedComparison } from "../src/scoring/bootstrap.js";

const anchors = [{ name: "naive", maps: 0, value: 700 }, { name: "median", maps: 0.5, value: 1300 }, { name: "winner", maps: 1, value: 3300 }];

test("anchors map piecewise-linearly, floor at 0 and extend above the top without a cap", () => {
  assert.deepEqual(normalise(700, anchors, "higher"), { value: 0, extrapolated: false });
  assert.deepEqual(normalise(1000, anchors, "higher"), { value: 0.25, extrapolated: false });
  assert.deepEqual(normalise(2300, anchors, "higher"), { value: 0.75, extrapolated: false });
  assert.deepEqual(normalise(3300, anchors, "higher"), { value: 1, extrapolated: false });
  assert.deepEqual(normalise(4300, anchors, "higher"), { value: 1.25, extrapolated: true }, "the last segment's slope continues, uncapped");
  assert.deepEqual(normalise(100, anchors, "higher"), { value: 0, extrapolated: false }, "floored at 0");
  // Lower is better: bytes or runtime.
  const bytes = [{ name: "naive", maps: 0, value: 1000 }, { name: "strong", maps: 1, value: 600 }];
  assert.deepEqual(normalise(800, bytes, "lower"), { value: 0.5, extrapolated: false });
  assert.deepEqual(normalise(500, bytes, "lower"), { value: 1.25, extrapolated: true });
  assert.throws(() => normalise(800, [{ name: "a", maps: 0, value: 1 }, { name: "b", maps: 1, value: 1 }], "higher"), /ANCHORS_VALUES_NOT_ORDERED/);
  assert.throws(() => normalise(800, [anchors[0]!], "higher"), /ANCHORS_TOO_FEW/);
});

const contract: ScoreModel = {
  primary: { kind: "resolved" },
  groups: [
    { id: "fail-to-pass", weight: 0.7, critical: true, rule: "all", checkIds: ["f1", "f2"] },
    { id: "no-regression", weight: 0.3, critical: true, rule: "fraction", checkIds: ["p1", "p2", "p3", "p4"] },
  ],
  format: { checkId: "answer-format", penalty: 0.2 },
};
const base = { trialId: "t1", model: "m:a-high", taskId: "task", taskVersion: "1.0.0", graderVersion: "1.0.0", itemId: "i1", structure: "repo:x" };

test("outcome records: groups by rule, resolved from critical groups, diagnostic, format kept apart", () => {
  const checks = (pass: string[]) => ["f1", "f2", "p1", "p2", "p3", "p4", "answer-format"].map(id => ({ id, passed: pass.includes(id) }));
  const partial = buildOutcome({ ...base, evaluation: { status: "failed", score: null, error: null, checks: checks(["f1", "p1", "p2", "p3", "answer-format"]) },
    execution: emptyExecution(), scoreModel: contract });
  assert.equal(partial.groups["fail-to-pass"]!.score, 0, "rule all: one failing check fails the group");
  assert.equal(partial.groups["no-regression"]!.score, 0.75, "rule fraction");
  assert.equal(partial.resolved, false);
  assert.equal(partial.primary, 0);
  assert.ok(Math.abs(partial.diagnostic! - 0.225) < 1e-12);
  assert.equal(partial.format.status, "strict");
  const recovered = buildOutcome({ ...base, evaluation: { status: "passed", score: null, error: null, checks: checks(["f1", "f2", "p1", "p2", "p3", "p4"]) },
    execution: emptyExecution(), scoreModel: contract });
  assert.equal(recovered.resolved, true);
  assert.ok(Math.abs(recovered.primary! - 0.8) < 1e-12, "the format deduction applies to the headline");
  assert.equal(recovered.format.status, "recovered");
  assert.equal(recovered.format.content, 1, "the value before the deduction is kept");
  const missing = buildOutcome({ ...base, evaluation: { status: "failed", score: null, error: null, checks: checks([]) }, execution: emptyExecution(), scoreModel: contract });
  assert.equal(missing.format.status, "missing");
  const infra = buildOutcome({ ...base, evaluation: { status: "skipped", score: null, error: null, checks: [] },
    execution: { ...emptyExecution(), status: "error", failureKind: "infrastructure", error: "PROVIDER_UNAVAILABLE" }, scoreModel: contract });
  assert.equal(infra.coverage, "unscored");
  assert.equal(infra.coverageReason, "infrastructure");
  assert.equal(infra.primary, null, "never a zero");
  assert.equal(stopOf({ ...emptyExecution(), status: "budget_exceeded", failureKind: "budget", error: "OUTPUT_TOKEN_LIMIT" }), "output_limit");
  assert.equal(stopOf({ ...emptyExecution(), status: "budget_exceeded", failureKind: "budget", error: "TRIAL_TOKEN_LIMIT" }), "budget");
});

test("an open-ended primary is the uncapped normalised metric; unreported usage is not zero", () => {
  const openEnded: ScoreModel = {
    primary: { kind: "metric", metric: "performance" },
    groups: [{ id: "valid", weight: 1, critical: false, rule: "all", checkIds: ["compiles"] }, { id: "performance", weight: 1, critical: false, rule: "metric", checkIds: [], metric: "performance" }],
    metrics: [{ id: "performance", unit: "AtCoder performance", direction: "higher", anchors: { version: "1", points: [{ name: "naive", maps: 0 }, { name: "median", maps: 0.5 }, { name: "winner", maps: 1 }] } }],
  };
  const execution = { ...emptyExecution(), requestUsage: [{ requestId: "r", interactionClass: "candidate" as const, status: "completed" as const, usageStatus: "partial" as const,
    durationMs: 1, inputTokens: 10, outputTokens: 5, cacheReadTokens: 0, cacheWriteTokens: 0, reasoningTokens: null, totalTokens: 15, costUsd: null, attempts: 1, failureClass: null }] };
  const outcome = buildOutcome({ ...base, evaluation: { status: "passed", score: null, error: null, checks: [{ id: "compiles", passed: true }] },
    metrics: [{ id: "performance", value: 4300 }], execution, scoreModel: openEnded, anchors: { performance: { naive: 700, median: 1300, winner: 3300 } } });
  assert.equal(outcome.primary, 1.25);
  assert.equal(outcome.normalised.performance!.extrapolated, true);
  assert.equal(outcome.groups.performance!.score, 1, "the diagnostic weighs a metric group within [0, 1]");
  assert.equal(outcome.usage.reasoningTokens, null, "a provider that hides reasoning tokens is not reported as 0");
  assert.equal(outcome.usage.totalTokens, 15);
  assert.throws(() => buildOutcome({ ...base, evaluation: { status: "passed", score: null, error: null, checks: [] }, metrics: [{ id: "performance", value: 1 }],
    execution, scoreModel: openEnded }), /ANCHOR_VALUES_MISSING/);
});

const task = (model: string, name: string, structure: string, primary: number | null, resolvedRate = primary): TaskScore =>
  ({ model, taskId: "family", task: name, structure, primary, resolvedRate, trials: 1, scored: primary === null ? 0 : 1 });

test("structure caps: a group above its cap is brought down to it; too few groups weigh equally", () => {
  const tasks = [...Array.from({ length: 5 }, (_, index) => ({ task: `a${index}`, structure: "A" })),
    ...["B", "C", "D", "E", "F"].map(group => ({ task: group.toLowerCase(), structure: group }))];
  const weights = taskWeights(tasks, 0.2);
  assert.ok(Math.abs([...weights.values()].reduce((total, value) => total + value, 0) - 1) < 1e-12);
  assert.ok(Math.abs(weights.get("a0")! * 5 - 0.2) < 1e-12, "group A capped at 20%");
  assert.ok(Math.abs(weights.get("b")! - 0.16) < 1e-12, "the rest shares 80% by tasks");
  const few = taskWeights([{ task: "x1", structure: "X" }, { task: "x2", structure: "X" }, { task: "y", structure: "Y" }], 0.2);
  assert.equal(few.get("y"), 0.5);
  assert.equal(few.get("x1"), 0.25);
  assert.equal(familyMean([task("m", "x1", "X", 1), task("m", "x2", "X", 1), task("m", "y", "Y", 0)]), 0.5);
  assert.ok(Math.abs(capabilityMean({ ER: 0.4, "E4-compress": null }, { ER: 0.8, "E4-compress": 0.2 })! - 0.4) < 1e-12, "a family without a score is left out");
});

test("repetitions average within a task; saturation counts solved by all and by none", () => {
  const outcome = (model: string, item: string, primary: number, repetition = 1) => buildOutcome({ ...base, model, itemId: item, structure: item, repetition,
    evaluation: { status: primary ? "passed" : "failed", score: null, error: null, checks: ["f1", "f2", "p1", "p2", "p3", "p4"].map(id => ({ id, passed: primary === 1 })) },
    execution: emptyExecution(), scoreModel: contract });
  const scores = taskScores([outcome("a", "i1", 1), outcome("a", "i1", 0, 2), outcome("b", "i1", 1), outcome("a", "i2", 1), outcome("b", "i2", 1), outcome("a", "i3", 0), outcome("b", "i3", 0)]);
  assert.equal(scores.find(score => score.model === "a" && score.task === "task@i1")!.primary, 0.5);
  const result = saturation(scores, ["a", "b"], false);
  assert.equal(result.tasks, 3);
  assert.equal(result.solvedByAll, 1);
  assert.equal(result.solvedByNone, 1);
});

test("cluster bootstrap: seeded and repeatable, no interval below five groups, paired by task", () => {
  const groups = ["g1", "g2", "g3", "g4", "g5", "g6"];
  const tasks = groups.flatMap((group, index) => [task("a", `${group}-1`, group, index % 2), task("a", `${group}-2`, group, 1),
    task("b", `${group}-1`, group, 0), task("b", `${group}-2`, group, index % 3 === 0 ? 1 : 0)]);
  const first = familyInterval(tasks.filter(entry => entry.model === "a"), 7);
  assert.deepEqual(familyInterval(tasks.filter(entry => entry.model === "a"), 7), first, "the same seed gives the same interval");
  assert.notEqual(first, "n too small");
  assert.equal(familyInterval(tasks.filter(entry => entry.model === "a" && ["g1", "g2", "g3", "g4"].includes(entry.structure)), 7), "n too small");
  const comparison = pairedComparison(tasks, "a", "b", 11);
  assert.equal(comparison.tasks, 12);
  assert.ok(comparison.meanDifference! > 0);
  assert.ok(comparison.ahead.a > comparison.ahead.b);
  assert.notEqual(comparison.interval, "n too small");
  assert.ok(comparison.tInterval, "the t interval of pairedDifference is the cross-check");
});

test("groups count only the task's own checks; an expected check the grading lacks counts as failed", () => {
  const cells: ScoreModel = { primary: { kind: "resolved" }, groups: [{ id: "cells", weight: 1, critical: true, rule: "fraction", checkIds: ["c1", "c2", "c3", "c4"] }] };
  const small = buildOutcome({ ...base, evaluation: { status: "passed", score: null, error: null, checks: [{ id: "c1", passed: true }, { id: "c2", passed: true }] },
    execution: emptyExecution(), scoreModel: cells, expectedCheckIds: ["c1", "c2"] });
  assert.equal(small.groups.cells!.score, 1, "a smaller item is judged on its own cells");
  assert.equal(small.resolved, true);
  const stopped = buildOutcome({ ...base, evaluation: { status: "passed", score: null, error: null, checks: [{ id: "c1", passed: true }, { id: "c2", passed: true }] },
    execution: emptyExecution(), scoreModel: cells, expectedCheckIds: ["c1", "c2", "c3", "c4"] });
  assert.equal(stopped.groups.cells!.score, 0.5, "a trajectory that never reached the later checks fails them");
  assert.equal(stopped.resolved, false);
});

test("per-item headlines: a contract item is resolved-primary, an open-ended item of the same package metric-primary", () => {
  const mixed: ScoreModel = {
    primary: { kind: "resolved" }, primaryByItem: { compress: { kind: "metric", metric: "ratio" } },
    groups: [{ id: "contract", weight: 1, critical: true, rule: "all", checkIds: ["c1"] }, { id: "valid", weight: 1, critical: true, rule: "all", checkIds: ["v1"] },
      { id: "ratio", weight: 1, critical: false, rule: "metric", checkIds: [], metric: "ratio", items: ["compress"] }],
    metrics: [{ id: "ratio", unit: "bytes per byte", direction: "lower", anchors: { version: "1", points: [{ name: "gzip", maps: 0 }, { name: "xz", maps: 1 }] } }],
  };
  const contract = buildOutcome({ ...base, itemId: "speedup", evaluation: { status: "passed", score: null, error: null, checks: [{ id: "c1", passed: true }] },
    execution: emptyExecution(), scoreModel: mixed, expectedCheckIds: ["c1"] });
  assert.equal(contract.primary, 1);
  assert.deepEqual(Object.keys(contract.groups), ["contract"], "the open-ended item's metric group does not apply to a contract item");
  assert.equal(contract.diagnostic, 1);
  const open = buildOutcome({ ...base, itemId: "compress", evaluation: { status: "passed", score: null, error: null, checks: [{ id: "v1", passed: true }] },
    metrics: [{ id: "ratio", value: 0.3 }], execution: emptyExecution(), scoreModel: mixed, expectedCheckIds: ["v1"], anchors: { ratio: { gzip: 0.4, xz: 0.3 } } });
  assert.ok(Math.abs(open.primary! - 1) < 1e-9);
  assert.deepEqual(Object.keys(open.groups).sort(), ["ratio", "valid"]);
  assert.throws(() => buildOutcome({ ...base, itemId: "compress", evaluation: { status: "passed", score: null, error: null, checks: [{ id: "v1", passed: true }] },
    metrics: [{ id: "ratio", value: 0.3 }], execution: emptyExecution(), scoreModel: mixed, expectedCheckIds: ["v1"] }), /ANCHOR_VALUES_MISSING/);
});
