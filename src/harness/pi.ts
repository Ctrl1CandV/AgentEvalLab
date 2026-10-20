import { anthropicProvider } from "@earendil-works/pi-ai/providers/anthropic";
import { budgetFraction, budgetStatus } from "./budget-notice.js";
import { openaiProvider } from "@earendil-works/pi-ai/providers/openai";
import { Agent, type AgentEvent, type AgentTool, type StreamFn } from "@earendil-works/pi-agent-core";
import { createModels } from "@earendil-works/pi-ai";
import { createHash, randomUUID } from "node:crypto";

import { emptyExecution, modelOptions, type InteractionClass, type RequestUsage, type Runner, type ModelSelection, type RunInput } from "../types.js";
import { redact, registerSecrets } from "../privacy.js";
import { EventSinkError, guardEventSink } from "../events.js";
import { validateBudget } from "../config.js";
import { apiKeyEnvFor, createCustomProvider, lookupProviderConfig } from "../providers.js";
import { classifyProviderFailure, failureOutcome } from "./provider-errors.js";
import type { AssistantMessage } from "@earendil-works/pi-ai";

// Use SDK providers for built-in catalogs; src/providers.ts registers custom providers.
// Keep catalogs in memory; do not load credential or model files or refresh remote catalogs.
export function resolveModel(selection: ModelSelection) {
  const models = createModels();
  if (selection.provider === "anthropic") {
    models.setProvider(anthropicProvider());
  } else if (selection.provider === "openai") {
    models.setProvider(openaiProvider());
  } else {
    const config = lookupProviderConfig(selection.provider);
    if (!config) throw new Error("UNKNOWN_PROVIDER");
    models.setProvider(createCustomProvider(config));
  }
  const found = models.getModel(selection.provider, selection.id);
  if (!found) throw new Error("UNKNOWN_MODEL");
  // With "provider-default", Pi must send no thinking parameter; it only sends one for reasoning models.
  const model = selection.thinkingLevel === "provider-default" ? { ...found, reasoning: false } : found;
  return { models, model };
}

// Create a fresh tool set for each run so task state cannot leak through a shared runner.
// Tool implementations are trusted caller code, not a security sandbox.
export interface PiRunnerOptions<Input extends RunInput> {
  /** Custom streaming transport, useful for custom protocols and offline tests. */
  stream?: StreamFn;
  /** Inject an API key explicitly; by default, read the provider environment variable. */
  apiKey?: string;
  trialId?: string;
  interactionClass?: InteractionClass;
  toolEvidenceMaxBytes?: number;
  /** Provider retries per request (408/409/429/5xx and connection errors, before output streams). Default 0. */
  maxRetries?: number;
  /** Longest provider-requested retry delay to honour. */
  maxRetryDelayMs?: number;
  toolProfile?: string;
  /** The returned tools form the allowlist for this run. */
  createTools?: (input: Input) => AgentTool[];
  /** Internal state shared only by the explicit continuous trajectory session. */
  sessionState?: PiSessionState;
  /**
   * Fractions of any limit after which the model receives one budget status message (PLAN-005 WP3).
   * Absent means no reminders. The statement of the budget itself belongs to the task prompt.
   */
  budgetReminders?: readonly number[];
}

export interface PiSessionState {
  agent?: Agent;
  disposed: boolean;
  traceSequence: number;
  traceBytes: number;
  systemPrompt?: string;
  context: { stageId: string; cycleId: string } | null;
  activeEventHandler?: (event: AgentEvent) => Promise<void>;
  unsubscribe?: () => void;
}

export interface PiAgentSession {
  send(input: RunInput, budget: import("../types.js").Budget, emit: import("../types.js").EventSink,
    context: { stageId: string; cycleId: string }): Promise<import("../types.js").ExecutionResult>;
  dispose(): Promise<void>;
}

function finiteNonNegative(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function contentChars(content: unknown): RequestUsage["contentChars"] {
  if (!Array.isArray(content)) return null;
  const chars = { thinking: 0, text: 0, toolCall: 0 };
  for (const block of content as Array<Record<string, unknown> | null>) {
    if (block?.type === "thinking" && typeof block.thinking === "string") chars.thinking += block.thinking.length;
    else if (block?.type === "text" && typeof block.text === "string") chars.text += block.text.length;
    else if (block?.type === "toolCall") chars.toolCall += JSON.stringify(block.arguments ?? {}).length;
  }
  return chars;
}

/** Pi Agent runner with budget enforcement, event reporting, and usage metrics. */
export function createPiRunner<Input extends RunInput = RunInput>(
  options: PiRunnerOptions<Input> = {},
): Runner<Input> {
  return async (input, selection, budget, emit) => {
    if (options.sessionState?.disposed) throw new Error("SESSION_DISPOSED");
    validateBudget(budget);
    if (!input.prompt.trim()) throw new Error("EMPTY_PROMPT");

    const events = guardEventSink(emit);
    const start = performance.now();
    const result = emptyExecution();

    // ---- Resolve model and credentials ----
    const { models, model } = resolveModel(selection);
    const requestOptions = modelOptions(selection);
    const envKey = apiKeyEnvFor(selection.provider);
    const key = options.apiKey ?? (envKey ? process.env[envKey] : undefined);
    if (!key) throw new Error("MISSING_API_KEY");
    registerSecrets(result, [key]);
    const trialId = options.trialId ?? randomUUID();
    const interactionClass = options.interactionClass ?? "candidate";
    const maxToolEvidenceBytes = options.toolEvidenceMaxBytes ?? 1024 * 1024;
    if (!Number.isSafeInteger(maxToolEvidenceBytes) || maxToolEvidenceBytes < 1) throw new Error("INVALID_TOOL_EVIDENCE_LIMIT");
    const toolVersion = `${options.toolProfile ?? "unprofiled"}@1`;
    let traceSequence = options.sessionState?.traceSequence ?? 0;
    let traceBytes = options.sessionState?.traceBytes ?? 0;
    const traceBytesAtStart = traceBytes;
    let requestEventPending = Promise.resolve();
    const interceptedCalls = new Set<string>();
    let remindedThreshold = 0;
    const requestState: { active: { usage: RequestUsage; started: number } | null } = { active: null };
    let currentRequestId: string | null = null;

    const trace = async (eventType: string, values: Record<string, unknown>) => {
      const at = new Date().toISOString();
      const context = options.sessionState?.context;
      const event = { schemaVersion: 1, sequence: ++traceSequence, trialId, interactionClass,
        ...(context ? { stageId: context.stageId, cycleId: context.cycleId } : {}), eventType, at, ...values };
      const encoded = redact(JSON.stringify(event), [key]);
      const lineBytes = Buffer.byteLength(encoded) + 1;
      if (traceBytes + lineBytes > maxToolEvidenceBytes) {
        result.toolEvidenceTruncated = true;
        const marker = {
          schemaVersion: 1,
          sequence: traceSequence,
          trialId,
          interactionClass,
          ...(context ? { stageId: context.stageId, cycleId: context.cycleId } : {}),
          eventType: "evidence_truncated",
          at,
          toolEvidenceMaxBytes: maxToolEvidenceBytes,
          omittedEventType: eventType,
          omittedPayloadBytes: lineBytes,
          omittedPayloadSha256: createHash("sha256").update(encoded).digest("hex"),
        };
        const markerBytes = Buffer.byteLength(JSON.stringify(marker)) + 1;
        if (traceBytes + markerBytes <= maxToolEvidenceBytes) {
          await events.emit("tool_trace", { toolCalls: result.toolCalls }, marker);
          traceBytes += markerBytes;
          result.toolEvidenceBytes = traceBytes - traceBytesAtStart;
        }
        if (options.sessionState) {
          options.sessionState.traceSequence = traceSequence;
          options.sessionState.traceBytes = traceBytes;
        }
        return;
      }
      let safeEvent: Record<string, unknown>;
      try { safeEvent = JSON.parse(encoded) as Record<string, unknown>; }
      catch { safeEvent = { schemaVersion: 1, sequence: traceSequence, trialId, interactionClass, eventType, at, truncated: true }; }
      await events.emit("tool_trace", { toolCalls: result.toolCalls }, safeEvent);
      traceBytes += Buffer.byteLength(JSON.stringify(safeEvent)) + 1;
      result.toolEvidenceBytes = traceBytes - traceBytesAtStart;
      if (options.sessionState) {
        options.sessionState.traceSequence = traceSequence;
        options.sessionState.traceBytes = traceBytes;
      }
    };

    const emitRequestEvent = (type: string, usage: RequestUsage) => {
      const snapshot = { ...usage };
      requestEventPending = requestEventPending.then(async () => {
        await events.emit(type, { modelCalls: result.modelCalls }, snapshot);
      }).catch(() => { /* events.check() below rethrows the sticky sink failure */ });
    };

    const finishRequest = (usage: RequestUsage, started: number, message?: { usage?: unknown; stopReason?: string; content?: unknown }) => {
      usage.durationMs = performance.now() - started;
      usage.contentChars = contentChars(message?.content);
      if (message?.stopReason === "error") usage.failureClass = classifyProviderFailure(message as AssistantMessage, model.contextWindow);
      if (!message || message.stopReason === "error" || message.stopReason === "aborted" || message.stopReason === "deferred") {
        usage.status = message?.stopReason === "error" ? "error" : "incomplete";
        usage.usageStatus = "missing";
        usage.inputTokens = usage.outputTokens = usage.cacheReadTokens = usage.cacheWriteTokens = null;
        usage.reasoningTokens = usage.totalTokens = usage.costUsd = null;
      } else {
        usage.status = "completed";
        const raw = message.usage && typeof message.usage === "object" ? message.usage as Record<string, unknown> : {};
        const total = finiteNonNegative(raw.totalTokens);
        if (total === null || total === 0) {
          usage.usageStatus = "missing";
          usage.inputTokens = usage.outputTokens = usage.cacheReadTokens = usage.cacheWriteTokens = null;
          usage.reasoningTokens = usage.totalTokens = usage.costUsd = null;
        } else {
          usage.inputTokens = finiteNonNegative(raw.input);
          usage.outputTokens = finiteNonNegative(raw.output);
          usage.cacheReadTokens = finiteNonNegative(raw.cacheRead);
          usage.cacheWriteTokens = finiteNonNegative(raw.cacheWrite);
          usage.reasoningTokens = finiteNonNegative(raw.reasoning);
          usage.totalTokens = total;
          const cost = raw.cost && typeof raw.cost === "object" ? finiteNonNegative((raw.cost as Record<string, unknown>).total) : null;
          usage.costUsd = cost !== null && cost > 0 ? cost : null;
          usage.usageStatus = usage.inputTokens !== null && usage.outputTokens !== null && usage.cacheReadTokens !== null &&
            usage.cacheWriteTokens !== null ? "reported" : "partial";
        }
      }
      emitRequestEvent(usage.status === "completed" ? "model_request_completed" :
        usage.status === "error" ? "model_request_failed" : "model_request_incomplete", usage);
    };

    // ---- Record the first budget failure while the run is still marked done ----
    const limit = (code: string) => {
      if (result.status === "done") {
        result.status = "budget_exceeded";
        result.failureKind = "budget";
        result.error = code;
      }
    };

    // ---- Enforce output limits and reject duplicate tool names ----
    const tools = (options.createTools?.(input) ?? []).map(tool => ({
      ...tool,
      async execute(...args: Parameters<AgentTool["execute"]>) {
        const toolCallId = typeof args[0] === "string" ? args[0] : "unknown";
        const toolArgs = args[1];
        const started = performance.now();
        result.toolExecutions++;
        await trace("execution_started", { requestId: currentRequestId, toolCallId, toolName: tool.name, toolVersion, args: toolArgs });
        try {
          const output = await tool.execute(...args);
          const chars = output.content.reduce(
            (sum, block) => sum + (block.type === "text" ? block.text.length : 0),
            0,
          );
          // An oversized result is returned to the model as a recoverable tool error; the run continues.
          if (chars > budget.maxToolResultChars) throw new Error("TOOL_RESULT_TOO_LARGE");
          const content = output.content.map(block => block.type === "text" ? { type: "text", text: block.text } : { type: block.type });
          await trace("execution_returned", {
            requestId: currentRequestId,
            toolCallId,
            toolName: tool.name,
            toolVersion,
            status: "success",
            durationMs: performance.now() - started,
            result: { content, details: output.details ?? null },
          });
          return output;
        } catch (error) {
          const message = error instanceof Error ? error.message : "TOOL_FAILED";
          const errorCode = /^[A-Z][A-Z0-9_]{1,79}$/.test(message) ? message : "TOOL_FAILED";
          await trace("execution_returned", {
            requestId: currentRequestId,
            toolCallId,
            toolName: tool.name,
            toolVersion,
            status: "error",
            durationMs: performance.now() - started,
            errorCode,
          });
          throw error;
        }
      },
    }));
    const allowedTools = new Set(tools.map(tool => tool.name));
    if (allowedTools.size !== tools.length) throw new Error("DUPLICATE_TOOL");

    // ---- Assemble the agent and enforce budgets at lifecycle hooks ----
    const configuredAgent = new Agent({
      initialState: {
        model,
        thinkingLevel: requestOptions.thinkingLevel === "provider-default" ? "off" : requestOptions.thinkingLevel,
        systemPrompt: input.systemPrompt ?? "",
        tools,
      },
      toolExecution: "sequential",
      getApiKey: () => key,

      // Before each model request, stop if the run has failed or exhausted its request budget.
      prepareRequest: () => {
        if (result.status !== "done" || result.modelCalls >= budget.maxModelCalls) {
          limit("MODEL_CALL_LIMIT");
          throw new Error("BUDGET_STOP");
        }
      },

      // Send the streaming request with the plan's temperature (0 by default; null omits it).
      streamFn: (selected, context, streamOptions) => {
        if (requestState.active) finishRequest(requestState.active.usage, requestState.active.started);
        result.modelCalls++;
        const usage: RequestUsage = {
          requestId: randomUUID(),
          interactionClass,
          ...(options.sessionState?.context ? { stageId: options.sessionState.context.stageId, cycleId: options.sessionState.context.cycleId } : {}),
          status: "incomplete",
          usageStatus: "missing",
          durationMs: null,
          inputTokens: null,
          outputTokens: null,
          cacheReadTokens: null,
          cacheWriteTokens: null,
          reasoningTokens: null,
          totalTokens: null,
          costUsd: null,
          attempts: 0,
          failureClass: null,
          contentChars: null,
        };
        result.requestUsage.push(usage);
        const requestStarted = performance.now();
        requestState.active = { usage, started: requestStarted };
        currentRequestId = usage.requestId;
        emitRequestEvent("model_request_started", usage);
        const stream = options.stream ?? ((m, c, o) => models.streamSimple(m, c, o));
        try {
          return stream(selected, context, {
            ...streamOptions,
            apiKey: key,
            ...(requestOptions.temperature === null ? {} : { temperature: requestOptions.temperature }),
            // The plan states one limit for every model; a model whose own output ceiling is lower stops at that ceiling.
            maxTokens: Math.min(budget.maxOutputTokensPerCall, selected.maxTokens || budget.maxOutputTokensPerCall),
            // Pi retries retryable failures before any output streams; each HTTP attempt is counted below.
            maxRetries: options.maxRetries ?? 0,
            ...(options.maxRetryDelayMs !== undefined ? { maxRetryDelayMs: options.maxRetryDelayMs } : {}),
            fetch: (input: Parameters<typeof fetch>[0], init?: Parameters<typeof fetch>[1]) => {
              usage.attempts++;
              return fetch(input, init);
            },
          });
        } catch (error) {
          finishRequest(usage, requestStarted, { stopReason: "error" });
          requestState.active = null;
          throw error;
        }
      },

      // Before each tool call, stop if the run has failed or the budget is exhausted. Pi answers calls to
      // tools outside the profile with an error result itself and never invokes this hook for them.
      beforeToolCall: async ({ toolCall }) => {
        if (result.status !== "done" || result.toolCalls >= budget.maxToolCalls) {
          limit("TOOL_LIMIT");
          if (!interceptedCalls.has(toolCall.id)) result.toolIntercepts++;
          interceptedCalls.add(toolCall.id);
          await trace("tool_intercepted", {
            requestId: currentRequestId,
            toolCallId: toolCall.id,
            toolName: toolCall.name,
            toolVersion,
            reason: result.toolCalls >= budget.maxToolCalls ? "tool_budget" : "execution_stopped",
            args: toolCall.arguments,
          });
          return { block: true, terminate: true, reason: "TOOL_BLOCKED" };
        }
        result.toolCalls++;
        await trace("tool_authorized", { requestId: currentRequestId, toolCallId: toolCall.id, toolName: toolCall.name, toolVersion });
      },

      // Account for turns and budgets when each assistant response ends.
      finishTurn: async ({ message }) => {
        result.turns++;

        // Stop immediately when a response is truncated by the output limit, or when it exceeds the limit
        // because the endpoint ignored it: every provider then runs under the same per-request cap.
        const reportedOutput = finiteNonNegative((message.usage as { output?: unknown } | undefined)?.output);
        if (message.stopReason === "length" || (reportedOutput !== null && reportedOutput > budget.maxOutputTokensPerCall)) {
          limit("OUTPUT_TOKEN_LIMIT");
          return { action: "end" };
        }
        if (result.status !== "done") {
          return { action: "end" };
        }
        // Before another request, enforce the per-trial token cap; every reported token counts, cached input included.
        if (budget.maxTrialTokens != null && message.stopReason === "toolUse" &&
            result.requestUsage.reduce((sum, request) => sum + (request.totalTokens ?? 0), 0) > budget.maxTrialTokens) {
          limit("TRIAL_TOKEN_LIMIT");
          return { action: "end" };
        }

        // Stop if the agent requests another tool after exhausting its turn or call budget.
        if (message.stopReason === "toolUse" && result.turns >= budget.maxTurns) {
          limit("TURN_LIMIT");
          return { action: "end" };
        }
        if (message.stopReason === "toolUse" && result.modelCalls >= budget.maxModelCalls) {
          limit("MODEL_CALL_LIMIT");
          return { action: "end" };
        }
        // The run continues: send one budget status when usage has passed a new reminder threshold.
        if (message.stopReason === "toolUse" && options.budgetReminders?.length) {
          const use = { tokens: result.requestUsage.reduce((sum, request) => sum + (request.totalTokens ?? 0), 0),
            modelCalls: result.modelCalls, toolCalls: result.toolCalls, elapsedMs: performance.now() - start };
          const fraction = budgetFraction(budget, use);
          const threshold = options.budgetReminders.filter(value => value <= fraction && value > remindedThreshold).at(-1);
          if (threshold !== undefined) {
            remindedThreshold = threshold;
            const text = budgetStatus(budget, use);
            agent.steer({ role: "user", content: text, timestamp: Date.now() });
            await events.emit("budget_notice", { modelCalls: result.modelCalls, toolCalls: result.toolCalls }, { threshold, fraction, text });
          }
        }
      },
    });
    let agent = configuredAgent;
    if (options.sessionState?.agent) {
      agent = options.sessionState.agent;
      agent.streamFunction = configuredAgent.streamFunction;
      agent.getApiKey = configuredAgent.getApiKey;
      agent.beforeToolCall = configuredAgent.beforeToolCall;
      agent.afterToolCall = configuredAgent.afterToolCall;
      agent.finishTurn = configuredAgent.finishTurn;
      agent.prepareRequest = configuredAgent.prepareRequest;
      agent.prepareNextTurn = configuredAgent.prepareNextTurn;
      agent.prepareNextTurnWithContext = configuredAgent.prepareNextTurnWithContext;
      agent.state.model = model;
      agent.state.thinkingLevel = requestOptions.thinkingLevel === "provider-default" ? "off" : requestOptions.thinkingLevel;
      agent.state.tools = tools;
      if ((input.systemPrompt ?? "") !== (options.sessionState.systemPrompt ?? input.systemPrompt ?? "")) {
        throw new Error("SESSION_SYSTEM_PROMPT_CHANGED");
      }
    } else if (options.sessionState) {
      options.sessionState.agent = configuredAgent;
      options.sessionState.systemPrompt = input.systemPrompt ?? "";
    }

    // ---- Subscribe to events, report counters, and abort when cumulative output exceeds the limit ----
    const eventHandler = async (event: AgentEvent) => {
      if (event.type === "message_end" && event.message.role === "assistant") {
        if (requestState.active) {
          finishRequest(requestState.active.usage, requestState.active.started, event.message);
          requestState.active = null;
        }
        for (const block of event.message.content) {
          if (block.type !== "toolCall") continue;
          const callId = block.id;
          const allowed = allowedTools.has(block.name);
          result.toolAttempts++;
          if (!allowed) {
            result.toolIntercepts++;
            interceptedCalls.add(callId);
          }
          await trace("tool_attempted", {
            requestId: currentRequestId,
            toolCallId: callId,
            toolName: block.name,
            toolVersion,
            allowed,
            reason: allowed ? null : "unknown_tool",
            args: block.arguments,
          });
        }
      }
      if (event.type === "message_update" && event.message.role === "assistant") {
        const chars = event.message.content.reduce(
          (sum, block) => sum + (block.type === "text" ? block.text.length : 0),
          0,
        );
        if (chars > budget.maxOutputChars) {
          limit("OUTPUT_LIMIT");
          agent.abort();
        }
      }
      if (event.type === "turn_start" || event.type === "turn_end" || event.type === "tool_execution_start" || event.type === "tool_execution_end") {
        await events.emit(event.type, {
          modelCalls: result.modelCalls,
          toolCalls: result.toolCalls,
        }, options.sessionState?.context ?? undefined);
      }
    };
    let unsubscribe: () => void;
    if (options.sessionState) {
      options.sessionState.activeEventHandler = eventHandler;
      if (!options.sessionState.unsubscribe) {
        options.sessionState.unsubscribe = agent.subscribe(async event => {
          const active = options.sessionState?.activeEventHandler;
          if (active) await active(event);
        });
      }
      unsubscribe = () => {
        if (options.sessionState?.activeEventHandler === eventHandler) options.sessionState.activeEventHandler = undefined;
      };
    } else unsubscribe = agent.subscribe(eventHandler);

    // ---- Timeout uses cooperative abort; tools should honor cancellation signals ----
    const timer = setTimeout(() => {
      if (result.status === "done") {
        result.status = "timeout";
        result.failureKind = "budget";
        result.error = "TIMEOUT";
      }
      agent.abort();
    }, budget.timeoutMs);

    try {
      await agent.prompt(input.prompt);
      await requestEventPending;
      events.check();

      // ---- Summarize results ----
      const messages = agent.state.messages.filter(m => m.role === "assistant");
      const last = messages.at(-1);
      result.output = last?.content
        .filter(b => b.type === "text")
        .map(b => b.text)
        .join("") ?? "";

      // Limit the persisted output to the configured character budget.
      if (result.output.length > budget.maxOutputChars) {
        limit("OUTPUT_LIMIT");
        result.output = result.output.slice(0, budget.maxOutputChars);
      }

      // SDK error or abort messages may report synthetic zero usage; never treat it as actual usage.
      const usageIsTrustworthy = result.requestUsage.length === result.modelCalls && result.requestUsage.length > 0 &&
        result.requestUsage.every(request => request.usageStatus === "reported" && request.totalTokens !== null && request.totalTokens > 0);
      if (usageIsTrustworthy) {
        result.reportedTokens = result.requestUsage.reduce((sum, request) => sum + request.totalTokens!, 0);
      }

      // The final response itself was truncated.
      if (result.status === "done" && last?.stopReason === "length") {
        limit("OUTPUT_TOKEN_LIMIT");
      }

      // A normal run must end with stop. toolUse indicates a model failure; a provider error is classified
      // (a full context window is part of the evaluated condition, the rest are infrastructure failures).
      if (result.status === "done" && last?.stopReason !== "stop") {
        result.status = "error";
        if (last?.stopReason === "error") {
          Object.assign(result, failureOutcome(classifyProviderFailure(last, model.contextWindow)));
        } else {
          result.failureKind = last?.stopReason === "toolUse" ? "model" : "infrastructure";
          result.error = "PROVIDER_OR_RESPONSE_ERROR";
        }
      }
    } catch (error) {
      events.check();

      // Propagate event persistence failures instead of classifying them as ordinary runner errors.
      if (error instanceof EventSinkError) throw error;
      if (result.status === "done") {
        result.status = "error";
        result.failureKind = "infrastructure";
        result.error = "RUNNER_ERROR";
      }
    } finally {
      clearTimeout(timer);
      unsubscribe();
      if (requestState.active) {
        finishRequest(requestState.active.usage, requestState.active.started);
        requestState.active = null;
      }
      await requestEventPending;
      events.check();
      result.durationMs = performance.now() - start;
    }

    return result;
  };
}

export const runAgent = createPiRunner();

/** A controlled continuous Pi Agent session for one multi-stage trajectory. */
export function createPiSession(
  selection: ModelSelection,
  options: PiRunnerOptions<RunInput> = {},
): PiAgentSession {
  if (options.sessionState) throw new Error("SESSION_STATE_ALREADY_CONFIGURED");
  const sessionState: PiSessionState = {
    disposed: false,
    traceSequence: 0,
    traceBytes: 0,
    context: null,
  };
  const originalFactory = options.createTools;
  let sharedTools: AgentTool[] | undefined;
  const runner = createPiRunner<RunInput>({
    ...options,
    sessionState,
    createTools: input => sharedTools ??= originalFactory?.(input) ?? [],
  });
  let inFlight: Promise<import("../types.js").ExecutionResult> | null = null;
  return {
    async send(input, budget, emit, context) {
      if (sessionState.disposed) throw new Error("SESSION_DISPOSED");
      if (inFlight) throw new Error("SESSION_BUSY");
      sessionState.context = context;
      const operation = runner(input, selection, budget, emit);
      inFlight = operation;
      try { return await operation; }
      finally { inFlight = null; sessionState.context = null; }
    },
    async dispose() {
      if (sessionState.disposed) return;
      sessionState.disposed = true;
      if (inFlight) {
        sessionState.agent?.abort();
        await inFlight.catch(() => undefined);
      }
      sessionState.activeEventHandler = undefined;
      sessionState.unsubscribe?.();
      sessionState.unsubscribe = undefined;
      sessionState.agent = undefined;
    },
  };
}
