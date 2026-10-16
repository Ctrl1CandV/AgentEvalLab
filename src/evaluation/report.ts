import { modelOptions, type ModelSelection, type RequestUsage } from "../types.js";
import { meanInterval, pairedDifference, passAtK, passHatK, wilsonInterval } from "./statistics.js";
import type { TrialRecord } from "./types.js";
import type { BatchSummary } from "./batch.js";

/**
 * Operational counts across records. No cross-task success rate is computed: engineering,
 * reasoning and tool tasks measure different things (SPEC rule 7); rates live in byTask.
 */
export function summarize(records: TrialRecord[]) {
  const known = records.filter(record => record.execution.reportedTokens !== null);
  return {
    total: records.length,
    passed: records.filter(record => record.evaluation.status === "passed").length,
    failed: records.filter(record => record.evaluation.status === "failed").length,
    decidedTrials: records.filter(record => record.evaluation.status === "passed" || record.evaluation.status === "failed").length,
    acceptedDeliveries: records.filter(record => record.evaluation.status === "passed" && record.execution.status === "done" && record.cleanup === "cleaned").length,
    executionFailures: records.filter(record => record.execution.status !== "done").length,
    infrastructureFailures: records.filter(record => record.execution.failureKind === "infrastructure").length,
    pendingReviews: records.filter(record => record.evaluation.status === "pending").length,
    // Objective verdicts whose non-critical human-review checks are still open.
    pendingHumanChecks: records.filter(record => record.evaluation.review?.status === "pending").length,
    evaluatorErrors: records.filter(record => record.evaluation.status === "error").length,
    unscoredRuns: records.filter(record => record.evaluation.status === "unscored").length,
    resourceLimitRuns: records.filter(record => record.evaluation.status === "resource_limit").length,
    cleanupFailures: records.filter(record => record.cleanup === "error").length,
    modelCalls: records.reduce((sum, record) => sum + record.execution.modelCalls, 0),
    toolCalls: records.reduce((sum, record) => sum + record.execution.toolCalls, 0),
    toolAttempts: records.reduce((sum, record) => sum + record.execution.toolAttempts, 0),
    toolIntercepts: records.reduce((sum, record) => sum + record.execution.toolIntercepts, 0),
    toolExecutions: records.reduce((sum, record) => sum + record.execution.toolExecutions, 0),
    turns: records.reduce((sum, record) => sum + record.execution.turns, 0),
    durationMs: records.reduce((sum, record) => sum + record.durationMs, 0),
    reportedTokens: known.length === records.length && records.length > 0 ? known.reduce((sum, record) => sum + record.execution.reportedTokens!, 0) : null,
    knownUsageRuns: known.length,
    toolEvidenceTruncatedRuns: records.filter(record => record.execution.toolEvidenceTruncated).length,
  };
}

function sumKnown(values: Array<number | null>): number | null {
  return values.length > 0 && values.every(value => value !== null)
    ? values.reduce<number>((sum, value) => sum + value!, 0)
    : null;
}

export function summarizeInteractionClass(records: TrialRecord[], interactionClass: "candidate" | "probe") {
  const requests = records.flatMap(record => (record.execution.requestUsage ?? []).filter(request => request.interactionClass === interactionClass));
  const matchingRecords = records.filter(record => interactionClass === "candidate"
    ? (record.interactionClass ?? "candidate") === "candidate"
    : (record.execution.requestUsage ?? []).some(request => request.interactionClass === "probe"));
  return {
    records: matchingRecords.length,
    requests: requests.length,
    completedRequests: requests.filter(request => request.status === "completed").length,
    failedOrIncompleteRequests: requests.filter(request => request.status !== "completed").length,
    reportedUsageRequests: requests.filter(request => request.usageStatus === "reported").length,
    partialOrUnknownUsageRequests: requests.filter(request => request.usageStatus !== "reported").length,
    inputTokens: sumKnown(requests.map(request => request.inputTokens)),
    outputTokens: sumKnown(requests.map(request => request.outputTokens)),
    cacheReadTokens: sumKnown(requests.map(request => request.cacheReadTokens)),
    cacheWriteTokens: sumKnown(requests.map(request => request.cacheWriteTokens)),
    reasoningTokens: sumKnown(requests.map(request => request.reasoningTokens)),
    totalTokens: sumKnown(requests.map(request => request.totalTokens)),
    costUsd: sumKnown(requests.map(request => request.costUsd)),
    requestDurationMs: sumKnown(requests.map(request => request.durationMs)),
    toolAttempts: matchingRecords.reduce((sum, record) => sum + record.execution.toolAttempts, 0),
    toolIntercepts: matchingRecords.reduce((sum, record) => sum + record.execution.toolIntercepts, 0),
    toolExecutions: matchingRecords.reduce((sum, record) => sum + record.execution.toolExecutions, 0),
  };
}

export interface ReportContext {
  plannedRuns: number;
  completed: boolean;
  models: ModelSelection[];
  /** Task capability per case ID; cases without a manifest are "unspecified". */
  capabilities: Record<string, string>;
  repetitions: number;
  batch?: BatchSummary;
}

const modelKey = (model: ModelSelection) => `${model.provider}:${model.id}`;

/**
 * Display label: the model with its thinking condition appended, as in supergpt:gpt-6-luna-medium. "default" means
 * no thinking parameter was sent, so the provider's default applied. Temperature is listed in the report's model table.
 */
export function modelLabel(model: ModelSelection): string {
  const { thinkingLevel } = modelOptions(model);
  return `${modelKey(model)}-${thinkingLevel === "provider-default" ? "default" : thinkingLevel}`;
}

/** Median and maximum of known values; trials with unknown values are counted, never treated as zero. */
function distribution(values: Array<number | null>) {
  const known = values.filter((value): value is number => value !== null).sort((left, right) => left - right);
  const middle = Math.floor(known.length / 2);
  const median = known.length === 0 ? null : known.length % 2 ? known[middle]! : (known[middle - 1]! + known[middle]!) / 2;
  return { median, max: known.length ? known[known.length - 1]! : null, unknown: values.length - known.length };
}

/**
 * Context tokens one request processed: uncached input, cache reads and cache writes, or null when any part is
 * unreported. Whether input hits a cache depends on the endpoint, so the sum, not the split, describes the model's run.
 */
function requestContext(request: RequestUsage): number | null {
  return request.inputTokens !== null && request.cacheReadTokens !== null && request.cacheWriteTokens !== null
    ? request.inputTokens + request.cacheReadTokens + request.cacheWriteTokens : null;
}

/** One trial's reported tokens of one kind, or null when any request lacks that figure. */
function trialTokens(record: TrialRecord, value: (request: RequestUsage) => number | null = request => request.totalTokens): number | null {
  const values = (record.execution.requestUsage ?? []).map(value);
  return values.length > 0 && values.every(item => item !== null) ? values.reduce((sum, item) => sum + item!, 0) : null;
}

/** Reported tokens of all trials in a group, or null when any trial lacks reported usage. */
function trialTokensSum(records: TrialRecord[]): number | null {
  const values = records.map(record => trialTokens(record));
  return values.every(value => value !== null) ? values.reduce<number>((sum, value) => sum + value!, 0) : null;
}

/** The largest context one request of the trial processed. */
function peakContext(record: TrialRecord): number | null {
  const values = (record.execution.requestUsage ?? []).map(requestContext);
  return values.length > 0 && values.every(item => item !== null) ? Math.max(...values as number[]) : null;
}

/** Per model and task: verdict counts, pass rates with Wilson intervals, pass@k/pass^k, and per-check rates. */
export function taskResults(records: TrialRecord[], context: ReportContext) {
  const groups = new Map<string, TrialRecord[]>();
  for (const record of records) {
    const key = `${modelKey(record.model)}\u0000${record.caseId}`;
    groups.set(key, [...(groups.get(key) ?? []), record]);
  }
  return [...groups.values()].map(group => {
    const first = group[0]!;
    const decided = group.filter(record => record.evaluation.status === "passed" || record.evaluation.status === "failed");
    const passes = decided.filter(record => record.evaluation.status === "passed").length;
    const statuses: Record<string, number> = {};
    for (const record of group) statuses[record.evaluation.status] = (statuses[record.evaluation.status] ?? 0) + 1;
    const checkIds = [...new Set(group.flatMap(record => record.evaluation.checks.map(check => check.id)))].sort();
    const checks = checkIds.map(id => {
      const values = group.map(record => record.evaluation.checks.find(check => check.id === id)?.passed).filter(value => value !== undefined && value !== null);
      const passed = values.filter(value => value === true).length;
      return { id, passed, judged: values.length, rate: values.length ? passed / values.length : null };
    });
    const k = context.repetitions;
    // How each execution ended: "done" or the stop code (budget limits, provider failures, timeouts).
    const executionOutcomes: Record<string, number> = {};
    for (const record of group) {
      const outcome = record.execution.status === "done" ? "done" : record.execution.error ?? record.execution.status;
      executionOutcomes[outcome] = (executionOutcomes[outcome] ?? 0) + 1;
    }
    // Partial-credit scores of graded trials; trials without a score (skipped, unscored, errors) are excluded.
    const scores = group.map(record => record.evaluation.score).filter((score): score is number => typeof score === "number");
    const score = meanInterval(scores);
    const resolvedTokens = trialTokensSum(group);
    return {
      model: modelKey(first.model),
      label: modelLabel(first.model),
      caseId: first.caseId,
      capability: context.capabilities[first.caseId] ?? "unspecified",
      trials: group.length,
      decided: decided.length,
      passes,
      passRate: decided.length ? passes / decided.length : null,
      interval: wilsonInterval(passes, decided.length),
      scored: scores.length,
      meanScore: score.mean,
      scoreInterval: score.interval,
      // Efficiency is reported, never scored: tokens spent per resolved trial, and trials stopped by a budget.
      tokensPerResolved: passes > 0 && resolvedTokens !== null ? resolvedTokens / passes : null,
      budgetStops: group.filter(record => record.execution.failureKind === "budget").length,
      k,
      passAtK: k > 1 ? passAtK(decided.length, passes, k) : null,
      passHatK: k > 1 ? passHatK(decided.length, passes, k) : null,
      statuses,
      malformedAnswers: group.filter(record => record.evaluation.checks.some(check => check.id === "answer-format" && check.passed === false)).length,
      reviewPending: group.filter(record => record.evaluation.review?.status === "pending").length,
      executionOutcomes,
      usage: {
        modelCalls: distribution(group.map(record => record.execution.modelCalls)),
        toolCalls: distribution(group.map(record => record.execution.toolCalls)),
        // Tokens are fixed units; prices never enter. Output is what the model generated (reasoning included);
        // input is every context token processed, of which cache reads are shown for information.
        totalTokens: distribution(group.map(record => trialTokens(record))),
        outputTokens: distribution(group.map(record => trialTokens(record, request => request.outputTokens))),
        inputTokens: distribution(group.map(record => trialTokens(record, requestContext))),
        cacheReadTokens: distribution(group.map(record => trialTokens(record, request => request.cacheReadTokens))),
        peakContextTokens: distribution(group.map(peakContext)),
        durationMs: distribution(group.map(record => record.durationMs)),
      },
      checks,
    };
  }).sort((left, right) => left.caseId.localeCompare(right.caseId) || left.model.localeCompare(right.model));
}

/** Paired model differences in per-task mean score, within one capability at a time. */
export function pairedComparisons(rows: ReturnType<typeof taskResults>, models: ModelSelection[]) {
  const keys = models.map(modelKey);
  const capabilities = [...new Set(rows.map(row => row.capability))].sort();
  const comparisons = [];
  for (const capability of capabilities) {
    const caseIds = [...new Set(rows.filter(row => row.capability === capability).map(row => row.caseId))];
    for (let left = 0; left < keys.length; left++) {
      for (let right = left + 1; right < keys.length; right++) {
        const differences: number[] = [];
        for (const caseId of caseIds) {
          const a = rows.find(row => row.caseId === caseId && row.model === keys[left]);
          const b = rows.find(row => row.caseId === caseId && row.model === keys[right]);
          if (a?.meanScore != null && b?.meanScore != null) differences.push(a.meanScore - b.meanScore);
        }
        comparisons.push({ capability, modelA: keys[left]!, modelB: keys[right]!, labelA: modelLabel(models[left]!), labelB: modelLabel(models[right]!),
          ...pairedDifference(differences) });
      }
    }
  }
  return comparisons;
}

export function buildReport(records: TrialRecord[], context: ReportContext) {
  const byTask = taskResults(records, context);
  return {
    version: 2,
    plannedRuns: context.plannedRuns,
    recordedRuns: records.length,
    completed: context.completed,
    repetitions: context.repetitions,
    scoreRunPolicy: "latest-append-only-score-run-per-trial",
    ...(context.batch !== undefined ? { batch: context.batch } : {}),
    summary: summarize(records),
    byTask,
    pairedComparisons: pairedComparisons(byTask, context.models),
    byInteractionClass: {
      candidate: summarizeInteractionClass(records, "candidate"),
      probe: summarizeInteractionClass(records, "probe"),
    },
    byModel: context.models.map(model => ({ model, label: modelLabel(model), summary: summarize(records.filter(record => modelKey(record.model) === modelKey(model))) })),
    records,
  };
}

const percent = (value: number | null | undefined) => value === null || value === undefined ? "n/a" : `${(value * 100).toFixed(1)}%`;
const interval = (value: [number, number] | null) => value ? `${percent(value[0])}–${percent(value[1])}` : "n/a";

export function markdownReport(report: ReturnType<typeof buildReport>): string {
  const { summary } = report;
  const lines = ["# Evaluation report", "",
    `Trials: ${summary.total} of ${report.plannedRuns} planned${report.completed ? "" : " (incomplete)"}; repetitions per model and case: ${report.repetitions}. ` +
    `Pending reviews: ${summary.pendingReviews}; verdicts awaiting human checks: ${summary.pendingHumanChecks}; unscored: ${summary.unscoredRuns}; ` +
    `resource-limit runs: ${summary.resourceLimitRuns}; evaluator errors: ${summary.evaluatorErrors}; infrastructure failures: ${summary.infrastructureFailures}. Unknown usage is not zero.`,
    "", "## Models", "",
    "Labels append the thinking level; \"default\" means no thinking parameter was sent and the provider's default applied.", "",
    "| Label | Model | Thinking | Temperature |", "| --- | --- | --- | --- |",
    ...report.byModel.map(({ model }) => {
      const options = modelOptions(model);
      return `| ${modelLabel(model)} | ${modelKey(model)} | ${options.thinkingLevel} | ${options.temperature ?? "provider default"} |`;
    }),
    "", "## Results by task", "",
    `Score is partial credit: the fraction of content checks a trial passed, less the task's format penalty when the answer had to be recovered; its 95% interval is the Wilson interval of the score sum, which is conservative for scores in [0, 1]. A trial is resolved when every critical check passes; the resolved rate counts decided trials and uses a 95% Wilson interval, and pass@k and pass^k use k = ${report.repetitions}. Budget stops and timeouts are graded and count; infrastructure failures are skipped and excluded.`, "",
    "| Task | Capability | Model | Mean score | 95% interval | Resolved | Resolved/decided | 95% interval | pass@k | pass^k | Format failures | Review pending |",
    "| --- | --- | --- | ---: | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ...report.byTask.map(row => `| ${row.caseId} | ${row.capability} | ${row.label} | ${percent(row.meanScore)} | ${interval(row.scoreInterval)} | ${percent(row.passRate)} | ${row.passes}/${row.decided} | ${interval(row.interval)} | ${percent(row.passAtK)} | ${percent(row.passHatK)} | ${row.malformedAnswers} | ${row.reviewPending} |`),
    ""];
  const range = (value: { median: number | null; max: number | null; unknown: number }, scale = 1, digits = 0) =>
    value.median === null ? "unknown" : `${(value.median / scale).toFixed(digits)} / ${(value.max! / scale).toFixed(digits)}${value.unknown ? ` (+${value.unknown} unknown)` : ""}`;
  lines.push("## Usage by task", "", "Median / maximum per trial. Tokens are fixed units in thousands, without prices. Output is generated text, tool calls and reasoning. Input counts every context token each request processed, cached or not; whether input hits a cache depends on the endpoint, so cache reads are shown for information only. Peak context is the largest single request. Total = input + output. Tokens per resolved trial divides all tokens of the row by its resolved trials; efficiency is reported for information and never enters the score. Execution outcomes show how trials ended; budget stops such as MODEL_CALL_LIMIT, OUTPUT_TOKEN_LIMIT or TRIAL_TOKEN_LIMIT indicate a binding budget.", "",
    "| Task | Model | Model calls | Tool calls | Output | Input | of which cache reads | Peak context | Total | Tokens per resolved trial | Duration (s) | Execution outcomes |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ...report.byTask.map(row => `| ${row.caseId} | ${row.label} | ${range(row.usage.modelCalls)} | ${range(row.usage.toolCalls)} | ${range(row.usage.outputTokens, 1000, 1)} | ${range(row.usage.inputTokens, 1000, 1)} | ${range(row.usage.cacheReadTokens, 1000, 1)} | ${range(row.usage.peakContextTokens, 1000, 1)} | ${range(row.usage.totalTokens, 1000, 1)} | ${row.tokensPerResolved === null ? "n/a" : (row.tokensPerResolved / 1000).toFixed(1)} | ${range(row.usage.durationMs, 1000, 1)} | ${Object.entries(row.executionOutcomes).map(([key, count]) => `${key} ${count}`).join(", ")} |`),
    "");
  const sum = (values: Array<number | null>) => values.reduce<number>((total, value) => total + (value ?? 0), 0);
  const thousands = (value: number) => (value / 1000).toFixed(1);
  lines.push("## Token use by model", "", "Sums over recorded trials, in thousands; requests without reported usage add nothing and are counted under the batch.", "",
    "| Model | Trials | Output | Input | of which cache reads | Total |", "| --- | ---: | ---: | ---: | ---: | ---: |",
    ...report.byModel.map(({ model, label }) => {
      const requests = report.records.filter(record => modelKey(record.model) === modelKey(model)).flatMap(record => record.execution.requestUsage ?? []);
      const trials = report.records.filter(record => modelKey(record.model) === modelKey(model)).length;
      return `| ${label} | ${trials} | ${thousands(sum(requests.map(request => request.outputTokens)))} | ${thousands(sum(requests.map(requestContext)))} | ${thousands(sum(requests.map(request => request.cacheReadTokens)))} | ${thousands(sum(requests.map(request => request.totalTokens)))} |`;
    }), "");
  if (report.batch) {
    const { policy, stopReason, knownTokens, unknownUsageRequests, notRun } = report.batch;
    const reasons = [...new Set(notRun.map(entry => entry.reason ?? stopReason ?? "unknown"))];
    lines.push(`Batch: ${thousands(knownTokens)}k known tokens (ceiling ${policy.maxTotalTokens == null ? "none" : `${thousands(policy.maxTotalTokens)}k`}; per model ${policy.maxTotalTokensPerModel == null ? "none" : `${thousands(policy.maxTotalTokensPerModel)}k`}); ` +
      `requests without usage: ${unknownUsageRequests}; stop reason: ${stopReason ?? "none"}; trials not run: ${notRun.length}${reasons.length ? ` (${reasons.join(", ")})` : ""}.`, "");
  }
  if (report.pairedComparisons.length) {
    lines.push("## Paired model differences", "", "Mean per-task score difference (A − B) within one capability, with a 95% t interval over tasks, clipped to ±100%; no interval with fewer than two tasks. With few tasks the interval is wide by construction.", "",
      "| Capability | Model A | Model B | Tasks | Mean difference | 95% interval |", "| --- | --- | --- | ---: | ---: | --- |",
      ...report.pairedComparisons.map(row => `| ${row.capability} | ${row.labelA} | ${row.labelB} | ${row.tasks} | ${percent(row.mean)} | ${interval(row.interval)} |`), "");
  }
  lines.push("## Trials", "",
    "| Case | Repetition | Model | Request class | Tool profile | Execution | Evaluation | Human review | Model requests | Tool attempts | Intercepted | Cleanup |",
    "| --- | ---: | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ...report.records.map(record => `| ${record.caseId} | ${record.repetition ?? 1} | ${modelLabel(record.model)} | ${record.interactionClass ?? "candidate"} | ${record.toolProfile ?? "workspace-basic"} | ${record.execution.status}${record.execution.error ? ` (${record.execution.error})` : ""} | ${record.evaluation.status} | ${record.evaluation.review?.status ?? "—"} | ${record.execution.modelCalls} | ${record.execution.toolAttempts} | ${record.execution.toolIntercepts} | ${record.cleanup} |`),
    "");
  return lines.join("\n");
}
