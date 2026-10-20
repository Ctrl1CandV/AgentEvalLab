import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import type { AssistantMessage } from "@earendil-works/pi-ai";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import { classifyProviderFailure, failureOutcome } from "../src/harness/provider-errors.js";
import { createPiRunner } from "../src/harness/pi.js";
import { budgetStatement, defaultReminderThresholds } from "../src/harness/budget-notice.js";
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
    ["429 Your token-plan 1-month quota has been exhausted. The quota will reset at 10-19 16:00:00 UTC.", "balance"],
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

test("a response lost to a transient failure mid-stream is dropped and the session continues", async () => {
  const contexts: number[] = [];
  const runner = createPiRunner({ apiKey: "offline-resume-key", resumeDelayMs: 0, stream: ((selected: { api: string; provider: string; id: string }, context: { messages: unknown[] }) => {
    contexts.push(context.messages.length);
    const stream = new AssistantMessageEventStream();
    if (contexts.length === 1) {
      const message = { ...failed("stream ended unexpectedly (key offline-resume-key)"), api: selected.api };
      stream.push({ type: "start", partial: { ...message, stopReason: "pending" } } as never);
      stream.push({ type: "error", reason: "error", error: message } as never);
      return stream;
    }
    const message = { role: "assistant", content: [{ type: "text", text: "done" }], api: selected.api, provider: selected.provider, model: selected.id,
      usage: { input: 4, output: 3, cacheRead: 0, cacheWrite: 0, totalTokens: 7, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      stopReason: "stop", timestamp: 0 };
    stream.push({ type: "start", partial: { ...message, content: [], stopReason: "pending" } } as never);
    stream.push({ type: "done", reason: "stop", message } as never);
    return stream;
  }) as never });
  const events: string[] = [];
  const result = await runner({ prompt: "go" }, parseModel("anthropic:claude-sonnet-4-6"), { ...defaultBudget, maxModelCalls: 1 },
    async type => { events.push(type); });
  assert.equal(result.status, "done", "the lost response counts toward no budget, so one model call is enough");
  assert.equal(result.output, "done");
  assert.deepEqual(contexts, [1, 1], "the continuation resends the prompt without the broken response");
  assert.equal(result.modelCalls, 2);
  assert.equal(result.requestUsage[0]!.retried, true);
  assert.equal(result.requestUsage[0]!.failureClass, "other");
  assert.equal(result.requestUsage[0]!.failureMessage, "stream ended unexpectedly (key [REDACTED])");
  assert.equal(result.reportedTokens, 7);
  assert.ok(events.includes("model_request_resumed"));
});

test("a session continues at most twice, then ends as an infrastructure failure", async () => {
  let requests = 0;
  const runner = createPiRunner({ apiKey: "offline", resumeDelayMs: 0, stream: ((selected: { api: string }) => {
    requests++;
    const message = { ...failed("503 Service Unavailable"), api: selected.api };
    const stream = new AssistantMessageEventStream();
    stream.push({ type: "start", partial: { ...message, stopReason: "pending" } } as never);
    stream.push({ type: "error", reason: "error", error: message } as never);
    return stream;
  }) as never });
  const result = await runner({ prompt: "go" }, parseModel("anthropic:claude-sonnet-4-6"), { ...defaultBudget }, async () => {});
  assert.equal(requests, 3);
  assert.equal(result.failureKind, "infrastructure");
  assert.equal(result.error, "PROVIDER_UNAVAILABLE");
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

test("a provider's failures stop only that provider", async () => {
  const root = await mkdtemp(join(tmpdir(), "batch-provider-"));
  try {
    const twoProviders = { ...plan({ maxConsecutiveInfrastructureFailures: 2 }), models: [{ provider: "deepseek", id: "deepseek-flash" }, { provider: "supercn", id: "glm-5.3", thinkingLevel: "high" as const }] };
    const ran: string[] = [];
    const result = await runEvaluation(twoProviders, { outputRoot: root, runner: async (input, model) => {
      ran.push(`${model.provider}:${input.prompt}`);
      return model.provider === "supercn" ? infra("PROVIDER_AUTH") : ok();
    } });
    assert.equal(ran.filter(entry => entry.startsWith("deepseek")).length, 4, "deepseek runs every case");
    assert.equal(ran.filter(entry => entry.startsWith("supercn")).length, 1, "supercn stops after its first failure");
    assert.equal(result.report.batch!.stopReason, "PROVIDER_AUTH");
    assert.deepEqual(result.report.batch!.providerStops, { supercn: "PROVIDER_AUTH" });
    assert.deepEqual(result.report.batch!.notRun.map(entry => entry.model), ["supercn:glm-5.3", "supercn:glm-5.3", "supercn:glm-5.3"]);
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

test("a per-model ceiling stops only that model, and a per-trial cap is reserved before a trial starts", async () => {
  const root = await mkdtemp(join(tmpdir(), "batch-per-model-"));
  try {
    const twoModels = (batch: EvaluationPlan["batch"], maxTrialTokens?: number): EvaluationPlan => ({ ...plan(batch, 3),
      models: [{ provider: "deepseek", id: "deepseek-flash" }, { provider: "aliplan", id: "qwen3.8-flash" }],
      budget: { ...defaultBudget, ...(maxTrialTokens ? { maxTrialTokens } : {}) } });
    const heavy = async (_input: unknown, model: { provider: string }) => ok(model.provider === "deepseek" ? 600 : 10);
    const perModel = await runEvaluation(twoModels({ maxTotalTokensPerModel: 1_000 }), { outputRoot: root, runner: heavy as never });
    assert.equal(perModel.report.batch!.stopReason, null, "a model's ceiling does not stop the batch");
    assert.deepEqual(perModel.report.batch!.notRun.map(entry => [entry.model, entry.reason]), [["deepseek:deepseek-flash", "MODEL_TOKEN_CEILING"]]);
    assert.equal(perModel.report.records.filter(record => record.model.provider === "aliplan").length, 3, "the other model keeps running");
    assert.deepEqual(perModel.report.batch!.tokensByModel, { "deepseek:deepseek-flash": 1_200, "aliplan:qwen3.8-flash": 30 });

    // With a 600-token trial cap, a second deepseek trial could cross the 1,000-token ceiling, so it never starts.
    const reserved = await runEvaluation(twoModels({ maxTotalTokensPerModel: 1_000 }, 600), { outputRoot: root, runner: heavy as never });
    assert.equal(reserved.report.batch!.tokensByModel!["deepseek:deepseek-flash"], 600);
    assert.equal(reserved.report.batch!.notRun.length, 2);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("the runner ends a trial with TRIAL_TOKEN_LIMIT before a request that would follow the cap", async () => {
  let call = 0;
  const stream = (selected: { api: string; provider: string; id: string }) => {
    call++;
    const content = call < 5 ? [{ type: "toolCall" as const, id: `c${call}`, name: "noop", arguments: {} }] : [{ type: "text" as const, text: "done" }];
    const message = { role: "assistant" as const, content, api: selected.api, provider: selected.provider, model: selected.id,
      usage: { input: 0, output: 100, cacheRead: 300, cacheWrite: 0, totalTokens: 400, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      stopReason: call < 5 ? "toolUse" as const : "stop" as const, timestamp: Date.now() };
    const events = new AssistantMessageEventStream();
    events.push({ type: "start", partial: { ...message, content: [], stopReason: "pending" } } as never);
    events.push({ type: "done", reason: message.stopReason, message } as never);
    return events;
  };
  const noop = { name: "noop", label: "Noop", description: "Do nothing.", parameters: { type: "object", properties: {} },
    async execute() { return { content: [{ type: "text", text: "ok" }], details: {} }; } };
  const runner = createPiRunner({ apiKey: "offline", stream: stream as never, createTools: () => [noop as never] });
  const result = await runner({ prompt: "go" }, parseModel("anthropic:claude-sonnet-4-6"), { ...defaultBudget, maxTrialTokens: 1_000 }, async () => {});
  assert.equal(result.status, "budget_exceeded");
  assert.equal(result.error, "TRIAL_TOKEN_LIMIT");
  assert.equal(result.modelCalls, 3, "cached input counts in full: 3 x 400 tokens passes the 1,000-token cap");
});

test("the budget is stated in the prompt and reminders arrive only after passing 50%, 75% and 90%", async () => {
  const budget = { ...defaultBudget, maxTurns: 40, maxModelCalls: 40, maxToolCalls: 40, timeoutMs: 600_000, maxTrialTokens: 2_000 };
  const statement = budgetStatement(budget, defaultReminderThresholds);
  assert.match(statement, /Tokens: at most 2,000 for the whole task/);
  assert.match(statement, /graded as it stands/);
  assert.match(statement, /after you pass 50%, 75% and 90% of any limit/);

  // Each response costs 100 of 2,000 tokens, so responses 10, 15 and 18 pass 50%, 75% and 90%; response 19 answers.
  let call = 0;
  const statusSeen: Array<[number, string]> = [];
  const stream = (selected: { api: string; provider: string; id: string }, context: { messages: Array<{ role: string; content: unknown }> }) => {
    call++;
    const last = context.messages.at(-1);
    if (last?.role === "user" && typeof last.content === "string" && last.content.startsWith("[Budget status]")) statusSeen.push([call, last.content]);
    const content = call < 19 ? [{ type: "toolCall" as const, id: `c${call}`, name: "noop", arguments: {} }] : [{ type: "text" as const, text: "done" }];
    const message = { role: "assistant" as const, content, api: selected.api, provider: selected.provider, model: selected.id,
      usage: { input: 50, output: 50, cacheRead: 0, cacheWrite: 0, totalTokens: 100, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      stopReason: call < 19 ? "toolUse" as const : "stop" as const, timestamp: Date.now() };
    const events = new AssistantMessageEventStream();
    events.push({ type: "start", partial: { ...message, content: [], stopReason: "pending" } } as never);
    events.push({ type: "done", reason: message.stopReason, message } as never);
    return events;
  };
  const noop = { name: "noop", label: "Noop", description: "Do nothing.", parameters: { type: "object", properties: {} },
    async execute() { return { content: [{ type: "text", text: "ok" }], details: {} }; } };
  const notices: Array<{ threshold: number }> = [];
  const runner = createPiRunner({ apiKey: "offline", stream: stream as never, createTools: () => [noop as never], budgetReminders: defaultReminderThresholds });
  const result = await runner({ prompt: "go" }, parseModel("anthropic:claude-sonnet-4-6"), budget,
    async (type, _counts, details) => { if (type === "budget_notice") notices.push(details as { threshold: number }); });
  assert.equal(result.status, "done", result.error ?? "");
  assert.deepEqual(notices.map(notice => notice.threshold), [0.5, 0.75, 0.9]);
  assert.deepEqual(statusSeen.map(([at]) => at), [11, 16, 19], "each status precedes the request after the response that passed a threshold");
  assert.match(statusSeen[0]![1], /1,000 of 2,000 tokens \(50%\), 10 of 40 model responses, 10 of 40 tool calls/);

  // Without reminders configured, no status is ever sent.
  call = 0; statusSeen.length = 0;
  await createPiRunner({ apiKey: "offline", stream: stream as never, createTools: () => [noop as never] })({ prompt: "go" }, parseModel("anthropic:claude-sonnet-4-6"), budget, async () => {});
  assert.equal(statusSeen.length, 0);
});

test("a plan's budgetNotice appends the statement to the prompt and is validated", async () => {
  const root = await mkdtemp(join(tmpdir(), "batch-notice-"));
  try {
    const prompts: string[] = [];
    const noticePlan: EvaluationPlan = { ...plan({ maxTotalTokens: 1_000_000 }, 1), budgetNotice: true, budget: { ...defaultBudget, maxTrialTokens: 50_000 } };
    validatePlan(noticePlan);
    await runEvaluation(noticePlan, { outputRoot: root, runner: async input => { prompts.push(input.prompt); return ok(); } });
    assert.match(prompts[0]!, /^p\n\nBudget for this task, the same for every model:\n- Tokens: at most 50,000/);
    await runEvaluation(plan({ maxTotalTokens: 1_000_000 }, 1), { outputRoot: root, runner: async input => { prompts.push(input.prompt); return ok(); } });
    assert.equal(prompts[1], "p", "without budgetNotice the prompt is unchanged");
    assert.throws(() => validatePlan({ ...noticePlan, budgetNotice: { reminders: [0.9, 0.5] } } as never), /INVALID_BUDGET_NOTICE/);
    validatePlan({ ...noticePlan, budgetNotice: { reminders: [0.8] } });
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("concurrent trials run up to the limit, record every trial, and reserve their budgets against ceilings", async () => {
  const root = await mkdtemp(join(tmpdir(), "batch-concurrency-"));
  try {
    let running = 0, peak = 0;
    const slow = async () => {
      running++; peak = Math.max(peak, running);
      await new Promise(resolveDelay => setTimeout(resolveDelay, 30));
      running--;
      return ok(10);
    };
    const parallel = await runEvaluation(plan({ concurrency: 3, maxTotalTokens: 1_000_000 }, 7), { outputRoot: root, runner: slow });
    assert.equal(parallel.report.recordedRuns, 7);
    assert.equal(peak, 3, "three trials run at once");
    assert.deepEqual(parallel.report.records.map(record => record.caseId).sort(), Array.from({ length: 7 }, (_, index) => `case-${index + 1}`).sort());
    const sequential = await runEvaluation(plan({ maxTotalTokens: 1_000_000 }, 7), { outputRoot: root, runner: async () => ok(10) });
    const fingerprintOf = async (directory: string) => (JSON.parse(await readFile(join(directory, "experiment.json"), "utf8")) as { fingerprint: string }).fingerprint;
    assert.equal(await fingerprintOf(parallel.directory), await fingerprintOf(sequential.directory), "concurrency does not enter the fingerprint");
    const saved = JSON.parse(await readFile(join(parallel.directory, "report.json"), "utf8")) as { recordedRuns: number };
    assert.equal(saved.recordedRuns, 7, "the last report write wins with every trial");

    // Each running trial holds its 600-token budget: with a 1,000-token ceiling only one may start at a time.
    running = 0; peak = 0;
    const reserved = await runEvaluation({ ...plan({ concurrency: 3, maxTotalTokensPerModel: 1_000 }, 3), budget: { ...defaultBudget, maxTrialTokens: 600 } },
      { outputRoot: root, runner: async () => { running++; peak = Math.max(peak, running); await new Promise(r => setTimeout(r, 20)); running--; return ok(10); } });
    assert.equal(peak, 1, "reservations keep concurrent trials within the ceiling");
    assert.equal(reserved.report.batch!.notRun.length, 2);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("batch policies are validated", () => {
  validatePlan(plan({ maxRetries: 3, maxTotalTokens: 5_000_000, maxTotalTokensPerModel: 3_000_000, maxCostUsd: 20 }));
  assert.throws(() => validatePlan(plan({ maxTotalTokensPerModel: 0 })), /INVALID_BATCH_POLICY:maxTotalTokensPerModel/);
  assert.throws(() => validatePlan(plan({ concurrency: 0 })), /INVALID_BATCH_POLICY:concurrency/);
  assert.throws(() => validatePlan({ ...plan({}), budget: { ...defaultBudget, maxTrialTokens: -1 } }), /INVALID_BUDGET:maxTrialTokens/);
  assert.throws(() => validatePlan(plan({ maxRetries: 9 })), /INVALID_BATCH_POLICY:maxRetries/);
  assert.throws(() => validatePlan(plan({ unknown: 1 } as never)), /INVALID_BATCH_POLICY/);
});
