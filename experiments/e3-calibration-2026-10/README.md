# E3 Calibration 2026-10

The first real-model run of E3, the long-horizon family (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). eng-005 is a five-stage maintenance task in one continuous session:

1. query filters, sorting and pagination;
2. dependencies and state transitions;
3. atomicity on rejected operations;
4. a migration with an event history;
5. standardized errors and a full check.

Each stage has a public check and one repair cycle, and private grading uses preserved snapshots.

The budget is stated to the model at the start (principle 3):

| Scope | Tokens | Responses | Tool calls | Time |
| --- | ---: | ---: | ---: | ---: |
| Whole task | 3,000,000 | 250 | 600 | 150 minutes |
| Each stage | 800,000 | 60 | 150 | 30 minutes |

Each response may hold 32,768 output tokens. Budget reminders come at 50%, 75% and 90% of what each stage started with.

Trajectory runs process their models one after another, so `trajectory-<model>.eval.json` runs one model each, and the five run side by side. `trajectory.eval.json` is the combined plan with the same conditions.

```bash
npm run harness -- --plan experiments/e3-calibration-2026-10/trajectory-deepseek-flash.eval.json
```
