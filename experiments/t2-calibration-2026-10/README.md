# T2 Calibration 2026-10

The first run of T2, the policy-bound service desk (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). It covers eight tickets on five models, twice each, at their middle thinking levels (qwen3.8-flash at its default) and temperature 0. Each trial gets 300,000 tokens, 40 responses, 60 tool calls and 20 minutes, stated to the model.

```bash
npm run harness -- --plan experiments/t2-calibration-2026-10/calibration.eval.json
```

## Runs

- 2026-10-20, `runs/5c62eab6-43ce-42c2-97d2-e75301151b6d`: 63 of 80 trials. The supercn relay then answered with an authentication error, and the batch stopped every model (since then, such a stop is limited to its provider). Four trials were infrastructure failures.
  - Graded first with grader 1.0.0, every model but luna lost the 20% format deduction on every ticket, for explaining its handling before the JSON reply, which POLICY.md allows. Grader 1.0.1 fixes that; the 59 graded trials were regraded.
  - After the regrade: deepseek, glm and step 100% on every ticket, qwen 97% (one format slip), luna 58% (its own policy errors: a book returned outside its 14-day window, a book return declined inside it, a missed compensation at exactly three days late, an exchange without its credit, and a reply that contradicts its actions).
  - T2 0.1.0 is therefore saturated for four of the five models and is not used for comparison; 0.2.0 replaces it.
