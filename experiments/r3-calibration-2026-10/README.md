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
