# R1 Calibration 2026-10

The difficulty calibration of the R1 shift-roster family (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). It runs every item once per model, with the same models, conditions and budget as the [R3 calibration](../r3-calibration-2026-10/README.md).

`task-library/calibration/r1-rostering` 0.1.0 has 32 generated instances, 8 per level, 4 feasible and 4 infeasible:

| Level | People | Days | Shifts × staff | Optional rules |
| --- | --- | --- | --- | --- |
| L1 | 4 | 4 | 2 × 1 | 3 |
| L2 | 5 | 5 | 2 × 1 | 4 |
| L3 | 6 | 6 | 2 × 2 | 5 |
| L4 | 7 | 7 | 3 × 1 | 6 |

The model is not told which instances are feasible. Feasible items score the fraction of rules a fully staffed roster satisfies. Infeasible items score the verdict and a solver-verified minimal conflict set, half each. Any minimal conflict set is accepted. A table of every rule subset's feasibility, computed at generation time, makes grading instant and deterministic.

```bash
npm run harness -- --plan experiments/r1-calibration-2026-10/calibration.eval.json
```

A first sequential run (`492b98b5`, stopped at 41 of 128 trials) was replaced by a fresh run with `batch.concurrency: 4`. Concurrency is not part of the fingerprint, but the harness commit had changed.


## Result (run `e4dda9c5`, 128 trials)

R1 is saturated for two of the four models: deepseek-flash scored 100% and step-5-preview 97%, glm-5.3 89% (mostly 20% format deductions), and gpt-6-luna 86%, falling only at L3. Every failed check was audited and is the model's own. R1 leaves the comparison set, and L1–L4 stay as easy anchors. Harder levels were not practical: with two people per shift and all seven rules, the exact solver produced no instance in ten minutes. See `docs/reviews/2026-10-19-task-set-v2-calibration.md`.
