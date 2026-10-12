import type { TrialRecord } from "./types.js";

export function summarize(records: TrialRecord[]) {
  const known = records.filter(record => record.execution.reportedTokens !== null);
  const passed = records.filter(record => record.evaluation.status === "passed").length;
  const decided = records.filter(record => record.evaluation.status === "passed" || record.evaluation.status === "failed");
  const acceptedDeliveries = records.filter(record => record.evaluation.status === "passed" && record.execution.status === "done" && record.cleanup === "cleaned").length;
  return {
    total: records.length,
    passed,
    decidedTrials: decided.length,
    successRate: decided.length > 0 ? passed / decided.length : null,
    decidedSuccessRate: decided.length > 0 ? passed / decided.length : null,
    evaluationCoverage: records.length > 0 ? decided.length / records.length : null,
    acceptedDeliveries,
    deliveryRate: records.length > 0 ? acceptedDeliveries / records.length : null,
    executionFailures: records.filter(record => record.execution.status !== "done").length,
    pendingReviews: records.filter(record => record.evaluation.status === "pending").length,
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

export function markdownReport(records: TrialRecord[]): string {
  const summary = summarize(records);
  const rows = records.map(record => `| ${record.caseId} | ${record.model.provider}:${record.model.id} | ${record.interactionClass ?? "candidate"} | ${record.toolProfile ?? "workspace-basic"} | ${record.execution.status} | ${record.evaluation.status} | ${record.execution.modelCalls} | ${record.execution.toolAttempts} | ${record.execution.toolIntercepts} | ${record.cleanup} |`);
  return ["# Evaluation report", "", `Objective pass rate: ${summary.passed}/${summary.decidedTrials} decided trials (${summary.decidedSuccessRate ?? "n/a"}). Objective coverage: ${summary.evaluationCoverage ?? "n/a"}. Accepted delivery: ${summary.acceptedDeliveries}/${summary.total} (${summary.deliveryRate ?? "n/a"}). Pending reviews: ${summary.pendingReviews}; unscored: ${summary.unscoredRuns}; resource-limit runs: ${summary.resourceLimitRuns}; evaluator errors: ${summary.evaluatorErrors}. Unknown usage is not zero.`, "",
    "| Case | Model | Request class | Tool profile | Execution | Evaluation | Model requests | Tool attempts | Intercepted | Cleanup |",
    "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |", ...rows, ""].join("\n");
}