/** Input for a single evaluation run. */
export interface RunInput {
  prompt: string;
  systemPrompt?: string;
}

// Bound runtime, turns, model requests, tool requests, output tokens per request, output characters,
// and the size of a single tool result.
export interface Budget {
  timeoutMs: number;
  maxTurns: number;
  maxModelCalls: number;
  maxToolCalls: number;
  maxOutputTokensPerCall: number;
  maxOutputChars: number;
  /** Characters one tool result may return; larger results become a recoverable tool error. */
  maxToolResultChars: number;
}

export type ThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max";
export const thinkingLevels: readonly ThinkingLevel[] = ["off", "minimal", "low", "medium", "high", "xhigh", "max"];

// Select a built-in provider ("anthropic" or "openai") or a custom provider registered in src/providers.ts.
// Request options are part of the evaluated condition; omitted values mean thinking "off" and temperature 0.
export interface ModelSelection {
  provider: string;
  id: string;
  thinkingLevel?: ThinkingLevel;
  /** null omits the parameter for models that reject an explicit temperature. */
  temperature?: number | null;
}

/** Resolve request options with their documented defaults. */
export function modelOptions(selection: ModelSelection): { thinkingLevel: ThinkingLevel; temperature: number | null } {
  return { thinkingLevel: selection.thinkingLevel ?? "off", temperature: selection.temperature === undefined ? 0 : selection.temperature };
}

export type InteractionClass = "candidate" | "probe";

export interface RequestUsage {
  requestId: string;
  interactionClass: InteractionClass;
  stageId?: string;
  cycleId?: string;
  status: "completed" | "error" | "incomplete";
  usageStatus: "reported" | "partial" | "missing";
  durationMs: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  cacheReadTokens: number | null;
  cacheWriteTokens: number | null;
  reasoningTokens: number | null;
  totalTokens: number | null;
  /** Null means the provider did not expose a trustworthy priced amount. */
  costUsd: number | null;
}

// Record execution outputs and process metrics.
export interface ExecutionResult {
  status: "done" | "error" | "timeout" | "budget_exceeded";
  failureKind: "model" | "infrastructure" | "budget" | null;
  output: string;
  error: string | null;
  durationMs: number;
  modelCalls: number;
  toolCalls: number;
  toolAttempts: number;
  toolIntercepts: number;
  toolExecutions: number;
  turns: number;
  reportedTokens: number | null;
  requestUsage: RequestUsage[];
  toolEvidenceBytes: number;
  toolEvidenceTruncated: boolean;
}

// Lifecycle event sink, such as an external events.jsonl writer.
export type EventSink = (
  type: string,
  counts?: Record<string, number>,
  details?: Record<string, unknown>,
) => Promise<void>;

// Run one input within budget and report lifecycle events through emit.
export type Runner<Input extends RunInput = RunInput> = (
  input: Input,
  model: ModelSelection,
  budget: Budget,
  emit: EventSink,
) => Promise<ExecutionResult>;

// Return a zeroed result for the runner to populate.
export function emptyExecution(): ExecutionResult {
  return {
    status: "done",
    failureKind: null,
    output: "",
    error: null,
    durationMs: 0,
    modelCalls: 0,
    toolCalls: 0,
    toolAttempts: 0,
    toolIntercepts: 0,
    toolExecutions: 0,
    turns: 0,
    reportedTokens: null,
    requestUsage: [],
    toolEvidenceBytes: 0,
    toolEvidenceTruncated: false,
  };
}
