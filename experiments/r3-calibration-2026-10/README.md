# R3 Calibration 2026-10

The first difficulty calibration of a generated family (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). It runs every R3 logic grid item once per model to find which levels separate models. Its results set R3's budget and choose the levels for the frozen set.

## Package

`task-library/calibration/r3-logic-grid` 0.1.0 holds 40 generated puzzles, 8 per level:

| Level | Grid | Clues per puzzle |
| --- | --- | --- |
| L1 | 4 houses × 4 attributes | 8–11 |
| L2 | 5 × 5 | 14–18 |
| L3 | 6 × 6 | 22–27 |
| L4 | 7 × 7 | 33–38 |
| L5 | 8 × 8 | 43–46 |

Every puzzle has a unique solution and a minimal clue set. The score is cell accuracy. An item is resolved only when every cell is correct.

## Conditions

Thinking runs at each model's middle level and temperature at 0. Thinking models may ignore temperature.

| Model | Label |
| --- | --- |
| `supergpt:gpt-6-luna` | gpt-6-luna-medium |
| `supercn:glm-5.3` | glm-5.3-high |
| `deepseek:deepseek-flash` | deepseek-flash-high |
| `supercn:step-5-preview` | step-5-preview-medium |

kimi-k3 is left out of the full run because it costs more (user decision, 2026-10-18). It will run on a small subset of the levels that separate models.

## Budget

The puzzle is in the prompt, so no tools are needed; the workspace is read-only and allows two tool calls. Each trial gets 100,000 tokens, 4 responses, 30 minutes, and up to 65,536 output tokens per response, because large grids may need long reasoning in one response. These are first-run values that will be set from this run. The plan also has a per-model ceiling of 2.5M tokens as a spending fuse.

## Running

```bash
npm run harness -- --plan experiments/r3-calibration-2026-10/calibration.eval.json
```

## Smoke test (2026-10-18)

Before this run, items L1-01 and L2-01 were run on luna-medium and glm-5.3-high.

- **glm-5.3 put a short explanation before correct JSON answers.** This led to the 0.5.1 recovery rule for every answer-graded package: an answer is recovered with the 20% deduction when exactly one JSON object can be found in it.
- **luna-medium sometimes returns an empty solution.** It answered `{"solution": {}}` or `{"solution": null}` in 2 of 6 harness trials. In 8 direct calls with the same prompt, it answered properly every time. Its usage shows almost all output tokens spent on reasoning and about 11 visible tokens, so the empty answer is the model's own output. This rate is watched in the calibration run.

## Runs

| Run | Plan | Commit | Levels used |
| --- | --- | --- | --- |
| `78ab1d6b` | `calibration.eval.json`, sequential | `9c39f04` | L1 and L2 (all 64 trials); stopped during L3 |
| continuation | `continuation.eval.json` (L3 to L5), `batch.concurrency: 4` | after `9b7be1e` | L3, L4 and L5 |

The first run was stopped once concurrent trials existed: sequentially, the large grids would have taken five to eight more hours. Both runs use package version 0.1.0 with identical conditions and budgets. The harness commits between them add other packages, rendering dependencies and concurrency, none of which changes what a model sees. The analysis takes L1 and L2 from the first run and L3 to L5 from the continuation.


## Completion (2026-10-19)

The continuation `f1c85624` was resumed from a worktree at its commit `e30b311` once a new deepseek key worked, and it completed 96 of 96 trials. At L5, 13 of the 24 trials of deepseek, glm and step stopped at the 65,536-token output limit of a single response. That limit binds most of these models, which goes against the rule that budgets must not stop most models, so the next R3 version should allow a longer single response; step-5-preview's own output limit is 64K.

## Hard levels (task 0.2.0, 2026-10-20)

`hard-levels.eval.json` runs L4–L6 on five models, qwen3.8-flash at its default thinking included. A single response may now hold 131,072 output tokens, up from 65,536; a model whose own output limit is lower, such as step-5-preview at 64K, stops at that limit. Each trial gets 300,000 tokens, 4 responses and 60 minutes.

```bash
npm run harness -- --plan experiments/r3-calibration-2026-10/hard-levels.eval.json
```

Run `38d352d0`: 89 of 120 trials. The supercn relay then answered with an authentication error, which at the time stopped the whole batch (now only that provider stops), so most L6 trials did not run.

| Model | L4 | L5 | L6 (2 puzzles) |
| --- | ---: | ---: | ---: |
| deepseek-flash | 100% | 100% | 100% |
| glm-5.3 | 57% | 45% | 50% |
| step-5-preview | 60% | 25% | 50% |
| gpt-6-luna | 30% | 19% | 27% |
| qwen3.8-flash | 14% | 28% | 29% |

deepseek solved every puzzle, so L4–L6 cannot place it in the target range of 30–80%. glm stopped at the 300,000-token trial budget in 8 of its 18 trials and step in 10; luna answers after 3,000–5,000 tokens.

## L5–L7 (task 0.3.0, 2026-10-20)

`l5-l7.eval.json` adds L7, eight 10-by-10 puzzles, and the two MiMo V2.6 models at their default thinking, so seven models run L5–L7 under the same conditions as before.

```bash
npm run harness -- --plan experiments/r3-calibration-2026-10/l5-l7.eval.json
```
