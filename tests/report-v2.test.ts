import test from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { emptyExecution } from "../src/types.js";
import { buildOutcome, type ScoreModel } from "../src/scoring/model.js";
import { buildReportV2, markdownReportV2, type V2FamilyData } from "../src/analysis/report-v2.js";

// A golden file of the suite report v2 (MEASUREMENT §7) on fixed outcomes: a core contract family over six structure
// groups, an open-ended frontier family whose best result passes the strong anchor, and a basic family. Rebuild the
// golden file with UPDATE_GOLDEN=1 after a deliberate change, and read the diff.
const GOLDEN = "tests/fixtures/report-v2.golden.md";
const models = [{ label: "m:a-high", thinking: "high", temperature: 0 }, { label: "m:b-default", thinking: "provider-default", temperature: 0 }];
const contract: ScoreModel = { primary: { kind: "resolved" }, groups: [{ id: "tests", weight: 1, critical: true, rule: "fraction", checkIds: ["t1", "t2"] }],
  format: { checkId: "answer-format", penalty: 0.2 } };
const openEnded: ScoreModel = { primary: { kind: "metric", metric: "score" }, groups: [{ id: "valid", weight: 1, critical: false, rule: "all", checkIds: ["valid"] }],
  metrics: [{ id: "score", unit: "points", direction: "higher", anchors: { version: "1", points: [{ name: "naive", maps: 0 }, { name: "median", maps: 0.5 }, { name: "winner", maps: 1 }] } }] };

function outcome(model: string, taskId: string, item: string, structure: string, scoreModel: ScoreModel, passes: string[], extra: { metric?: number; tokens?: number; stop?: "budget" } = {}) {
  const usage = { requestId: "r", interactionClass: "candidate" as const, status: "completed" as const, usageStatus: "reported" as const, durationMs: 1, inputTokens: (extra.tokens ?? 1000) - 100,
    outputTokens: 100, cacheReadTokens: 0, cacheWriteTokens: 0, reasoningTokens: null, totalTokens: extra.tokens ?? 1000, costUsd: null, attempts: 1, failureClass: null };
  const checks = [...new Set([...scoreModel.groups.flatMap(group => group.checkIds), ...(scoreModel.format ? [scoreModel.format.checkId] : [])])].map(id => ({ id, passed: passes.includes(id) }));
  return buildOutcome({ trialId: `${model}-${taskId}-${item}`, model, taskId, taskVersion: "0.1.0", graderVersion: "1.0.0", itemId: item, split: "validation", structure,
    evaluation: { status: "passed", score: null, error: null, checks }, ...(extra.metric !== undefined ? { metrics: [{ id: "score", value: extra.metric }] } : {}),
    execution: { ...emptyExecution(), status: extra.stop ? "budget_exceeded" : "done", failureKind: extra.stop ? "budget" : null, durationMs: 60_000, modelCalls: 12, requestUsage: [usage] },
    scoreModel, ...(extra.metric !== undefined ? { anchors: { score: { naive: 100, median: 500, winner: 900 } } } : {}) });
}

function families(): V2FamilyData[] {
  const protocol = { budget: "2M/task", contextPolicy: "single", tools: "workspace-basic", commandLimits: "default" };
  const core = ["g1", "g2", "g3", "g4", "g5", "g6"].flatMap((group, index) => [
    outcome("m:a-high", "core-task", `${group}a`, group, contract, ["t1", "t2", "answer-format"], { tokens: 2000 }),
    outcome("m:a-high", "core-task", `${group}b`, group, contract, index % 2 ? ["t1", "t2"] : ["t1", "answer-format"], { tokens: 3000 }),
    outcome("m:b-default", "core-task", `${group}a`, group, contract, index % 3 ? ["t1", "answer-format"] : ["t1", "t2", "answer-format"], { tokens: 1500 }),
    outcome("m:b-default", "core-task", `${group}b`, group, contract, ["answer-format"], { tokens: 1000, ...(index === 0 ? { stop: "budget" as const } : {}) }),
  ]);
  const frontier = ["p1", "p2", "p3"].flatMap((problem, index) => [
    outcome("m:a-high", "frontier-task", problem, problem, openEnded, ["valid"], { metric: [950, 700, 300][index]! }),
    outcome("m:b-default", "frontier-task", problem, problem, openEnded, ["valid"], { metric: [400, 100, 50][index]! }),
  ]);
  const basic = ["b1", "b2"].flatMap(item => models.map(model => outcome(model.label, "basic-task", item, `basic:${item}`, contract, ["t1", "t2", "answer-format"])));
  return [
    { id: "CORE", tier: "core", capability: "reasoning", openEnded: false, structureCap: 0.2, packageId: "core-task", taskVersion: "0.1.0", primaryKind: "resolved",
      outcomes: core, plannedTasks: { "m:a-high": 12, "m:b-default": 12 }, notRun: {}, protocol, runDirectories: ["runs/suites/x/runs/CORE/r1"] },
    { id: "FRONT", tier: "frontier", capability: "engineering", openEnded: true, structureCap: 0.2, packageId: "frontier-task", taskVersion: "0.1.0", primaryKind: "metric",
      outcomes: frontier, plannedTasks: { "m:a-high": 3, "m:b-default": 4 }, notRun: { "m:b-default": 1 }, protocol: { ...protocol, budget: "30M/task" }, runDirectories: ["runs/suites/x/runs/FRONT/r1"] },
    { id: "BASE", tier: "basic", capability: "agentic", openEnded: false, structureCap: 0.2, packageId: "basic-task", taskVersion: "0.1.0", primaryKind: "resolved",
      outcomes: basic, plannedTasks: { "m:a-high": 2, "m:b-default": 2 }, notRun: {}, protocol, runDirectories: ["runs/suites/x/runs/BASE/r1"] },
  ];
}

test("report v2: the golden fixture suite", async () => {
  const report = buildReportV2({ suite: "fixture", id: "20261024-000000-fixture-0000", release: "v2.0-fixture", split: "validation", track: "fixed", commit: "0123456789abcdef0123",
    startedAt: "2026-10-24T00:00:00.000Z", finishedAt: "2026-10-24T01:00:00.000Z", status: "completed", models, repetitions: 1, capabilityWeights: { reasoning: { CORE: 1 } },
    families: families(), audits: { CORE: { date: "2026-10-24", summary: { "true pass": 10 } }, FRONT: null, BASE: null } });
  const markdown = markdownReportV2(report);
  if (process.env.UPDATE_GOLDEN) await writeFile(GOLDEN, markdown);
  assert.equal(markdown, await readFile(GOLDEN, "utf8"));
  // The facts the golden file encodes, stated directly.
  const core = report.families.find(family => family.id === "CORE")!;
  assert.equal(core.rows[0]!.primary, 0.75, "model a resolves 9 of 12 tasks, every group weighing the same");
  assert.notEqual(core.rows[0]!.interval, "n too small", "six structure groups give an interval");
  const frontier = report.families.find(family => family.id === "FRONT")!;
  assert.ok(frontier.rows[0]!.primary! > 0.5);
  assert.equal(frontier.saturation.bestAboveStrong, 1, "950 passes the winner's 900");
  assert.equal(frontier.rows[1]!.complete, false, "3 of 4 planned tasks is under 90% coverage");
  assert.equal(report.exploratory, true, "the frontier and basic families have fewer than five groups");
  assert.equal(report.comparisons.length, 1);
  assert.ok(report.comparisons[0]!.meanDifference! > 0);
  assert.deepEqual(Object.keys(report.profile[0]!.rows).sort(), ["BASE", "FRONT"], "basic and frontier rows stay out of the core profile");
});

test("report v2: a core family of a second protocol is its own row, never averaged into its capability", () => {
  const [core, front, base] = families();
  const second = { ...core!, id: "CORE-CODE", ownRow: true };
  const report = buildReportV2({ suite: "fixture", id: "20261024-000000-fixture-0001", release: null, split: "dev", track: "fixed", commit: "0123456789abcdef0123",
    startedAt: "2026-10-24T00:00:00.000Z", finishedAt: "2026-10-24T01:00:00.000Z", status: "completed", models, repetitions: 1, capabilityWeights: {},
    families: [core!, second, front!, base!], audits: { CORE: null, "CORE-CODE": null, FRONT: null, BASE: null } });
  assert.deepEqual(report.profile[0]!.capabilities.reasoning!.families, ["CORE"]);
  assert.ok("CORE-CODE" in report.profile[0]!.rows);
  assert.ok(report.comparisons.every(comparison => comparison.capability === "reasoning"));
});
