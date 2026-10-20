# T2 Calibration 2026-10

The first run of T2, the policy-bound service desk (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). It covers eight tickets on five models, twice each, at their middle thinking levels (qwen3.8-flash at its default) and temperature 0. Each trial gets 300,000 tokens, 40 responses, 60 tool calls and 20 minutes, stated to the model.

```bash
npm run harness -- --plan experiments/t2-calibration-2026-10/calibration.eval.json
```
