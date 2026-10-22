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

## T2 0.2.0 (2026-10-20)

`v0.2.eval.json` runs the twelve tickets of T2 0.2.0, whose policy rules interact (see the package's `calibration.md`), on seven models twice each: the five calibration models and the two MiMo V2.6 models at their default thinking. Budgets are those of the first run.

```bash
npm run harness -- --plan experiments/t2-calibration-2026-10/v0.2.eval.json
```

## T2 0.3.0: optimisation tickets (2026-10-21)

`v0.3.eval.json` runs the twelve optimisation tickets (levels S, M and L) once each, with 600,000 tokens, 80 responses and 120 tool calls per trial, stated to the model. Each response may hold 131,072 output tokens and 524,288 characters. The 0.2.0 tickets stay in the package as anchors and are not in the family score.

In the first suite run (`runs/suites/20261021-120039-dev-fe3b`, 0.2.0 with the response limits raised), deepseek-flash scored 100% and qwen3.8-flash 96.7%, two tickets losing only the format deduction.

Run `runs/suites/20261021-124022-dev-1249` (dev suite, commit `2b02ac4`), the twelve optimisation tickets once per model. Scores are under grader 1.1.1 after the regrade:

| Model | Score | Tickets resolved | At the optimum | Median tokens | Budget stops |
| --- | ---: | ---: | ---: | ---: | ---: |
| deepseek-flash | 95.2% | 10/12 | 11/12 | 167k | 1 |
| qwen3.8-flash | 100% | 12/12 | 12/12 | 222k | 0 |
| mimo-v2.6-flash | 78.6% | 8/12 | 9 of 10 compliant | 340k | 3 |

Every remaining deduction was audited and is the model's own:

- deepseek's `om2` is compliant but 7.3% above the optimum. It gave credit for two cast-iron teapots where sending one from stock was cheaper. An enumeration of every option confirms the optimum of 183.91.
- deepseek and mimo stopped at the token budget on `ol4` after making every unit good at the optimum, so they gave no reply.
- mimo planned `os4` without running a command, looped one sentence on `os2` until a response passed 524,288 characters, and stopped at the budget on `om4`, 4.5% above the optimum.

qwen and deepseek wrote small solvers for most tickets. **Optimisation at this size did not harden T2 for them.**
