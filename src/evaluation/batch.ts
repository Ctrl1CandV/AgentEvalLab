import { batchStoppingErrors } from "../harness/provider-errors.js";
import type { ExecutionResult } from "../types.js";
import type { EvaluationPlan } from "./types.js";

/** Batch-level limits that keep provider failures and spending contained. */
export interface BatchPolicy {
  /** Provider retries per request for 408/409/429/5xx and connection errors, before any output streams. */
  maxRetries: number;
  /** Longest provider-requested retry delay to honour; longer delays fail the request. */
  maxRetryDelayMs: number;
  /** Stop a provider after this many of its trials (or trajectory cycles) in a row end in an infrastructure failure. */
  maxConsecutiveInfrastructureFailures: number;
  /**
   * Token ceilings in fixed units: every reported token counts once, cached input included; prices never enter.
   * maxTotalTokens bounds the batch; maxTotalTokensPerModel bounds each model separately, so a model that uses
   * many tokens cannot use up another model's share. Null means no ceiling.
   */
  maxTotalTokens: number | null;
  maxTotalTokensPerModel: number | null;
  /** Stop scheduling new work once known cost reaches this amount; null means no ceiling. */
  maxCostUsd: number | null;
  /** Trials run at the same time (single-run plans). Each running trial reserves its token budget against the ceilings. */
  concurrency: number;
}

export const defaultBatchPolicy: Readonly<BatchPolicy> = Object.freeze({
  maxRetries: 2,
  maxRetryDelayMs: 30_000,
  maxConsecutiveInfrastructureFailures: 3,
  maxTotalTokens: null,
  maxTotalTokensPerModel: null,
  maxCostUsd: null,
  concurrency: 1,
});

export function resolveBatchPolicy(plan: EvaluationPlan): BatchPolicy {
  return { ...defaultBatchPolicy, ...(plan.batch ?? {}) };
}

/** Validate an untrusted plan's batch block; every field is optional. */
export function validateBatchPolicy(value: unknown): void {
  if (value === undefined) return;
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("INVALID_BATCH_POLICY");
  const policy = value as Record<string, unknown>;
  for (const key of Object.keys(policy)) if (!(key in defaultBatchPolicy)) throw new Error("INVALID_BATCH_POLICY");
  const integer = (key: string, minimum: number, maximum: number) => {
    const field = policy[key];
    if (field !== undefined && (typeof field !== "number" || !Number.isSafeInteger(field) || field < minimum || field > maximum)) {
      throw new Error(`INVALID_BATCH_POLICY:${key}`);
    }
  };
  integer("maxRetries", 0, 5);
  integer("maxRetryDelayMs", 0, 300_000);
  integer("maxConsecutiveInfrastructureFailures", 1, 1_000);
  integer("concurrency", 1, 16);
  if (policy.maxTotalTokens !== undefined && policy.maxTotalTokens !== null) integer("maxTotalTokens", 1, Number.MAX_SAFE_INTEGER);
  if (policy.maxTotalTokensPerModel !== undefined && policy.maxTotalTokensPerModel !== null) integer("maxTotalTokensPerModel", 1, Number.MAX_SAFE_INTEGER);
  if (policy.maxCostUsd !== undefined && policy.maxCostUsd !== null &&
      (typeof policy.maxCostUsd !== "number" || !Number.isFinite(policy.maxCostUsd) || policy.maxCostUsd <= 0)) {
    throw new Error("INVALID_BATCH_POLICY:maxCostUsd");
  }
}

/** A scheduled trial that did not start, and why (a batch stop reason or MODEL_TOKEN_CEILING). */
export interface NotRunEntry {
  model: string;
  caseId: string;
  repetition: number;
  itemId?: string;
  reason?: string;
}

export interface BatchSummary {
  policy: BatchPolicy;
  /** Why the whole batch stopped, or else why its providers stopped (their distinct reasons, comma-separated). */
  stopReason: string | null;
  /** Providers stopped by an authentication, balance or repeated infrastructure failure, with the reason. */
  providerStops?: Record<string, string>;
  knownTokens: number;
  /** Known tokens per provider:id model. */
  tokensByModel?: Record<string, number>;
  knownCostUsd: number;
  unknownUsageRequests: number;
  notRun: NotRunEntry[];
}

/**
 * Tracks usage and failures across a batch and decides when to stop scheduling work.
 * Known usage only: requests whose usage the provider did not report are counted separately.
 * Failures stop only the provider that had them (an expired key at one provider says nothing about the others);
 * the token and cost ceilings stop the whole batch.
 */
export class BatchGuard {
  knownTokens = 0;
  tokensByModel: Record<string, number> = {};
  /** Token budgets reserved by trials that are running, in total and per model. */
  reservedTokens = 0;
  reservedByModel: Record<string, number> = {};
  knownCostUsd = 0;
  unknownUsageRequests = 0;
  /** Infrastructure failures in a row, per provider ("*" for work recorded without a model). */
  consecutiveInfrastructureFailures: Record<string, number> = {};
  stopReason: string | null = null;
  providerStops: Record<string, string> = {};

  constructor(readonly policy: BatchPolicy) {}

  /**
   * Account one finished trial or trajectory cycle. A trial that a resumed batch reruns still
   * counts toward usage (`countFailure: false`), but its failure no longer counts toward stopping.
   */
  record(execution: ExecutionResult, options: { countFailure?: boolean; model?: string } = {}): void {
    for (const request of execution.requestUsage) {
      if (request.totalTokens === null) this.unknownUsageRequests++;
      else {
        this.knownTokens += request.totalTokens;
        if (options.model) this.tokensByModel[options.model] = (this.tokensByModel[options.model] ?? 0) + request.totalTokens;
      }
      if (request.costUsd !== null) this.knownCostUsd += request.costUsd;
    }
    if (options.countFailure === false) return;
    const provider = providerOf(options.model);
    const failures = execution.failureKind === "infrastructure" ? (this.consecutiveInfrastructureFailures[provider] ?? 0) + 1 : 0;
    this.consecutiveInfrastructureFailures[provider] = failures;
    if (this.stopReason) return;
    if (!this.providerStops[provider]) {
      if (execution.error && batchStoppingErrors.has(execution.error)) this.providerStops[provider] = execution.error;
      else if (failures >= this.policy.maxConsecutiveInfrastructureFailures) this.providerStops[provider] = "INFRASTRUCTURE_FAILURES";
    }
    if (this.policy.maxTotalTokens !== null && this.knownTokens >= this.policy.maxTotalTokens) this.stopReason = "TOKEN_CEILING";
    else if (this.policy.maxCostUsd !== null && this.knownCostUsd >= this.policy.maxCostUsd) this.stopReason = "COST_CEILING";
  }

  /**
   * Why a trial of this model may not start, or null. A ceiling that has been reached blocks; so does one that the
   * next trial could cross, when `reserve` (the plan's per-trial token cap) is given. With a per-trial cap, a ceiling
   * is therefore exceeded by at most the last request of a trial.
   */
  blockedReason(model: string, reserve = 0): string | null {
    if (this.stopReason) return this.stopReason;
    const providerStop = this.providerStops[providerOf(model)] ?? this.providerStops["*"];
    if (providerStop) return providerStop;
    const exceeds = (used: number, ceiling: number | null) => ceiling !== null && (used >= ceiling || used + reserve > ceiling);
    if (exceeds(this.knownTokens + this.reservedTokens, this.policy.maxTotalTokens)) return "TOKEN_CEILING";
    if (exceeds((this.tokensByModel[model] ?? 0) + (this.reservedByModel[model] ?? 0), this.policy.maxTotalTokensPerModel)) return "MODEL_TOKEN_CEILING";
    return null;
  }

  /** Hold a running trial's token budget against the ceilings until it is recorded; returns the release function. */
  reserve(model: string, tokens: number): () => void {
    this.reservedTokens += tokens;
    this.reservedByModel[model] = (this.reservedByModel[model] ?? 0) + tokens;
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.reservedTokens -= tokens;
      this.reservedByModel[model]! -= tokens;
    };
  }

  summary(notRun: NotRunEntry[]): BatchSummary {
    const providerReasons = [...new Set(Object.values(this.providerStops))];
    return {
      policy: this.policy,
      stopReason: this.stopReason ?? (providerReasons.length ? providerReasons.join(", ") : null),
      ...(Object.keys(this.providerStops).length ? { providerStops: { ...this.providerStops } } : {}),
      knownTokens: this.knownTokens,
      tokensByModel: this.tokensByModel,
      knownCostUsd: this.knownCostUsd,
      unknownUsageRequests: this.unknownUsageRequests,
      notRun,
    };
  }
}

/** The provider of a "provider:id" model key; work recorded without a model counts as "*". */
function providerOf(model: string | undefined): string {
  return model ? model.split(":")[0]! : "*";
}
