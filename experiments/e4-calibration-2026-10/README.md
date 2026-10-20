# E4 Calibration 2026-10

The first run of the E4 command-line family (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). Task 0.1.0 has four items:

- `perf`: make a slow report fast without changing its output;
- `migrate`: write and run a SQLite schema migration;
- `bisect`: find and undo a regression in a Git history;
- `build`: repair a C project's build and bugs.

The calibration models solve each item twice, at their middle thinking levels and temperature 0.

Each trial gets 500,000 tokens, 60 responses, 100 tool calls and 30 minutes, stated to the model, and four trials run at once. The grader runs the hidden checks in the sandbox; the score is the fraction of checks passed.

```bash
npm run harness -- --plan experiments/e4-calibration-2026-10/calibration.eval.json
```

The deepseek API key was rejected on 2026-10-19. `calibration-without-deepseek.eval.json` runs the same plan on the other three models in the meantime. deepseek follows later under the same task version and budget.

## Result (run `fbdcfb07`, without deepseek, 24 trials)

E4 0.1.0 is saturated. gpt-6-luna, glm-5.3 and step-5-preview passed every check of every item in both repetitions. They differed only in cost: luna needed 16,000–50,000 tokens per trial, and glm and step 100,000–500,000, twice reaching the 500,000-token limit just as they finished. The items stay as easy anchors and an end-to-end check of the sandbox. Harder command-line work needs longer, compound tasks; see `docs/reviews/2026-10-19-task-set-v2-calibration.md`.

A new deepseek key works from 2026-10-19. The `*-deepseek.eval.json` plans add deepseek under the same conditions.

## Compound items (task 0.2.0, 2026-10-20)

`compound.eval.json` runs the three compound items, `stockroom`, `pipeline` and `recover`, twice on five models, qwen3.8-flash at its default thinking included. Each trial gets 800,000 tokens, 100 responses, 150 tool calls and 60 minutes, stated to the model. The null-agent baseline scores 0 on every item.

```bash
npm run harness -- --plan experiments/e4-calibration-2026-10/compound.eval.json
```

Run `c95f78c8`: 20 of 30 trials, before the airy.work relays ran out of balance (at the time this stopped every model). Every graded trial of every model passed every check of `stockroom`, `pipeline` and `recover`. Several stopped at the 800,000-token budget after they had already repaired everything. gpt-6-luna needed 18 responses for the six stockroom faults. The compound items are saturated as well.

## codec (task 0.3.0, 2026-10-20)

`codec.eval.json` runs the reverse-engineering item twice on seven models: the five calibration models and the two MiMo V2.6 models at their default thinking. Budgets are those of the compound run, except that a single response may hold 131,072 output tokens, as in R3 and E2 (clamped to each model's own limit). From now on only the task budget, not one response, should stop a model.

```bash
npm run harness -- --plan experiments/e4-calibration-2026-10/codec.eval.json
```

Run `627cdf83` (task 0.3.0, codec):

| Model | Trials | Checks passed |
| --- | --- | --- |
| deepseek-flash | 1 (the other: no balance) | 11/11 |
| qwen3.8-flash | 2 | 11/11, 11/11 |
| mimo-v2.6-flash | 2 | 11/11, 8/11 (missed `timestamps`, `multi-day`, `restore` at the token budget) |
| mimo-v2.6-pro | 2 | 0/11, 0/11: stopped by the 32,768-character text limit of a single response |
| glm-5.3, step-5-preview, gpt-6-luna | — | not run: the airy.work relay had no balance |

Recovering a format from bytecode does not separate the strong models either: deepseek, qwen and mimo-flash decoded every hidden group in 19–34 responses. mimo-v2.6-pro writes its reasoning out as text as well as in its thinking, so the per-response text limit stopped it in both trials. That limit is a safety guard, not the task budget, so plans from now on allow 524,288 characters of text per response.

## speedup (task 0.4.0, 2026-10-20)

`speedup.eval.json` runs the speedup item twice on seven models with the codec run's budgets. A single response may hold 524,288 characters of text, and the grader has 15 minutes, since the timing runs take up to three minutes.

```bash
npm run harness -- --plan experiments/e4-calibration-2026-10/speedup.eval.json
```
