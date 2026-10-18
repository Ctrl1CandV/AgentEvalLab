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

## GLM-5.3 replaces GLM-5.3-Flash (fourth check, 2026-10-15)

After the first pilot round, the user replaced `glm-5.3-flash` with `supercn:glm-5.3`. [Zhipu's model page](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3) gives 1M context and 128K maximum output. Thinking is always on, with `reasoning_effort` `low`, `high` or `max`, and the default is `max`. The model is declared with exactly those levels; on the Anthropic protocol Pi sends them as `thinking: {type: "adaptive"}` with `output_config.effort`.

Probes on 2026-10-15 sent one easy question per configuration. Effort reached the model on both protocols:

| Configuration | Sent | Output tokens | Thinking characters |
| --- | --- | --- | --- |
| Anthropic, nothing sent | — | 274 | 657 |
| Anthropic, `low` | `output_config.effort: low` | 91 | 150 |
| Anthropic, `max` | `output_config.effort: max` | 445 | 1,023 |
| OpenAI, nothing sent | — | 304 | 640 |
| OpenAI, `low` | `reasoning_effort: low` | 82 | 147 |
| OpenAI, `max` | `reasoning_effort: max` | 320 | 670 |

Two rounds on a harder puzzle varied more between samples than between levels: `low` once answered wrongly after 1.8K output tokens and once used 11.6K. Single samples therefore cannot order the levels, but they show the parameter takes effect. A further probe confirmed that the relay returns signed thinking blocks, so Pi sends GLM's reasoning back during tool calls as genuine thinking. Zhipu requires this for interleaved thinking, and it is why each thinking token is read again on every later turn.

`npm run provider-check -- 'supercn:glm-5.3?thinking=max'` passed every check: usage reported, output cap enforced, tool round trip, `PROVIDER_AUTH` for an invalid key, and thinking with tools attached (646 thinking characters, correct answer). Because the relay reports no reasoning tokens, that last check now falls back to the length of the returned thinking text.

## Calibration models (fifth check, 2026-10-18)

The user made `deepseek:deepseek-flash`, `supercn:step-5-preview` and `supercn:kimi-k3` available for difficulty calibration. Each runs at its middle level (PLAN-005):

| Model | Source | Context / output | Levels | Middle | Sent |
| --- | --- | --- | --- | --- | --- |
| deepseek-flash | [DeepSeek thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/) | 1M / 384K | low, high, max (default high); other names silently remapped | high | `thinking: enabled`, `reasoning_effort: high` |
| step-5-preview | [StepFun docs](https://platform.stepfun.ai/docs/en/guides/models/step-5-preview) | 1M / 64K | low, medium, high | medium | `output_config.effort: medium` |
| kimi-k3 | third-party guides citing Moonshot ([reapi](https://reapi.ai/blog/kimi-k3-complete-guide), [morphllm](https://www.morphllm.com/kimi-k3)) | 1,048,576 / 131,072 | low, high, max (default max) | high | `output_config.effort: high` |

Levels a model lacks are declared null, so validation rejects them instead of letting the provider remap them silently. All three passed every `provider-check` check at their middle level, including reasoning with tools attached. kimi-k3's first usage request hit a transient network error and passed on rerun.

**kimi-k3 request overhead.** "Reply with exactly OK." costs kimi-k3 2,090 input tokens, uncached, on both SuperCN protocols. The same request costs deepseek-flash 40 and step-5-preview 31. About 2,080 tokens of injected context therefore come with every kimi request and count toward its token budgets. That is roughly 4K of a 50K reasoning budget and up to 40K of a 300K eng-001 budget over 20 requests. The budgets have at least five times headroom, so this is recorded rather than corrected; it is revisited if kimi trials hit their budgets.

## Image input (2026-10-18)

The vision-model judge of PLAN-005 WP6 needs models that actually see images. Each model received a 390x844 screenshot showing "BookLoop" on a blue background and was asked for the heading and the background colour:

| Model | Answer | Input tokens |
| --- | --- | --- |
| supergpt:gpt-6-luna | BookLoop; blue | 446 |
| supercn:step-5-preview | BookLoop; blue | 367 |
| supercn:kimi-k3 | BookLoop; blue | 2,546 |
| deepseek:deepseek-flash | BookLoop; blue | 282 |
| supercn:glm-5.3-flash | BookLoop; blue | 466 |
| supercn:glm-5.3 | "HelloWorld" on black | 187 |

glm-5.3 is a text model. The relay dropped the image without an error, and the model then described an image it never received. Models now declare `vision: true` only when this probe passed, and only those may judge visual work. An unverified judge would invent its verdicts.

## Limits

Five requests per model cannot show variance, long-context behaviour, or context-overflow messages. Live context-limit classification is still unverified for both providers.
