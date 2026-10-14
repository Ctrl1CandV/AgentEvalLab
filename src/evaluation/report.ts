import { modelOptions, type ModelSelection } from "../types.js";
import { pairedDifference, passAtK, passHatK, wilsonInterval } from "./statistics.js";
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

/** Total reported tokens of one trial, or null when any request lacks reported usage. */
function trialTokens(record: TrialRecord): number | null {
  const requests = record.execution.requestUsage ?? [];
  return requests.length > 0 && requests.every(request => request.totalTokens !== null)
    ? requests.reduce((sum, request) => sum + request.totalTokens!, 0) : null;
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
        totalTokens: distribution(group.map(trialTokens)),
        durationMs: distribution(group.map(record => record.durationMs)),
      },
      checks,
    };
  }).sort((left, right) => left.caseId.localeCompare(right.caseId) || left.model.localeCompare(right.model));
}

/** Paired model differences in per-task pass rate, within one capability at a time. */
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
          if (a?.passRate != null && b?.passRate != null) differences.push(a.passRate - b.passRate);
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
    `Pass rates count decided trials (passed or failed) only. Intervals are 95% Wilson intervals; pass@k and pass^k use k = ${report.repetitions}.`, "",
    "| Task | Capability | Model | Decided/trials | Pass rate | 95% interval | pass@k | pass^k | Malformed answers | Review pending |",
    "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ...report.byTask.map(row => `| ${row.caseId} | ${row.capability} | ${row.label} | ${row.decided}/${row.trials} | ${percent(row.passRate)} | ${interval(row.interval)} | ${percent(row.passAtK)} | ${percent(row.passHatK)} | ${row.malformedAnswers} | ${row.reviewPending} |`),
    ""];
  const range = (value: { median: number | null; max: number | null; unknown: number }, scale = 1, digits = 0) =>
    value.median === null ? "unknown" : `${(value.median / scale).toFixed(digits)} / ${(value.max! / scale).toFixed(digits)}${value.unknown ? ` (+${value.unknown} unknown)` : ""}`;
  lines.push("## Usage by task", "", "Median / maximum per trial. Execution outcomes show how trials ended; budget stops such as MODEL_CALL_LIMIT or OUTPUT_TOKEN_LIMIT indicate a binding budget.", "",
    "| Task | Model | Model calls | Tool calls | Tokens (thousands) | Duration (s) | Execution outcomes |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...report.byTask.map(row => `| ${row.caseId} | ${row.label} | ${range(row.usage.modelCalls)} | ${range(row.usage.toolCalls)} | ${range(row.usage.totalTokens, 1000, 1)} | ${range(row.usage.durationMs, 1000, 1)} | ${Object.entries(row.executionOutcomes).map(([key, count]) => `${key} ${count}`).join(", ")} |`),
    "");
  if (report.pairedComparisons.length) {
    lines.push("## Paired model differences", "", "Mean per-task pass-rate difference (A − B) within one capability, with a 95% t interval over tasks; no interval with fewer than two tasks.", "",
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
