import { anthropicMessagesApi } from "@earendil-works/pi-ai/api/anthropic-messages.lazy";
import { openAICompletionsApi } from "@earendil-works/pi-ai/api/openai-completions.lazy";
import { createProvider, envApiKeyAuth, type Model, type Provider, type ThinkingLevelMap } from "@earendil-works/pi-ai";

// Load .env from the project root. Keep credentials there, never in source files or Git.
// Skip silently when the file is absent; the later MISSING_API_KEY check reports missing credentials.
export function loadCredentials(): void {
  try {
    process.loadEnvFile(new URL("../.env", import.meta.url));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      throw new Error("CREDENTIAL_FILE_FAILED");
    }
  }
}

export type CustomApi = "anthropic-messages" | "openai-completions";

/** Prices in USD per million tokens, as the provider bills them. */
export interface ModelPrices {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
}

/**
 * How a model's thinking can be controlled. "always-on" models cannot run with thinking "off"; plans
 * must use "provider-default" or an explicit level. "unknown" is used until the model is checked.
 */
export type ThinkingControl = "configurable" | "always-on" | "none" | "unknown";

/** Per-model metadata. Pi uses contextWindow to clamp output tokens and prices to compute cost. */
export interface CustomModelConfig {
  id: string;
  contextWindow: number;
  maxTokens: number;
  reasoning: boolean;
  thinking: ThinkingControl;
  /** Provider values Pi sends per thinking level, for example { off: "none" } for OpenAI reasoning_effort. */
  thinkingLevelMap?: ThinkingLevelMap;
  /** Anthropic-protocol models whose effort is sent as adaptive thinking with output_config.effort. */
  adaptiveThinking?: boolean;
  /**
   * Image input verified through this endpoint (2026-10-18 probe). Only verified models may judge visual work:
   * glm-5.3 drops images on the SuperCN relay and then describes an image it never received.
   */
  vision?: boolean;
  /**
   * Without prices, request cost stays unknown (null), never zero. Evaluations measure usage in fixed token units
   * and deliberately declare no prices (user decision, 2026-10-15): prices are set outside the model and would
   * bring the provider's pricing into the comparison.
   */
  prices: ModelPrices | null;
  /** False until the values have been checked against the provider (PLAN-004 WP7). */
  verified: boolean;
}

// Pi only sends an explicit "thinking disabled" parameter for models declared with reasoning: true, so a
// model that thinks by default must be declared that way for a plan's thinkingLevel "off" to take effect.

// Checked 2026-10-14 against https://api-docs.deepseek.com/quick_start/pricing: 1M context, 384K maximum
// output, thinking on by default. Prices change between peak and off-peak hours, so cost stays unknown and
// batches are bounded by tokens.
const deepseekFlash: CustomModelConfig = {
  id: "deepseek-flash", contextWindow: 1_000_000, maxTokens: 384_000, reasoning: true, thinking: "configurable",
  // Checked 2026-10-18 against https://api-docs.deepseek.com/guides/thinking_mode/: effort low, high or max (default
  // high); other names are silently remapped, so they are declared null and rejected by validation. Temperature has
  // no effect in thinking mode.
  thinkingLevelMap: { minimal: null, low: "low", medium: null, high: "high", xhigh: null, max: "max" }, prices: null, verified: true, vision: true
};

// Checked 2026-10-14 against https://help.aliyun.com/zh/model-studio/qwen3-8-flash: 1M context, 131,072
// maximum output, thinking supported. AliPlan bills through a token plan, so no per-token prices are declared.
// Checked 2026-10-20 against https://help.aliyun.com/zh/model-studio/deep-thinking: thinking is on by default with
// the model's full reasoning length, and its only control is a token budget; there are no effort levels. Plans
// therefore run it at "provider-default", which sends no thinking parameter; a probe on 2026-10-20 returned a thinking
// block and the right answer. Image input is documented and a screenshot probe on 2026-10-20 read the page exactly.
const qwen38Flash: CustomModelConfig = {
  id: "qwen3.8-flash", contextWindow: 1_000_000, maxTokens: 131_072, reasoning: true, thinking: "configurable", prices: null,
  verified: true, vision: true
};

// Checked 2026-10-14 against https://developers.openai.com/api/docs/models/gpt-6-luna: 1,050,000 context
// (922,000 input), 128,000 maximum output, reasoning effort none, low, medium (default), high, xhigh and max.
// Thinking "off" is sent as reasoning_effort "none"; "minimal" does not exist. Pi clamps undeclared levels, so
// every supported level is declared and validation rejects the rest. Through the SuperGPT relay the effort also
// applies when tools are present (checked 2026-10-14), although OpenAI's Chat Completions allows function calling
// only with "none". The relay's prices are not published here, and it ignores both max_tokens and
// max_completion_tokens; the runner enforces the output cap from reported usage.
const gpt6Luna: CustomModelConfig = {
  id: "gpt-6-luna", contextWindow: 1_050_000, maxTokens: 128_000, reasoning: true, thinking: "configurable",
  thinkingLevelMap: { off: "none", minimal: null, xhigh: "xhigh", max: "max" }, prices: null, verified: true, vision: true
};

// Checked 2026-10-14 against https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash: 1M context, 128K
// maximum output, and thinking that cannot be disabled (thinking.type only "enabled"). Declared without
// reasoning so Pi sends no thinking parameter; plans must say "provider-default". Served through the SuperCN relay.
// Checked 2026-10-15 against https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3: 1M context, 128K maximum
// output, thinking always on, and reasoning_effort low, high or max with default "max". Through the SuperCN relay's
// Anthropic endpoint the effort is sent as adaptive thinking with output_config.effort; a probe on 2026-10-15 showed
// the relay applies it. GLM has no off, minimal, medium or xhigh level, so those are declared null and rejected.
const glm53: CustomModelConfig = {
  id: "glm-5.3", contextWindow: 1_000_000, maxTokens: 131_072, reasoning: true, thinking: "always-on",
  thinkingLevelMap: { off: null, minimal: null, low: "low", medium: null, high: "high", xhigh: null, max: "max" }, adaptiveThinking: true,
  prices: null, verified: true
};

// Checked 2026-10-18 against https://platform.stepfun.ai/docs/en/guides/models/step-5-preview: 1M context, 64K
// maximum output, reasoning effort low, medium or high, sent as output_config.effort on the Messages API. Disabling
// thinking is not documented, so "off" is rejected. Served through the SuperCN relay.
const step5Preview: CustomModelConfig = {
  id: "step-5-preview", contextWindow: 1_000_000, maxTokens: 64_000, reasoning: true, thinking: "always-on",
  thinkingLevelMap: { off: null, minimal: null, low: "low", medium: "medium", high: "high", xhigh: null, max: null }, adaptiveThinking: true,
  prices: null, verified: true, vision: true
};

// Checked 2026-10-18 against third-party guides citing Moonshot's documentation (no official page was reachable):
// 1,048,576 context, 131,072 default maximum output, thinking always on, reasoning effort low, high or max (default
// max). Costs more than the other models. Every request carries about 2,080 input tokens that the model did not
// write ("Reply with exactly OK." costs 2,090 input tokens on both SuperCN protocols, uncached); they count toward
// token budgets.
const kimiK3: CustomModelConfig = {
  id: "kimi-k3", contextWindow: 1_048_576, maxTokens: 131_072, reasoning: true, thinking: "always-on",
  thinkingLevelMap: { off: null, minimal: null, low: "low", medium: null, high: "high", xhigh: null, max: "max" }, adaptiveThinking: true,
  prices: null, verified: true, vision: true
};

const glm53Flash: CustomModelConfig = {
  id: "glm-5.3-flash", contextWindow: 1_000_000, maxTokens: 131_072, reasoning: false, thinking: "always-on",
  prices: null, verified: true, vision: true
};

// Checked 2026-10-20 against https://mimo.mi.com/models/en-US/mimo-v2.6-flash and the Deep Thinking guide
// (https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/deep-thinking): 1M context (1,048,576),
// 128K (131,072) maximum output covering thinking and answer, text, image, video and audio input. Thinking is on by
// default and only switches on or off (thinking.type), with no effort levels or budget, so plans run both models at
// "provider-default"; in thinking mode temperature and top_p are forced to 1.0 and 0.95. Thinking must be passed
// back across tool calls; Pi does, and probes on 2026-10-20 passed usage, output cap, tool round trip and error
// classification on both protocols, and read a rendered page correctly. The token plan is billed in tokens, so no
// prices are declared.
const mimoV26Pro: CustomModelConfig = {
  id: "mimo-v2.6-pro", contextWindow: 1_048_576, maxTokens: 131_072, reasoning: true, thinking: "configurable", prices: null,
  verified: true, vision: true
};
const mimoV26Flash: CustomModelConfig = { ...mimoV26Pro, id: "mimo-v2.6-flash" };

// Conservative placeholders used until a model's metadata is checked against its provider.
function unverified(id: string): CustomModelConfig {
  return { id, contextWindow: 128_000, maxTokens: 8_192, reasoning: false, thinking: "unknown", prices: null, verified: false };
}

/** An endpoint entry: protocol, base URL, and API key environment variable. */
export interface ProviderConfig {
  /** Provider prefix used during model selection, such as provider:model-id. */
  id: string;
  name: string;
  /** Endpoint protocol used to select the API implementation. */
  api: CustomApi;
  baseUrl: string;
  /** Environment variable that stores the API key. */
  apiKeyEnv: string;
  /** Supported models and their metadata. */
  models: readonly CustomModelConfig[];
}

// Register a primary and fallback endpoint for a provider; a protocol suffix selects the fallback:
// Switch endpoints by changing the provider prefix in --model; no code change is required.
export const providerConfigs: readonly ProviderConfig[] = [
  // ---- DeepSeek: native OpenAI protocol with an Anthropic-compatible fallback ----
  {
    id: "deepseek", name: "DeepSeek", api: "openai-completions",
    baseUrl: "https://api.deepseek.com", apiKeyEnv: "DEEPSEEK_APIKEY",
    models: [unverified("deepseek-v4-pro"), deepseekFlash],
  },
  {
    id: "deepseek-anthropic", name: "DeepSeek (Anthropic)", api: "anthropic-messages",
    baseUrl: "https://api.deepseek.com/anthropic", apiKeyEnv: "DEEPSEEK_APIKEY",
    models: [unverified("deepseek-v4-pro"), unverified("deepseek-flash")],
  },
  // ---- AliPlan: Anthropic endpoint with an OpenAI-compatible fallback ----
  {
    id: "aliplan", name: "AliPlan", api: "anthropic-messages",
    baseUrl: "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic", apiKeyEnv: "ALIPLAN_APIKEY",
    models: [unverified("qwen3.8-max"), qwen38Flash, unverified("qwen3.7-max"), unverified("qwen3.7-flash")],
  },
  {
    id: "aliplan-openai", name: "AliPlan (OpenAI)", api: "openai-completions",
    baseUrl: "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", apiKeyEnv: "ALIPLAN_APIKEY",
    models: [unverified("qwen3.8-max"), unverified("qwen3.8-flash"), unverified("qwen3.7-max"), unverified("qwen3.7-flash")],
  },
  // ---- SuperCN: Anthropic endpoint with an OpenAI-compatible fallback ----
  {
    id: "supercn", name: "SuperCN", api: "anthropic-messages",
    baseUrl: "https://api.airy.work", apiKeyEnv: "SUPERCN_APIKEY",
    models: [glm53, glm53Flash, kimiK3, unverified("kimi-k2.8-preview"), unverified("MiniMax-M3.1-Flash-Preview"), step5Preview],
  },
  {
    id: "supercn-openai", name: "SuperCN (OpenAI)", api: "openai-completions",
    baseUrl: "https://api.airy.work/v1", apiKeyEnv: "SUPERCN_APIKEY",
    models: [unverified("glm-5.3"), unverified("glm-5.3-flash"), unverified("kimi-k3"), unverified("kimi-k2.8-preview"), unverified("MiniMax-M3.1-Flash-Preview")],
  },
  // ---- SuperGPT: OpenAI protocol with an Anthropic-compatible fallback ----
  {
    id: "supergpt", name: "SuperGPT", api: "openai-completions",
    baseUrl: "https://api.airy.work/v1", apiKeyEnv: "SUPERGPT_APIKEY",
    models: [unverified("gpt-6-astra"), unverified("gpt-6-sol"), gpt6Luna, unverified("gpt-5.6-sol")],
  },
  {
    id: "supergpt-anthropic", name: "SuperGPT (Anthropic)", api: "anthropic-messages",
    baseUrl: "https://api.airy.work", apiKeyEnv: "SUPERGPT_APIKEY",
    models: [unverified("gpt-6-astra"), unverified("gpt-6-sol"), unverified("gpt-6-luna"), unverified("gpt-5.6-sol")],
  },
  // ---- MiMo Plan: Anthropic endpoint with an OpenAI-compatible fallback (added 2026-10-20) ----
  // mimo-v2.5-pro has been routed to V2.6 since 2026-10-14, and its ID is retired on 2026-10-21, so it stays unverified.
  {
    id: "mimoplan", name: "MiMo Plan", api: "anthropic-messages",
    baseUrl: "https://token-plan-cn.xiaomimimo.com/anthropic", apiKeyEnv: "MIMOPLAN_APIKEY",
    models: [mimoV26Pro, mimoV26Flash, unverified("mimo-v2.5-pro")],
  },
  {
    id: "mimoplan-openai", name: "MiMo Plan (OpenAI)", api: "openai-completions",
    baseUrl: "https://token-plan-cn.xiaomimimo.com/v1", apiKeyEnv: "MIMOPLAN_APIKEY",
    models: [unverified("mimo-v2.6-pro"), unverified("mimo-v2.6-flash"), unverified("mimo-v2.5-pro")],
  },
];

/** Find a custom model's declared metadata, or undefined for built-in providers and unknown models. */
export function lookupModelConfig(provider: string, id: string): CustomModelConfig | undefined {
  return lookupProviderConfig(provider)?.models.find(model => model.id === id);
}

/** Find a custom endpoint by ID. */
export function lookupProviderConfig(id: string): ProviderConfig | undefined {
  return providerConfigs.find(config => config.id === id);
}

/** Build a Pi model from its declared metadata; evaluation output is still governed by the run budget. */
function buildModel(config: ProviderConfig, entry: CustomModelConfig): Model<CustomApi> {
  return {
    id: entry.id,
    name: entry.id,
    api: config.api,
    provider: config.id,
    baseUrl: config.baseUrl,
    reasoning: entry.reasoning,
    ...(entry.thinkingLevelMap ? { thinkingLevelMap: entry.thinkingLevelMap } : {}),
    ...(entry.adaptiveThinking ? { compat: { forceAdaptiveThinking: true } as Model<CustomApi>["compat"] } : {}),
    input: entry.vision ? ["text", "image"] : ["text"],
    // Zero prices make Pi report zero cost, which the runner records as unknown rather than free.
    cost: entry.prices ?? { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: entry.contextWindow,
    maxTokens: entry.maxTokens,
  };
}

/** Build an SDK provider for an endpoint and read its key from the configured environment variable. */
export function createCustomProvider(config: ProviderConfig): Provider<CustomApi> {
  return createProvider({
    id: config.id,
    name: config.name,
    baseUrl: config.baseUrl,
    auth: { apiKey: envApiKeyAuth(`${config.name} API key`, [config.apiKeyEnv]) },
    models: config.models.map(entry => buildModel(config, entry)),
    api: config.api === "anthropic-messages" ? anthropicMessagesApi() : openAICompletionsApi(),
  });
}

/** Return the API key environment variable for a provider, or undefined for an unknown provider. */
export function apiKeyEnvFor(provider: string): string | undefined {
  if (provider === "anthropic") return "ANTHROPIC_API_KEY";
  if (provider === "openai") return "OPENAI_API_KEY";
  return lookupProviderConfig(provider)?.apiKeyEnv;
}
