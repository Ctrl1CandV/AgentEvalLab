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
  /** Optional list of supported model IDs. */
  models: readonly string[];
}

// Register a primary and fallback endpoint for a provider; a protocol suffix selects the fallback:
// Switch endpoints by changing the provider prefix in --model; no code change is required.
export const providerConfigs: readonly ProviderConfig[] = [
  // ---- DeepSeek: native OpenAI protocol with an Anthropic-compatible fallback ----
  {
    id: "deepseek", name: "DeepSeek", api: "openai-completions",
    baseUrl: "https://api.deepseek.com", apiKeyEnv: "DEEPSEEK_APIKEY",
    models: ["deepseek-v4-pro", "deepseek-flash"],
  },
  {
    id: "deepseek-anthropic", name: "DeepSeek (Anthropic)", api: "anthropic-messages",
    baseUrl: "https://api.deepseek.com/anthropic", apiKeyEnv: "DEEPSEEK_APIKEY",
    models: ["deepseek-v4-pro", "deepseek-flash"],
  },
  // ---- AliPlan: Anthropic endpoint with an OpenAI-compatible fallback ----
  {
    id: "aliplan", name: "AliPlan", api: "anthropic-messages",
    baseUrl: "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic", apiKeyEnv: "ALIPLAN_APIKEY",
    models: ["qwen3.8-max", "qwen3.8-flash", "qwen3.7-max", "qwen3.7-flash"],
  },
  {
    id: "aliplan-openai", name: "AliPlan (OpenAI)", api: "openai-completions",
    baseUrl: "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", apiKeyEnv: "ALIPLAN_APIKEY",
    models: ["qwen3.8-max", "qwen3.8-flash", "qwen3.7-max", "qwen3.7-flash"],
  },
  // ---- SuperCN: Anthropic endpoint with an OpenAI-compatible fallback ----
  {
    id: "supercn", name: "SuperCN", api: "anthropic-messages",
    baseUrl: "https://api.airy.work", apiKeyEnv: "SUPERCN_APIKEY",
    models: ["glm-5.3", "glm-5.3-flash", "kimi-k3", "kimi-k2.8-preview", "MiniMax-M3.1-Flash-Preview"],
  },
  {
    id: "supercn-openai", name: "SuperCN (OpenAI)", api: "openai-completions",
    baseUrl: "https://api.airy.work/v1", apiKeyEnv: "SUPERCN_APIKEY",
    models: ["glm-5.3", "glm-5.3-flash", "kimi-k3", "kimi-k2.8-preview", "MiniMax-M3.1-Flash-Preview"],
  },
  // ---- SuperGPT: OpenAI protocol with an Anthropic-compatible fallback ----
  {
    id: "supergpt", name: "SuperGPT", api: "openai-completions",
    baseUrl: "https://api.airy.work/v1", apiKeyEnv: "SUPERGPT_APIKEY",
    models: ["gpt-6-astra", "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol"],
  },
  {
    id: "supergpt-anthropic", name: "SuperGPT (Anthropic)", api: "anthropic-messages",
    baseUrl: "https://api.airy.work", apiKeyEnv: "SUPERGPT_APIKEY",
    models: ["gpt-6-astra", "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol"],
  },
];

/** Find a custom endpoint by ID. */
export function lookupProviderConfig(id: string): ProviderConfig | undefined {
  return providerConfigs.find(config => config.id === id);
}

/** Use conservative defaults for custom models; evaluation output is governed by the run budget. */
function buildModel(config: ProviderConfig, id: string): Model<CustomApi> {
  return {
    id,
    name: id,
    api: config.api,
    provider: config.id,
    baseUrl: config.baseUrl,
    reasoning: false,
    input: ["text"],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128_000,
    maxTokens: 8_192,
  };
}

/** Build an SDK provider for an endpoint and read its key from the configured environment variable. */
export function createCustomProvider(config: ProviderConfig): Provider<CustomApi> {
  return createProvider({
    id: config.id,
    name: config.name,
    baseUrl: config.baseUrl,
    auth: { apiKey: envApiKeyAuth(`${config.name} API key`, [config.apiKeyEnv]) },
    models: config.models.map(id => buildModel(config, id)),
    api: config.api === "anthropic-messages" ? anthropicMessagesApi() : openAICompletionsApi(),
  });
}

/** Return the API key environment variable for a provider, or undefined for an unknown provider. */
export function apiKeyEnvFor(provider: string): string | undefined {
  if (provider === "anthropic") return "ANTHROPIC_API_KEY";
  if (provider === "openai") return "OPENAI_API_KEY";
  return lookupProviderConfig(provider)?.apiKeyEnv;
}
