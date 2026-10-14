import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import { Type } from "typebox";
import { createPiRunner } from "../src/harness/pi.js";
import { defaultBudget, parseModel } from "../src/config.js";
import { emptyExecution, type ModelSelection } from "../src/types.js";
import { validatePlan } from "../src/evaluation/validate.js";
import { runEvaluation } from "../src/evaluation/run.js";
import type { EvaluationPlan } from "../src/evaluation/types.js";

type StreamOptions = { temperature?: number; reasoning?: unknown };

function scriptedStream(steps: Array<{ toolCall?: { name: string; arguments: Record<string, unknown> }; text?: string }>,
  observe: (context: { messages: Array<{ role: string; content: unknown }> }, options: StreamOptions) => void) {
  let call = 0;
  return (selected: { api: string; provider: string; id: string }, context: never, options: StreamOptions) => {
    observe(context, options);
    const step = steps[Math.min(call++, steps.length - 1)]!;
    const content = step.toolCall
      ? [{ type: "toolCall" as const, id: `call-${call}`, name: step.toolCall.name, arguments: step.toolCall.arguments }]
      : [{ type: "text" as const, text: step.text ?? "done" }];
    const message = { role: "assistant" as const, content, api: selected.api, provider: selected.provider, model: selected.id,
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      stopReason: step.toolCall ? "toolUse" as const : "stop" as const, timestamp: Date.now() };
    const stream = new AssistantMessageEventStream();
    stream.push({ type: "start", partial: { ...message, content: [], stopReason: "pending" } } as never);
    stream.push({ type: "done", reason: message.stopReason, message } as never);
    return stream;
  };
}

test("an oversized tool result is returned to the model as an error and the run continues", async () => {
  const parameters = Type.Object({});
  const big: AgentTool<typeof parameters> = { name: "big", label: "Big", description: "Return a large result.", parameters,
    async execute() { return { content: [{ type: "text", text: "x".repeat(200) }], details: {} }; } };
  let toolResultSeen = "";
  const runner = createPiRunner({ apiKey: "offline", createTools: () => [big as unknown as AgentTool],
    stream: scriptedStream([{ toolCall: { name: "big", arguments: {} } }, { text: "recovered" }], context => {
      const last = context.messages.at(-1);
      if (last?.role === "toolResult") toolResultSeen = JSON.stringify(last.content);
    }) as never });
  const result = await runner({ prompt: "go" }, parseModel("anthropic:claude-sonnet-4-6"), { ...defaultBudget, maxToolResultChars: 100 }, async () => {});
  assert.equal(result.status, "done", result.error ?? "");
  assert.equal(result.output, "recovered");
  assert.match(toolResultSeen, /TOOL_RESULT_TOO_LARGE/);
});

test("plan model options reach the provider request", async () => {
  const seen: StreamOptions[] = [];
  const run = async (selection: ModelSelection) => {
    const runner = createPiRunner({ apiKey: "offline", stream: scriptedStream([{ text: "ok" }], (_context, options) => { seen.push(options); }) as never });
    await runner({ prompt: "go" }, selection, { ...defaultBudget }, async () => {});
  };
  await run({ provider: "anthropic", id: "claude-sonnet-4-6" });
  await run({ provider: "anthropic", id: "claude-sonnet-4-6", temperature: 0.7 });
  await run({ provider: "anthropic", id: "claude-sonnet-4-6", temperature: null });
  assert.equal(seen[0]!.temperature, 0, "temperature defaults to 0");
  assert.equal(seen[1]!.temperature, 0.7);
  assert.equal("temperature" in seen[2]!, false, "null omits the parameter");
});

test("schema 3 plans validate model options and reject older schema versions", () => {
  const plan = {
    name: "options", models: [{ provider: "anthropic", id: "claude-sonnet-4-6", thinkingLevel: "off", temperature: 0 }],
    budget: { ...defaultBudget }, trustedLocalExecution: false,
    cases: [{ id: "case", input: { prompt: "text" }, evaluator: { kind: "human", dimensions: ["clarity"] } }],
  };
  validatePlan(plan);
  validatePlan({ ...plan, models: [{ ...plan.models[0], thinkingLevel: "high", temperature: null }] });
  assert.throws(() => validatePlan({ ...plan, models: [{ ...plan.models[0], thinkingLevel: "extreme" }] }), /INVALID_THINKING_LEVEL/);
  assert.throws(() => validatePlan({ ...plan, models: [{ ...plan.models[0], temperature: 3 }] }), /INVALID_TEMPERATURE/);
  assert.throws(() => validatePlan({ ...plan, schemaVersion: 2 }), /UNSUPPORTED_PLAN_VERSION/);
  const { maxToolResultChars: _omitted, ...withoutToolLimit } = defaultBudget;
  assert.throws(() => validatePlan({ ...plan, budget: withoutToolLimit }), /INVALID_BUDGET:maxToolResultChars/);
});

test("experiment.json records the evaluated condition and fingerprints it", async () => {
  const root = await mkdtemp(join(tmpdir(), "condition-test-"));
  try {
    const plan: EvaluationPlan = {
      name: "condition", models: [{ provider: "deepseek", id: "deepseek-flash", thinkingLevel: "off", temperature: 0 }],
      budget: { ...defaultBudget }, trustedLocalExecution: true,
      cases: [{ id: "case", input: { prompt: "text" }, evaluator: { kind: "exact-match", expected: "ok" } }],
    };
    const result = await runEvaluation(plan, { outputRoot: root, runner: async () => ({ ...emptyExecution(), output: "ok" }) });
    const experiment = JSON.parse(await readFile(join(result.directory, "experiment.json"), "utf8")) as {
      fingerprint: string;
      condition: {
        git: { commit: string | null; dirty: boolean | null };
        runtimes: { node: string; python: string | null };
        packages: Record<string, string | null>;
        models: Array<Record<string, unknown>>;
        tools: Array<{ caseId: string; profile: string; toolNames: string[]; definitionsSha256: string }>;
        isolation: { mode: string; launcherSha256: string };
      };
    };
    const { condition } = experiment;
    assert.match(experiment.fingerprint, /^[a-f0-9]{64}$/);
    assert.match(condition.git.commit ?? "", /^[a-f0-9]{40}$/);
    assert.equal(condition.runtimes.node, process.version);
    assert.match(condition.runtimes.python ?? "", /^Python 3\./);
    assert.equal(condition.packages["@earendil-works/pi-agent-core"], "0.87.1");
    assert.deepEqual(condition.models[0], {
      provider: "deepseek", id: "deepseek-flash", thinkingLevel: "off", temperature: 0, api: "openai-completions",
      baseUrl: "https://api.deepseek.com", contextWindow: 1_000_000, maxTokens: 384_000, reasoning: true,
      pricesDeclared: false, metadataVerified: true,
    });
    assert.deepEqual(condition.tools[0]!.toolNames, ["read_file", "list_directory", "write_file", "execute_command"]);
    assert.match(condition.tools[0]!.definitionsSha256, /^[a-f0-9]{64}$/);
    assert.equal(condition.isolation.mode, "sandbox");
  } finally { await rm(root, { recursive: true, force: true }); }
});
