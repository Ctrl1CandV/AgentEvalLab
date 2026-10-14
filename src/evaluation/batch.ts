import { batchStoppingErrors } from "../harness/provider-errors.js";
import type { ExecutionResult } from "../types.js";
import type { EvaluationPlan } from "./types.js";

/** Batch-level limits that keep provider failures and spending contained. */
export interface BatchPolicy {
  /** Provider retries per request for 408/409/429/5xx and connection errors, before any output streams. */
  maxRetries: number;
  /** Longest provider-requested retry delay to honour; longer delays fail the request. */
  maxRetryDelayMs: number;
  /** Stop after this many trials (or trajectory cycles) in a row end in an infrastructure failure. */
  maxConsecutiveInfrastructureFailures: number;
  /** Stop scheduling new work once known token usage reaches this total; null means no ceiling. */
  maxTotalTokens: number | null;
  /** Stop scheduling new work once known cost reaches this amount; null means no ceiling. */
  maxCostUsd: number | null;
}

export const defaultBatchPolicy: Readonly<BatchPolicy> = Object.freeze({
  maxRetries: 2,
  maxRetryDelayMs: 30_000,
  maxConsecutiveInfrastructureFailures: 3,
  maxTotalTokens: null,
  maxCostUsd: null,
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
  if (policy.maxTotalTokens !== undefined && policy.maxTotalTokens !== null) integer("maxTotalTokens", 1, Number.MAX_SAFE_INTEGER);
  if (policy.maxCostUsd !== undefined && policy.maxCostUsd !== null &&
      (typeof policy.maxCostUsd !== "number" || !Number.isFinite(policy.maxCostUsd) || policy.maxCostUsd <= 0)) {
    throw new Error("INVALID_BATCH_POLICY:maxCostUsd");
  }
}

/**
 * Tracks usage and failures across a batch and decides when to stop scheduling work.
 * Known usage only: requests whose usage the provider did not report are counted separately.
 */
export class BatchGuard {
  knownTokens = 0;
  knownCostUsd = 0;
  unknownUsageRequests = 0;
  consecutiveInfrastructureFailures = 0;
  stopReason: string | null = null;

  constructor(readonly policy: BatchPolicy) {}

  get stopped(): boolean {
    return this.stopReason !== null;
  }

  /**
   * Account one finished trial or trajectory cycle. A trial that a resumed batch reruns still
   * counts toward usage (`countFailure: false`), but its failure no longer counts toward stopping.
   */
  record(execution: ExecutionResult, options: { countFailure?: boolean } = {}): void {
    for (const request of execution.requestUsage) {
      if (request.totalTokens === null) this.unknownUsageRequests++;
      else this.knownTokens += request.totalTokens;
      if (request.costUsd !== null) this.knownCostUsd += request.costUsd;
    }
    if (options.countFailure === false) return;
    if (execution.failureKind === "infrastructure") this.consecutiveInfrastructureFailures++;
    else this.consecutiveInfrastructureFailures = 0;
    if (this.stopReason) return;
    if (execution.error && batchStoppingErrors.has(execution.error)) this.stopReason = execution.error;
    else if (this.consecutiveInfrastructureFailures >= this.policy.maxConsecutiveInfrastructureFailures) this.stopReason = "INFRASTRUCTURE_FAILURES";
    else if (this.policy.maxTotalTokens !== null && this.knownTokens >= this.policy.maxTotalTokens) this.stopReason = "TOKEN_CEILING";
    else if (this.policy.maxCostUsd !== null && this.knownCostUsd >= this.policy.maxCostUsd) this.stopReason = "COST_CEILING";
  }

  summary(notRun: Array<{ model: string; caseId: string; repetition: number }>) {
    return {
      policy: this.policy,
      stopReason: this.stopReason,
      knownTokens: this.knownTokens,
      knownCostUsd: this.knownCostUsd,
      unknownUsageRequests: this.unknownUsageRequests,
      notRun,
    };
  }
}
