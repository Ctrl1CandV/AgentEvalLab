// Live provider check for PLAN-004 WP7. Sends at most five small requests per model through the
// harness's own Pi runner and reports usage, output-cap, tool round-trip and error classification.
// Usage: npm run provider-check -- provider:model[?thinking=off&temperature=0|omit] [...]
// thinking accepts a plan thinking level (default "off"); temperature "omit" sends no temperature.
// Credentials come from .env; no key is printed or written.
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { Type } from "typebox";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { defaultBudget, parseModel } from "../src/config.js";
import { createPiRunner } from "../src/harness/pi.js";
import { loadCredentials } from "../src/providers.js";
import { thinkingLevels, type Budget, type ExecutionResult, type ModelSelection, type PlanThinkingLevel } from "../src/types.js";

const checkBudget: Budget = { ...defaultBudget, timeoutMs: 90_000, maxTurns: 3, maxModelCalls: 3, maxToolCalls: 1, maxOutputTokensPerCall: 256 };

function secretNumberTool(): AgentTool {
  const parameters = Type.Object({});
  const tool: AgentTool<typeof parameters> = {
    name: "get_secret_number", label: "Get secret number", description: "Return the secret number for this check.", parameters,
    async execute() { return { content: [{ type: "text", text: JSON.stringify({ value: 7310 }) }], details: {} }; },
  };
  return tool as unknown as AgentTool;
}

function summary(execution: ExecutionResult) {
  return {
    status: execution.status,
    error: execution.error,
    output: execution.output.slice(0, 120),
    modelCalls: execution.modelCalls,
    toolCalls: execution.toolCalls,
    requests: execution.requestUsage.map(request => ({
      status: request.status, usageStatus: request.usageStatus, inputTokens: request.inputTokens, outputTokens: request.outputTokens,
      reasoningTokens: request.reasoningTokens, totalTokens: request.totalTokens, attempts: request.attempts, failureClass: request.failureClass,
    })),
  };
}

async function check(selection: ModelSelection) {
  const run = (prompt: string, budget: Budget, options: { tools?: boolean; apiKey?: string } = {}) =>
    createPiRunner({ ...(options.apiKey ? { apiKey: options.apiKey } : {}), maxRetries: 1, createTools: () => options.tools ? [secretNumberTool()] : [] })(
      { prompt }, selection, budget, async () => {});
  const usage = await run("Reply with exactly the word OK and nothing else.", checkBudget);
  const cap = await run("Write the integers from 1 to 300, separated by single spaces.", { ...checkBudget, maxModelCalls: 1, maxOutputTokensPerCall: 16 });
  const tool = await run("Call the get_secret_number tool once, then reply with only the number it returned.", checkBudget, { tools: true });
  const auth = await run("Reply with OK.", { ...checkBudget, maxModelCalls: 1 }, { apiKey: "invalid-provider-check-key" });
  const usageRequest = usage.requestUsage[0];
  return {
    model: `${selection.provider}:${selection.id}`,
    thinkingLevel: selection.thinkingLevel,
    temperature: selection.temperature,
    checks: {
      usageReported: usage.status === "done" && usageRequest?.usageStatus === "reported" && (usageRequest.totalTokens ?? 0) > 0,
      outputCapEnforced: cap.status === "budget_exceeded" && cap.error === "OUTPUT_TOKEN_LIMIT",
      toolRoundTrip: tool.status === "done" && tool.toolCalls === 1 && tool.output.includes("7310"),
      authErrorClassified: auth.status === "error" && auth.error === "PROVIDER_AUTH",
      // With thinking "off" a model should spend no reasoning tokens; null means the provider did not report the field.
      ...(selection.thinkingLevel === "off" ? {
        thinkingOff: [usage, tool].flatMap(result => result.requestUsage).every(request => request.reasoningTokens === null || request.reasoningTokens === 0),
      } : {}),
    },
    reasoningTokensObserved: [usage, tool].flatMap(result => result.requestUsage).map(request => request.reasoningTokens),
    details: { usage: summary(usage), outputCap: summary(cap), toolRoundTrip: summary(tool), invalidKey: summary(auth) },
  };
}

async function main() {
  const models = process.argv.slice(2).map((value): ModelSelection => {
    const [spec, query = ""] = value.split("?", 2);
    const options = new URLSearchParams(query);
    const thinkingLevel = (options.get("thinking") ?? "off") as PlanThinkingLevel;
    if (!thinkingLevels.includes(thinkingLevel)) throw new Error("INVALID_THINKING_LEVEL");
    const temperatureOption = options.get("temperature") ?? "0";
    const temperature = temperatureOption === "omit" ? null : Number(temperatureOption);
    if (temperature !== null && !Number.isFinite(temperature)) throw new Error("INVALID_TEMPERATURE");
    return { ...parseModel(spec!), thinkingLevel, temperature };
  });
  if (!models.length) throw new Error("MODEL_REQUIRED");
  loadCredentials();
  const results = [];
  for (const model of models) results.push(await check(model));
  const directory = join("runs", "provider-checks");
  await mkdir(directory, { recursive: true });
  const path = join(directory, `provider-check-${new Date().toISOString().replace(/[:.]/g, "-")}.json`);
  await writeFile(path, JSON.stringify({ checkedAt: new Date().toISOString(), results }, null, 2));
  console.log(JSON.stringify({ path, results: results.map(result => ({ model: result.model, checks: result.checks })) }, null, 2));
  if (results.some(result => Object.values(result.checks).some(passed => !passed))) process.exitCode = 1;
}

main().catch(error => {
  console.error(`PROVIDER_CHECK_FAILED: ${error instanceof Error && /^[A-Z_:]+$/.test(error.message) ? error.message : "UNCLASSIFIED_ERROR"}`);
  process.exitCode = 1;
});
