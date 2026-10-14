# Provider Check: Pilot Models

Date: 2026-10-14. Command: `npm run provider-check -- deepseek:deepseek-flash aliplan:qwen3.8-flash`, with thinking "off" and temperature 0. Each model received at most five small requests through the harness's Pi runner (PLAN-004 WP7). Raw results are in the ignored `runs/provider-checks/` directory and contain no credentials.

## Results

| Check | deepseek:deepseek-flash | aliplan:qwen3.8-flash |
| --- | --- | --- |
| Usage reported and non-zero | pass (14 in, 1 out) | not observed: quota exhausted |
| 16-token output cap ends the run with `OUTPUT_TOKEN_LIMIT` | pass | not observed |
| Tool call round trip (1 tool call, answer contains the tool result) | pass (2 requests, 605 tokens) | not observed |
| Invalid key classified as `PROVIDER_AUTH` | pass | pass |
| No reasoning tokens with thinking "off" | pass (0 reported) | not observed |

AliPlan returned `429 Your token-plan 1-month quota has been exhausted. The quota will reset at 10-19 16:00:00 UTC.` The `aliplan-openai` endpoint uses the same key and plan, so it is affected too. Repeat the AliPlan check after the reset, or replace the second pilot model.

## Defects found and fixed

- **Thinking "off" was not sent.** Pi sends an explicit `thinking: {type: "disabled"}` (DeepSeek and Anthropic protocols) only for models declared with `reasoning: true`. All custom models had been declared `reasoning: false`, so DeepSeek, which thinks by default, would have run with thinking on under a plan that says "off". Both pilot models are now declared from their provider documentation: 1M context, 384K and 131,072 maximum output, `reasoning: true`, and no per-token prices. DeepSeek prices change by time of day and AliPlan bills through a token plan, so cost stays unknown and batches are bounded by tokens.
- **Node's fetch ignored the proxy.** This host allows outbound traffic only through the configured proxy. Node's built-in fetch ignores `HTTPS_PROXY` unless `NODE_USE_ENV_PROXY=1` is set. Every request had therefore failed as a network error; the failure was retried and counted (2 attempts each), and the batch guard would have stopped. The `harness` and `provider-check` npm scripts now set the variable.
- **Exhausted quotas were classified as rate limiting.** The AliPlan message was classified `rate_limit`, so a batch would have stopped only after three consecutive failures. Exhausted quotas and plans now classify as `balance` (`PROVIDER_BALANCE`), which stops the batch at once.

## Limits

Five requests per model cannot show variance, long-context behaviour, or context-overflow messages. Live context-limit classification is still unverified for both providers.
