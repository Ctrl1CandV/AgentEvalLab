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
