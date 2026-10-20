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
