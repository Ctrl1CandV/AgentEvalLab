import { anthropicMessagesApi } from "@earendil-works/pi-ai/api/anthropic-messages.lazy";
import { openAICompletionsApi } from "@earendil-works/pi-ai/api/openai-completions.lazy";
import { createProvider, envApiKeyAuth, type Model, type Provider } from "@earendil-works/pi-ai";

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

/** Per-model metadata. Pi uses contextWindow to clamp output tokens and prices to compute cost. */
export interface CustomModelConfig {
  id: string;
  contextWindow: number;
  maxTokens: number;
  reasoning: boolean;
  /** Without prices, request cost stays unknown (null), never zero. */
  prices: ModelPrices | null;
  /** False until the values have been checked against the provider (PLAN-004 WP7). */
  verified: boolean;
}

// Conservative placeholders used until a model's metadata is checked against its provider.
function unverified(id: string): CustomModelConfig {
  return { id, contextWindow: 128_000, maxTokens: 8_192, reasoning: false, prices: null, verified: false };
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
    models: [unverified("deepseek-v4-pro"), unverified("deepseek-flash")],
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
    models: [unverified("qwen3.8-max"), unverified("qwen3.8-flash"), unverified("qwen3.7-max"), unverified("qwen3.7-flash")],
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
    models: [unverified("glm-5.3"), unverified("glm-5.3-flash"), unverified("kimi-k3"), unverified("kimi-k2.8-preview"), unverified("MiniMax-M3.1-Flash-Preview")],
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
    models: [unverified("gpt-6-astra"), unverified("gpt-6-sol"), unverified("gpt-6-luna"), unverified("gpt-5.6-sol")],
  },
  {
    id: "supergpt-anthropic", name: "SuperGPT (Anthropic)", api: "anthropic-messages",
    baseUrl: "https://api.airy.work", apiKeyEnv: "SUPERGPT_APIKEY",
    models: [unverified("gpt-6-astra"), unverified("gpt-6-sol"), unverified("gpt-6-luna"), unverified("gpt-5.6-sol")],
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
    input: ["text"],
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
