import type { ExecutionResult } from "./types.js";

// Keep credential metadata in memory only; never serialize it or use it for scoring.
const executionSecrets = new WeakMap<ExecutionResult, readonly string[]>();

/** Register secrets associated with an execution result, such as an API key, in memory only. */
export function registerSecrets(execution: ExecutionResult, secrets: readonly string[]) {
  executionSecrets.set(execution, secrets);
}

/** Create a persistable copy by redacting and truncating output without changing the in-memory object. */
export function persistedExecution(execution: ExecutionResult, maxChars: number): ExecutionResult {
  const secrets = executionSecrets.get(execution) ?? [];
  const output = redact(execution.output, secrets).slice(0, maxChars);
  return { ...execution, output };
}

/** Redact registered secrets first, then replace common credential formats. */
export function redact(text: string, secrets: readonly string[] = []): string {
  let safe = text;

  for (const secret of secrets) {
    if (secret) safe = safe.split(secret).join("[REDACTED]");
  }

  return safe
    // JSON field: "api_key": "..."
    .replace(/("(?:api[_-]?key|token|password)"\s*:\s*)"(?:\\.|[^"\\])*"/gi, '$1"[REDACTED]"')
    // HTTP authorization header: Bearer xxx
    .replace(/Bearer\s+[^\s"']+/gi, "Bearer [REDACTED]")
    // Keys with the sk- prefix
    .replace(/\bsk-[A-Za-z0-9_-]+/g, "[REDACTED]")
    // Key-value forms such as api_key=xxx or token: xxx
    .replace(/((?:api[_-]?key|token|password)\s*[=:]\s*)[^\s,;"']+/gi, "$1[REDACTED]");
}
