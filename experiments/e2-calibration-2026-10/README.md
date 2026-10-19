# E2 Calibration 2026-10

The first run of the E2 specification-implementation family (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). It uses a single item, `sheet`, a spreadsheet evaluator with 16 rule areas and a README check. The four calibration models implement it three times each, at their middle thinking levels and temperature 0.

Each trial gets 800,000 tokens, 40 responses, 60 tool calls and 30 minutes, stated to the model, and four trials run at once. The grader runs the candidate on the hidden fixtures in the sandbox. The score is the fraction of rule areas whose fixtures all pass.

```bash
npm run harness -- --plan experiments/e2-calibration-2026-10/calibration.eval.json
```

## Runs

- `82f84f8a` (2026-10-18, task 0.1.0, 300,000 tokens per trial). Superseded. Both valid deepseek and glm trials stopped at the token limit after about 11 responses, so the budget was raised to 800,000; most of the spend is context resent with each request. Five trials lost their workspaces to an operator cleanup command during the run and are infrastructure failures, not model results. Details in the task's `calibration.md`.
- Task 0.2.0 at 800,000 tokens per trial: pending.
