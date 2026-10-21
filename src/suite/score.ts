import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { loadRecordedTrials } from "../evaluation/regrade.js";
import { modelLabel } from "../evaluation/report.js";
import { meanInterval } from "../evaluation/statistics.js";
import type { NotRunEntry } from "../evaluation/batch.js";
import type { TrajectoryRecord, TrialRecord } from "../evaluation/types.js";
import type { ExecutionResult, ModelSelection } from "../types.js";
import { inScore } from "./plans.js";
import type { FamilySpec } from "./spec.js";

/** One scored unit of a family: a trial of a single-run plan, or a whole trajectory. */
export interface FamilyUnit {
  familyId: string;
  model: string;
  label: string;
  runDirectory: string;
  trialId: string;
  itemId: string | null;
  level: string | null;
  /** Null when the unit has no score: an infrastructure failure, an evaluator error or a resource limit. */
  score: number | null;
  status: string;
  resolved: boolean;
  decided: boolean;
  tokens: number | null;
  budgetStop: boolean;
  infrastructure: boolean;
  /** How the execution ended: "done" or its stop code. */
  outcome: string;
  /** The provider's last error text, for infrastructure failures. */
  providerError: string | null;
  failedChecks: string[];
  passedChecks: string[];
}

export interface FamilyModelResult {
  familyId: string;
  model: string;
  label: string;
  units: number;
  scored: number;
  meanScore: number | null;
  interval: [number, number] | null;
  resolved: number;
  decided: number;
  medianTokens: number | null;
  budgetStops: number;
  infrastructureFailures: number;
  unscored: number;
  notRun: number;
  /** Visual families: the tournament win rate, which is the family score there. */
  winRate?: number | null;
}

export interface NotRunUnit extends NotRunEntry { familyId: string; runDirectory: string }

const modelKey = (model: ModelSelection) => `${model.provider}:${model.id}`;

function executionTokens(execution: ExecutionResult): number | null {
  const requests = execution.requestUsage ?? [];
  if (!requests.length) return 0;
  return requests.every(request => request.totalTokens !== null) ? requests.reduce((sum, request) => sum + request.totalTokens!, 0) : null;
}

function providerError(execution: ExecutionResult): string | null {
  const failed = [...(execution.requestUsage ?? [])].reverse().find(request => request.failureMessage);
  return failed?.failureMessage ?? null;
}

function outcome(execution: ExecutionResult): string {
  return execution.status === "done" ? "done" : execution.error ?? execution.status;
}

export function trialUnit(familyId: string, runDirectory: string, record: TrialRecord): FamilyUnit {
  const infrastructure = record.execution.failureKind === "infrastructure";
  const status = record.evaluation.status;
  return {
    familyId, model: modelKey(record.model), label: modelLabel(record.model), runDirectory, trialId: record.id,
    itemId: record.itemId ?? null, level: record.itemLevel ?? null,
    score: infrastructure || typeof record.evaluation.score !== "number" ? null : record.evaluation.score,
    status, resolved: status === "passed", decided: status === "passed" || status === "failed",
    tokens: executionTokens(record.execution), budgetStop: record.execution.failureKind === "budget", infrastructure,
    outcome: outcome(record.execution), providerError: infrastructure ? providerError(record.execution) : null,
    failedChecks: record.evaluation.checks.filter(check => check.passed === false).map(check => check.id),
    passedChecks: record.evaluation.checks.filter(check => check.passed === true).map(check => check.id),
  };
}

/** Every check a trajectory is scored on: the checks of the requirements active in its final stage. */
export async function trajectoryCheckIds(root: string, packagePath: string): Promise<string[]> {
  const manifest = JSON.parse(await readFile(resolve(root, packagePath, "manifest.json"), "utf8")) as {
    requirements: Array<{ id: string; checkIds: string[] }>; stages: Array<{ activeRequirementIds: string[] }>;
  };
  const final = new Set(manifest.stages.at(-1)!.activeRequirementIds);
  return manifest.requirements.filter(requirement => final.has(requirement.id)).flatMap(requirement => requirement.checkIds);
}

/**
 * A trajectory scores the share of its final-stage checks that pass in its last graded snapshot; checks of stages it
 * did not reach count as failed, so the score rewards progress and keeping earlier stages working (E3 README).
 */
export function trajectoryUnit(familyId: string, runDirectory: string, record: TrajectoryRecord, checkIds: string[]): FamilyUnit {
  const grades = record.stages.flatMap(stage => stage.cycles.map(cycle => cycle.privateGrade))
    .filter(grade => grade && (grade.status === "passed" || grade.status === "failed"));
  const last = grades.at(-1);
  const passing = new Set(last?.checks.filter(check => check.passed === true).map(check => check.id) ?? []);
  const execution = record.aggregateExecution;
  const infrastructure = execution.failureKind === "infrastructure";
  // A trajectory stopped by the provider before any snapshot was graded says nothing about the model.
  const score = infrastructure && !last ? null : checkIds.filter(id => passing.has(id)).length / checkIds.length;
  return {
    familyId, model: modelKey(record.model), label: modelLabel(record.model), runDirectory, trialId: record.id, itemId: null,
    level: record.stages.filter(stage => stage.cycles.some(cycle => cycle.privateGrade)).at(-1)?.stageId ?? null,
    score, status: record.status, resolved: score === 1, decided: score !== null,
    tokens: executionTokens(execution), budgetStop: execution.failureKind === "budget" || record.stopReason === "BUDGET_EXHAUSTED",
    infrastructure, outcome: record.stopReason ?? "completed", providerError: infrastructure ? providerError(execution) : null,
    failedChecks: checkIds.filter(id => !passing.has(id)), passedChecks: checkIds.filter(id => passing.has(id)),
  };
}

export interface RunContents { units: FamilyUnit[]; notRun: NotRunUnit[]; providerStops: Record<string, string> }

/** Units and not-run trials of one single-run or visual-page run directory, by default only those in the family score. */
export async function loadSingleRun(family: FamilySpec, runDirectory: string, scoredOnly = true): Promise<RunContents> {
  const records = await loadRecordedTrials(runDirectory);
  const report = JSON.parse(await readFile(join(runDirectory, "report.json"), "utf8").catch(() => "{}")) as {
    batch?: { notRun?: NotRunEntry[]; providerStops?: Record<string, string> };
  };
  return {
    units: records.filter(record => !scoredOnly || inScore(family, record.itemId, record.itemLevel)).map(record => trialUnit(family.id, runDirectory, record)),
    notRun: (report.batch?.notRun ?? []).map(entry => ({ ...entry, familyId: family.id, runDirectory })),
    providerStops: report.batch?.providerStops ?? {},
  };
}

export async function loadTrajectoryRun(family: FamilySpec, runDirectory: string, checkIds: string[]): Promise<RunContents> {
  const report = JSON.parse(await readFile(join(runDirectory, "report.json"), "utf8")) as {
    records: TrajectoryRecord[]; batch?: { notRun?: NotRunEntry[]; providerStops?: Record<string, string> };
  };
  return {
    units: report.records.map(record => trajectoryUnit(family.id, runDirectory, record, checkIds)),
    notRun: (report.batch?.notRun ?? []).map(entry => ({ ...entry, familyId: family.id, runDirectory })),
    providerStops: report.batch?.providerStops ?? {},
  };
}

const median = (values: number[]) => {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle]! : (sorted[middle - 1]! + sorted[middle]!) / 2;
};

/**
 * Per-model family results. Infrastructure failures are excluded, as in the item analyses; units without a score
 * (evaluator errors, resource limits) are counted separately and never treated as zero.
 */
export function familyResults(familyId: string, models: ModelSelection[], units: FamilyUnit[], notRun: NotRunUnit[]): FamilyModelResult[] {
  return models.map(model => {
    const own = units.filter(unit => unit.model === modelKey(model));
    const counted = own.filter(unit => !unit.infrastructure);
    const scores = counted.map(unit => unit.score).filter((score): score is number => score !== null);
    const { mean, interval } = meanInterval(scores);
    return {
      familyId, model: modelKey(model), label: modelLabel(model), units: own.length, scored: scores.length, meanScore: mean, interval,
      resolved: counted.filter(unit => unit.resolved).length, decided: counted.filter(unit => unit.decided).length,
      medianTokens: median(counted.map(unit => unit.tokens).filter((tokens): tokens is number => tokens !== null)),
      budgetStops: counted.filter(unit => unit.budgetStop).length,
      infrastructureFailures: own.filter(unit => unit.infrastructure).length,
      unscored: counted.filter(unit => unit.score === null).length,
      notRun: notRun.filter(entry => entry.model === modelKey(model)).length,
    };
  });
}
