import type { EvaluationResult } from "../evaluation/types.js";
import type { ExecutionResult, RequestUsage } from "../types.js";
import { normalise, type AnchorPoint } from "./anchors.js";

/**
 * The task outcome record (MEASUREMENT §2): one per trial, computed from the grader's verdict, its raw metrics and the
 * manifest's score model. A task is the sample; checks, cells and stages are evidence inside it.
 */

export type GroupRule = "all" | "fraction" | "metric";

export interface ScoreGroup {
  id: string;
  weight: number;
  /** Resolved needs every critical group to pass in full. */
  critical: boolean;
  rule: GroupRule;
  /** The checks of the group ("all", "fraction"); a metric group names its metric instead. */
  checkIds: string[];
  metric?: string;
  /** The items a metric group applies to; every item when omitted. */
  items?: string[];
}

export interface ScoreMetric {
  id: string;
  unit: string;
  direction: "higher" | "lower";
  /** Anchor names and the normalised value each maps to; the raw values are per item. */
  anchors?: { version: string; points: Array<{ name: string; maps: number }> };
  /** The items whose grading reports this metric; every item when omitted. */
  items?: string[];
}

export type Primary = { kind: "resolved" } | { kind: "metric"; metric: string } | { kind: "rating" };

export interface ScoreModel {
  primary: Primary;
  /**
   * The headline of particular items where it differs from the package's (PLAN-007 WP2.2): a package such as E4 holds
   * contract items and an open-ended one, reported as separate families.
   */
  primaryByItem?: Record<string, Primary>;
  groups: ScoreGroup[];
  metrics?: ScoreMetric[];
  /** The format check and its deduction, applied to the primary (user decision of 2026-10-25: following the format is
   * part of the ability measured; the deduction is lighter, 10% in v2's packages). */
  format?: { checkId: string; penalty: number };
  /** The most a structure group may weigh in its family (default 0.2). */
  structureCap?: number;
}

export type Stop = "done" | "budget" | "timeout" | "output_limit" | "model_error" | "infrastructure";
export type Coverage = "scored" | "unscored" | "not_run";

export interface OutcomeRecord {
  schemaVersion: 1;
  trialId: string;
  model: string;
  task: { id: string; version: string; graderVersion: string | null; itemId: string | null; split: string | null; structure: string | null };
  repetition: number;
  resolved: boolean | null;
  groups: Record<string, { score: number; weight: number; critical: boolean }>;
  diagnostic: number | null;
  metrics: Array<{ id: string; value: number; unit: string | null; direction: "higher" | "lower" | null }>;
  normalised: Record<string, { value: number; extrapolated: boolean; anchorVersion: string }>;
  primary: number | null;
  /** `penalised` is the primary (after the deduction); `content` the value before it. */
  format: { status: "strict" | "recovered" | "missing" | "n/a"; penalised: number | null; content: number | null };
  stop: Stop;
  usage: {
    inputTokens: number | null; cacheReadTokens: number | null; cacheWriteTokens: number | null; outputTokens: number | null;
    reasoningTokens: number | null; totalTokens: number | null; modelCalls: number; toolCalls: number; wallMs: number;
  };
  coverage: Coverage;
  coverageReason: string | null;
  /** The score run this outcome was computed from; a re-grade appends a new outcome beside a new score run. */
  scoreRunId: string | null;
}

export interface OutcomeInput {
  trialId: string;
  model: string;
  taskId: string;
  taskVersion: string;
  graderVersion: string | null;
  itemId: string | null;
  split?: string | null;
  structure?: string | null;
  repetition?: number;
  evaluation: EvaluationResult;
  /** Raw values the grader reported (grader result v2); none for a v1 grader. */
  metrics?: Array<{ id: string; value: number; unit?: string }>;
  execution: ExecutionResult;
  scoreModel: ScoreModel;
  /** The item's raw anchor values per metric and anchor name. */
  anchors?: Record<string, Record<string, number>>;
  scoreRunId?: string | null;
  /**
   * The checks this task is graded on (its active requirements; a trajectory's final stage). A group counts only these;
   * an expected check the grading does not show counts as failed. Omitted, the evaluation's own checks are expected.
   */
  expectedCheckIds?: string[];
}

/** Sum of one usage field over requests, or null when any request did not report it ("not reported", never 0). */
function sum(requests: RequestUsage[], field: keyof Pick<RequestUsage, "inputTokens" | "cacheReadTokens" | "cacheWriteTokens" | "outputTokens" | "reasoningTokens" | "totalTokens">): number | null {
  if (!requests.length) return 0;
  const values = requests.map(request => request[field]);
  return values.every(value => typeof value === "number") ? (values as number[]).reduce((total, value) => total + value, 0) : null;
}

/** The headline of an item: its own, or the package's. */
export function primaryOf(scoreModel: ScoreModel, itemId: string | null): Primary {
  return (itemId ? scoreModel.primaryByItem?.[itemId] : undefined) ?? scoreModel.primary;
}

/** Whether a group applies to an item: a check group when it holds one of the task's checks, a metric group by its items. */
function applies(group: ScoreGroup, itemId: string | null, expected: Set<string>): boolean {
  if (group.rule === "metric") return !group.items || (itemId !== null && group.items.includes(itemId));
  return group.checkIds.some(id => expected.has(id));
}

/** The metrics an item is normalised on: its headline metric and the metrics of the metric groups applying to it. */
export function metricsOf(scoreModel: ScoreModel, itemId: string | null): Set<string> {
  const headline = primaryOf(scoreModel, itemId);
  return new Set([...(headline.kind === "metric" ? [headline.metric] : []),
    ...scoreModel.groups.filter(group => group.rule === "metric" && applies(group, itemId, new Set())).map(group => group.metric!)]);
}

export function stopOf(execution: ExecutionResult): Stop {
  if (execution.failureKind === "infrastructure") return "infrastructure";
  if (execution.error === "OUTPUT_TOKEN_LIMIT" || execution.error === "OUTPUT_LIMIT") return "output_limit";
  if (execution.status === "timeout" || execution.error === "TIMEOUT" || execution.error === "TRIAL_TIMEOUT") return "timeout";
  if (execution.failureKind === "budget" || execution.status === "budget_exceeded") return "budget";
  if (execution.status === "error" || execution.failureKind === "model") return "model_error";
  return "done";
}

/** A provider's content refusal is reported per model, never scored (PROTOCOL §7). */
function providerRefusal(execution: ExecutionResult): boolean {
  return (execution.requestUsage ?? []).some(request => /content_filter|considered high risk/i.test(request.failureMessage ?? ""));
}

/** The anchor points of one metric for one item, or null when the metric has no anchors. */
export function itemAnchors(metric: ScoreMetric, values: Record<string, number> | undefined): AnchorPoint[] | null {
  if (!metric.anchors) return null;
  if (!values) throw new Error(`ANCHOR_VALUES_MISSING:${metric.id}`);
  return metric.anchors.points.map(point => {
    const value = values[point.name];
    if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`ANCHOR_VALUE_MISSING:${metric.id}.${point.name}`);
    return { name: point.name, maps: point.maps, value };
  });
}

export function buildOutcome(input: OutcomeInput): OutcomeRecord {
  const { evaluation, execution, scoreModel } = input;
  const stop = stopOf(execution);
  const refused = providerRefusal(execution);
  const graded = evaluation.status === "passed" || evaluation.status === "failed";
  const coverage: Coverage = stop === "infrastructure" || refused || !graded ? "unscored" : "scored";
  const coverageReason = coverage === "scored" ? null : refused ? "provider_refusal" : stop === "infrastructure" ? "infrastructure" : `evaluation_${evaluation.status}`;
  const passed = new Map(evaluation.checks.map(check => [check.id, check.passed]));
  const metricDefinitions = new Map((scoreModel.metrics ?? []).map(metric => [metric.id, metric]));
  const metrics = (input.metrics ?? []).map(metric => ({ id: metric.id, value: metric.value, unit: metric.unit ?? metricDefinitions.get(metric.id)?.unit ?? null,
    direction: metricDefinitions.get(metric.id)?.direction ?? null }));
  const normalised: OutcomeRecord["normalised"] = {};
  const used = metricsOf(scoreModel, input.itemId);
  for (const metric of scoreModel.metrics ?? []) {
    const raw = metrics.find(entry => entry.id === metric.id);
    // A metric the item is not scored on is normalised only where the item has anchors for it.
    if (!used.has(metric.id) && !input.anchors?.[metric.id]) continue;
    const points = itemAnchors(metric, input.anchors?.[metric.id]);
    if (raw && points) normalised[metric.id] = { ...normalise(raw.value, points, metric.direction), anchorVersion: metric.anchors!.version };
  }
  const expected = new Set(input.expectedCheckIds ?? evaluation.checks.map(check => check.id));
  const groups: OutcomeRecord["groups"] = {};
  // A group with none of the task's checks does not apply to it (an item of another size, say).
  const applying = scoreModel.groups.filter(group => applies(group, input.itemId, expected));
  for (const group of applying) {
    let score: number;
    if (group.rule === "metric") {
      // The diagnostic weighs a metric group within [0, 1]; the uncapped value is the primary, not the diagnostic.
      score = coverage === "scored" ? Math.min(1, normalised[group.metric!]?.value ?? 0) : 0;
    } else {
      const own = group.checkIds.filter(id => expected.has(id));
      const share = own.filter(id => passed.get(id) === true).length / own.length;
      score = group.rule === "all" ? (share === 1 ? 1 : 0) : share;
    }
    groups[group.id] = { score, weight: group.weight, critical: group.critical };
  }
  const totalWeight = applying.reduce((total, group) => total + group.weight, 0);
  const diagnostic = coverage === "scored" && totalWeight > 0
    ? applying.reduce((total, group) => total + group.weight * groups[group.id]!.score, 0) / totalWeight : null;
  const criticalPass = applying.filter(group => group.critical).every(group => groups[group.id]!.score === 1);
  const resolved = coverage === "scored" ? criticalPass : null;
  let primary: number | null = null;
  const headline = primaryOf(scoreModel, input.itemId);
  if (coverage === "scored") {
    if (headline.kind === "resolved") primary = resolved ? 1 : 0;
    else if (headline.kind === "metric") {
      // An open-ended task's delivery counts only when it is valid (its critical groups pass); otherwise it is at 0.
      primary = criticalPass ? normalised[headline.metric]?.value ?? 0 : 0;
    }
  }
  let format: OutcomeRecord["format"] = { status: "n/a", penalised: primary, content: primary };
  if (scoreModel.format) {
    const verdict = passed.get(scoreModel.format.checkId);
    const anyContent = evaluation.checks.some(check => check.id !== scoreModel.format!.checkId && check.passed === true);
    const status = verdict === true ? "strict" : verdict === false ? (anyContent ? "recovered" : "missing") : "n/a";
    const content = primary;
    // A recovered answer (found, but not in the required format) loses the deduction from the primary itself.
    if (primary !== null && status === "recovered") primary = primary * (1 - scoreModel.format.penalty);
    format = { status, penalised: primary, content };
  }
  const requests = execution.requestUsage ?? [];
  return {
    schemaVersion: 1, trialId: input.trialId, model: input.model,
    task: { id: input.taskId, version: input.taskVersion, graderVersion: input.graderVersion, itemId: input.itemId, split: input.split ?? null, structure: input.structure ?? null },
    repetition: input.repetition ?? 1, resolved, groups, diagnostic, metrics, normalised, primary, format, stop,
    usage: { inputTokens: sum(requests, "inputTokens"), cacheReadTokens: sum(requests, "cacheReadTokens"), cacheWriteTokens: sum(requests, "cacheWriteTokens"),
      outputTokens: sum(requests, "outputTokens"), reasoningTokens: sum(requests, "reasoningTokens"), totalTokens: sum(requests, "totalTokens"),
      modelCalls: execution.modelCalls, toolCalls: execution.toolCalls, wallMs: execution.durationMs },
    coverage, coverageReason, scoreRunId: input.scoreRunId ?? null,
  };
}
