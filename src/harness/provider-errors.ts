import { isContextOverflow, type AssistantMessage } from "@earendil-works/pi-ai";
import type { ExecutionResult } from "../types.js";

/** Why a provider request ended with an error, after Pi's own retries were exhausted. */
export type ProviderFailure = "context_limit" | "auth" | "balance" | "rate_limit" | "server" | "network" | "other";

/** Classify a failed assistant message from its error text, status code, and Pi's overflow patterns. */
export function classifyProviderFailure(message: AssistantMessage, contextWindow: number): ProviderFailure {
  if (isContextOverflow(message, contextWindow)) return "context_limit";
  const text = (message.errorMessage ?? "").toLowerCase();
  const status = Number(/(?:^|[(\s])([45]\d\d)(?=\D|$)/.exec(text)?.[1] ?? Number.NaN);
  // Exhausted plans and quotas are billing states, not transient throttling, even when sent as 429.
  if (status === 402 || /insufficient[_ ](?:\w+[_ ])?(balance|quota|funds|credit)|exceeded your current quota|quota exceeded|quota (has been |is )?exhausted|exhausted.{0,40}quota|arrearage|account balance|billing|额度不足|余额不足|剩余额度/.test(text)) return "balance";
  if (status === 401 || status === 403 || /invalid[_ ]?api[_ ]?key|incorrect api key|unauthori[sz]ed|authentication|permission denied/.test(text)) return "auth";
  if (status === 429 || /rate limit|too many requests/.test(text)) return "rate_limit";
  if ((status >= 500 && status < 600) || /overloaded|internal server error|bad gateway|service unavailable|gateway timeout/.test(text)) return "server";
  if (/econnreset|etimedout|enotfound|econnrefused|socket hang up|fetch failed|network|connection error|timed out/.test(text)) return "network";
  return "other";
}

/** Map a provider failure onto the run outcome; only a full context window is a property of the evaluated condition. */
export function failureOutcome(failure: ProviderFailure): Pick<ExecutionResult, "failureKind" | "error"> {
  switch (failure) {
    case "context_limit": return { failureKind: "budget", error: "CONTEXT_LIMIT" };
    case "auth": return { failureKind: "infrastructure", error: "PROVIDER_AUTH" };
    case "balance": return { failureKind: "infrastructure", error: "PROVIDER_BALANCE" };
    case "rate_limit":
    case "server":
    case "network": return { failureKind: "infrastructure", error: "PROVIDER_UNAVAILABLE" };
    default: return { failureKind: "infrastructure", error: "PROVIDER_OR_RESPONSE_ERROR" };
  }
}

/** Errors after which no further request to the same provider can succeed in this batch. */
export const batchStoppingErrors: ReadonlySet<string> = new Set(["PROVIDER_AUTH", "PROVIDER_BALANCE"]);
