import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import type { AssistantMessage } from "@earendil-works/pi-ai";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import { classifyProviderFailure, failureOutcome } from "../src/harness/provider-errors.js";
import { createPiRunner } from "../src/harness/pi.js";
import { defaultBudget, parseModel } from "../src/config.js";
import { emptyExecution, type ExecutionResult, type RequestUsage } from "../src/types.js";
import { runEvaluation } from "../src/evaluation/run.js";
import { rebuildReports } from "../src/evaluation/regrade.js";
import { validatePlan } from "../src/evaluation/validate.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";

function failed(errorMessage: string, input = 0): AssistantMessage {
  return { role: "assistant", content: [], api: "openai-completions", provider: "deepseek", model: "deepseek-flash",
    usage: { input, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: input, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    stopReason: "error", errorMessage, timestamp: 0 } as AssistantMessage;
}

test("provider failures are classified from status codes, messages and overflow patterns", () => {
  const cases: Array<[string, string]> = [
    ["401 Incorrect API key provided", "auth"],
    ["Provider (403): permission denied", "auth"],
    ["402 Insufficient Balance", "balance"],
    ["429 You exceeded your current quota, please check your plan and billing details", "balance"],
    ["429 Rate limit reached for requests", "rate_limit"],
    ["503 Service Unavailable", "server"],
    ["fetch failed: ECONNRESET", "network"],
    ["prompt is too long: 210000 tokens > 200000 maximum", "context_limit"],
    ["This model's maximum context length is 128000 tokens. However, your messages resulted in 140000 tokens", "context_limit"],
    ["400 Invalid tool schema", "other"],
  ];
  for (const [message, expected] of cases) assert.equal(classifyProviderFailure(failed(message), 128_000), expected, message);
  assert.deepEqual(failureOutcome("context_limit"), { failureKind: "budget", error: "CONTEXT_LIMIT" });
  assert.deepEqual(failureOutcome("rate_limit"), { failureKind: "infrastructure", error: "PROVIDER_UNAVAILABLE" });
});

test("the runner records a classified provider failure on the request and the run", async () => {
  const runner = createPiRunner({ apiKey: "offline", stream: ((selected: { api: string }) => {
    const message = { ...failed("401 Incorrect API key provided"), api: selected.api };
    const stream = new AssistantMessageEventStream();
    stream.push({ type: "start", partial: { ...message, stopReason: "pending" } } as never);
    stream.push({ type: "error", reason: "error", error: message } as never);
    return stream;
  }) as never });
  const result = await runner({ prompt: "go" }, parseModel("anthropic:claude-sonnet-4-6"), { ...defaultBudget }, async () => {});
  assert.equal(result.status, "error");
  assert.equal(result.failureKind, "infrastructure");
  assert.equal(result.error, "PROVIDER_AUTH");
  assert.equal(result.requestUsage[0]!.failureClass, "auth");
  assert.equal(result.requestUsage[0]!.attempts, 0, "injected streams make no HTTP request");
});

function usage(totalTokens: number | null): RequestUsage {
  return { requestId: "r", interactionClass: "candidate", status: "completed", usageStatus: totalTokens === null ? "missing" : "reported",
    durationMs: 1, inputTokens: null, outputTokens: null, cacheReadTokens: null, cacheWriteTokens: null, reasoningTokens: null,
    totalTokens, costUsd: null, attempts: 1, failureClass: null };
}

function plan(batch: EvaluationPlan["batch"], caseCount = 4): EvaluationPlan {
  return {
    name: "batch", models: [{ provider: "deepseek", id: "deepseek-flash" }], budget: { ...defaultBudget }, trustedLocalExecution: false, batch,
    cases: Array.from({ length: caseCount }, (_, index) => ({ id: `case-${index + 1}`, input: { prompt: "p" }, evaluator: { kind: "exact-match" as const, expected: "ok" } })),
  };
}

const ok = (tokens = 10): ExecutionResult => ({ ...emptyExecution(), output: "ok", modelCalls: 1, requestUsage: [usage(tokens)] });
const infra = (error: string): ExecutionResult => ({ ...emptyExecution(), status: "error", failureKind: "infrastructure", error, modelCalls: 1, requestUsage: [usage(null)] });

test("an authentication or balance error stops the batch and leaves the rest not run", async () => {
  const root = await mkdtemp(join(tmpdir(), "batch-stop-"));
  try {
    let calls = 0;
    const result = await runEvaluation(plan({}), { outputRoot: root, runner: async () => (++calls === 2 ? infra("PROVIDER_BALANCE") : ok()) });
    assert.equal(calls, 2);
    assert.equal(result.report.completed, false);
    assert.equal(result.report.batch!.stopReason, "PROVIDER_BALANCE");
    assert.deepEqual(result.report.batch!.notRun.map(entry => entry.caseId), ["case-3", "case-4"]);
    assert.equal(result.report.recordedRuns, 2);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("consecutive infrastructure failures and the token ceiling stop the batch", async () => {
  const root = await mkdtemp(join(tmpdir(), "batch-limits-"));
  try {
    let calls = 0;
    const failures = await runEvaluation(plan({ maxConsecutiveInfrastructureFailures: 2 }), { outputRoot: root,
      runner: async () => (++calls === 1 ? ok() : infra("PROVIDER_UNAVAILABLE")) });
    assert.equal(failures.report.batch!.stopReason, "INFRASTRUCTURE_FAILURES");
    assert.equal(failures.report.recordedRuns, 3);

    const ceiling = await runEvaluation(plan({ maxTotalTokens: 1_000 }), { outputRoot: root, runner: async () => ok(600) });
    assert.equal(ceiling.report.batch!.stopReason, "TOKEN_CEILING");
    assert.equal(ceiling.report.batch!.knownTokens, 1_200);
    assert.equal(ceiling.report.recordedRuns, 2);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("resume reruns only missing and infrastructure-failed trials of an identical plan", async () => {
  const root = await mkdtemp(join(tmpdir(), "batch-resume-"));
  try {
    const batchPlan = plan({ maxConsecutiveInfrastructureFailures: 1 });
    let calls = 0;
    const first = await runEvaluation(batchPlan, { outputRoot: root, runner: async () => (++calls === 2 ? infra("PROVIDER_UNAVAILABLE") : ok()) });
    assert.equal(first.report.batch!.stopReason, "INFRASTRUCTURE_FAILURES");
    const failedTrial = first.report.records[1]!;

    await assert.rejects(runEvaluation({ ...batchPlan, name: "changed" }, { outputRoot: root, resumeDirectory: first.directory, runner: async () => ok() }),
      /RESUME_FINGERPRINT_MISMATCH/);

    const rerun: string[] = [];
    const resumed = await runEvaluation(batchPlan, { outputRoot: root, resumeDirectory: first.directory,
      runner: async input => { rerun.push(input.prompt); return ok(); } });
    assert.equal(resumed.directory, first.directory);
    assert.equal(rerun.length, 3, "case-1 is kept; case-2 (infrastructure failure), case-3 and case-4 run");
    assert.equal(resumed.report.completed, true);
    assert.equal(resumed.report.summary.passed, 4);
    const replacement = resumed.report.records.find(record => record.caseId === "case-2")!;
    assert.equal(replacement.supersedes, failedTrial.id);
    const rebuilt = await rebuildReports(first.directory) as { records: Array<{ id: string }> };
    assert.equal(rebuilt.records.length, 4);
    assert.ok(!rebuilt.records.some(record => record.id === failedTrial.id), "superseded trials stay on disk but leave the report");
    assert.ok(JSON.parse(await readFile(join(first.directory, failedTrial.id, "result.json"), "utf8")));
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("batch policies are validated", () => {
  validatePlan(plan({ maxRetries: 3, maxTotalTokens: 5_000_000, maxCostUsd: 20 }));
  assert.throws(() => validatePlan(plan({ maxRetries: 9 })), /INVALID_BATCH_POLICY:maxRetries/);
  assert.throws(() => validatePlan(plan({ unknown: 1 } as never)), /INVALID_BATCH_POLICY/);
});
