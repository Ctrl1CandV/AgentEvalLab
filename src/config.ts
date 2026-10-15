import type { Budget, ModelSelection } from "./types.js";
import { lookupProviderConfig } from "./providers.js";

/** Default budget shared by the CLI and programmatic callers. */
export const defaultBudget: Readonly<Budget> = Object.freeze({
  timeoutMs: 60_000, // Maximum run duration
  maxTurns: 6, // Completed assistant turns
  maxModelCalls: 6, // Dispatched model requests
  maxToolCalls: 8, // Tool execution attempts (zero is allowed)
  maxOutputTokensPerCall: 512, // Output token limit per model request
  maxOutputChars: 8192, // Cumulative output character limit
  maxToolResultChars: 100_000, // Characters in one tool result, matching the 100 KB file-read limit
});

/** Require safe integers within range; maxToolCalls may be zero. */
export function validateBudget(budget: Budget): void {
  for (const key of Object.keys(defaultBudget) as (keyof Budget)[]) {
    const minimum = key === "maxToolCalls" ? 0 : 1;
    const value = budget[key] as number;
    if (!Number.isSafeInteger(value) || value < minimum || value > 2_147_483_647) {
      throw new Error(`INVALID_BUDGET:${key}`);
    }
  }
  const trialTokens = budget.maxTrialTokens;
  if (trialTokens !== undefined && trialTokens !== null && (!Number.isSafeInteger(trialTokens) || trialTokens < 1)) {
    throw new Error("INVALID_BUDGET:maxTrialTokens");
  }
}

/** Parse a provider:id selection using a built-in catalog or a provider registered in src/providers.ts. */
export function parseModel(value: string): ModelSelection {
  const separator = value.indexOf(":");
  const provider = value.slice(0, separator);
  const id = value.slice(separator + 1);
  const builtin = provider === "anthropic" || provider === "openai";
  if ((!builtin && !lookupProviderConfig(provider)) || !/^[a-zA-Z0-9._/-]{1,120}$/.test(id)) {
    throw new Error("INVALID_MODEL");
  }
  return { provider, id };
}
