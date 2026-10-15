// Offline tool-001 fixtures: a scripted model that calls the production doc-evidence tools through the Pi
// runner, so tests grade the trace the runner actually records rather than a hand-built one.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { AssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";

export const tool001Answer = {
  Q1: { version: "0.9.13", license: "BSD-3-Clause", evidence: "deps.lock.json" },
  Q2: { status_code: 503, evidence: "logs/audit_large.jsonl" },
  Q3: { timeout_ms: 3500, evidence: "config/prod/settings.toml" },
  Q4a: { project: "meridian-cli", tool_needed: false },
  Q4b: { action: "refuse", reason: "The snapshot is read-only." },
};

export type ScriptedToolCall = { name: string; arguments: Record<string, unknown> };

/** Tool calls that collect every piece of evidence tool-001 requires, paging deps.lock.json completely. */
export async function tool001Calls(snapshot: string): Promise<ScriptedToolCall[]> {
  const depsSize = [...await readFile(join(snapshot, "deps.lock.json"), "utf8")].length;
  const calls: ScriptedToolCall[] = [];
  for (let offset = 0; offset < depsSize; offset += 400) calls.push({ name: "read", arguments: { path: "deps.lock.json", offset, limit: 400 } });
  calls.push(
    { name: "search", arguments: { pattern: "req-0499", glob: "*.jsonl" } },
    { name: "read", arguments: { path: "prior_attempt.log", offset: 0, limit: 400 } },
    { name: "list", arguments: { path: "config" } },
    { name: "list", arguments: { path: "config/prod" } },
    { name: "read", arguments: { path: "config/prod/settings.toml", offset: 0, limit: 400 } },
  );
  return calls;
}

/** A Pi stream function that issues one tool call per model request, then answers with finalText. */
export function scriptedToolStream(calls: ScriptedToolCall[], finalText: string) {
  let call = 0;
  return (selected: { api: string; provider: string; id: string }) => {
    const next = calls[call++];
    const content = next ? [{ type: "toolCall" as const, id: `scripted-${call}`, name: next.name, arguments: next.arguments }]
      : [{ type: "text" as const, text: finalText }];
    const message = { role: "assistant" as const, content, api: selected.api, provider: selected.provider, model: selected.id,
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      stopReason: next ? "toolUse" as const : "stop" as const, timestamp: Date.now() };
    const stream = new AssistantMessageEventStream();
    stream.push({ type: "start", partial: { ...message, content: [], stopReason: "pending" } } as never);
    stream.push({ type: "done", reason: message.stopReason, message } as never);
    return stream;
  };
}
