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

## Pilot models (second check, 2026-10-14)

The user chose `supergpt:gpt-6-luna` and `supercn:glm-5.3-flash` for the pilot. Their metadata was declared from provider documentation:
- [OpenAI GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna): 1,050,000 context, 128,000 maximum output, reasoning effort `none` to `max`, default `medium`.
- [Zhipu GLM-5.3-Flash](https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash): 1M context, 128K maximum output; thinking cannot be disabled.

| Check | gpt-6-luna, thinking off | gpt-6-luna, provider-default | glm-5.3-flash, provider-default |
| --- | --- | --- | --- |
| Usage reported | pass | pass | pass |
| Output cap ends the run | pass (enforced by the harness) | pass (enforced by the harness) | pass (empty answer: thinking used all 16 tokens) |
| Tool round trip | pass | pass | pass |
| Invalid key gives `PROVIDER_AUTH` | pass | pass | pass |
| Reasoning tokens | 0 | 0 to 25 | not reported (121 output tokens to answer "OK") |
| Temperature 0 accepted | yes | yes | yes |

Further findings and changes:

- **The SuperGPT relay ignores output caps.** It ignores both `max_completion_tokens` and `max_tokens`: luna returned 603 tokens with a 16-token cap. The runner now ends a run with `OUTPUT_TOKEN_LIMIT` whenever a response reports more output tokens than the cap, so every provider runs under the same per-request limit. Tokens past the cap are still billed.
- **Thinking control is now metadata.**
  - GPT-6 Luna needs `thinkingLevelMap: { off: "none" }` for thinking "off" to reach the API.
  - GLM-5.3-Flash is declared `always-on`. Validation rejects thinking "off" for it, and plans use `provider-default`, which sends no thinking parameter at all.

## Explicit reasoning effort for GPT-6 Luna (third check, 2026-10-14)

The user decided that thinking levels need not match across models; each model runs at a stated level, and reports label it, as in `gpt-6-luna-medium`. Luna therefore moves from `provider-default` to an explicit `medium`, so the label reflects what was sent rather than the relay's default.

OpenAI's model page states that "Chat Completions supports function calling only with `reasoning_effort` set to `none`", and the SuperGPT provider uses Chat Completions. Every task needs tools, so a probe sent a question that needs reasoning (the smallest n with n mod 7 = 3, n mod 11 = 5, n mod 13 = 9; the answer is 269) with and without a tool definition attached:

| Reasoning effort | Reasoning tokens, no tools / with tools | Answers |
| --- | --- | --- |
| `none` (thinking "off") | 0 / 0 | 432, 581 (wrong) |
| `medium` | 118 / 148 | 269, 269 |
| `high` | 145 / 166 | 269, 269 |

The relay accepts reasoning together with tools and applies the requested effort. `provider-check` now includes this probe as the check `thinkingWithTools` for any explicit thinking level, and `supergpt:gpt-6-luna?thinking=medium` passed all five checks.

Reading Pi's request code turned up another defect: **Pi clamps an undeclared thinking level to the nearest supported one without notice.** A plan saying `max` for luna, whose metadata then declared only `off`, would have sent `high`. Luna now declares its full range (`none`, `low`, `medium`, `high`, `xhigh`, `max`, and no `minimal`), and validation rejects any level the resolved model does not support (`THINKING_LEVEL_UNSUPPORTED`).

## Limits

Five requests per model cannot show variance, long-context behaviour, or context-overflow messages. Live context-limit classification is still unverified for both providers.
