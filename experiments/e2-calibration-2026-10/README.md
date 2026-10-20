# E2 Calibration 2026-10

The first run of the E2 specification-implementation family (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). Task 0.3.0 has three items: `sheet`, a spreadsheet evaluator (16 rule areas); `ledger`, an account ledger (12); and `recur`, a recurrence expander (11); each also has a README check. The four calibration models implement each item twice, at their middle thinking levels and temperature 0.

Each trial gets 800,000 tokens, 40 responses, 60 tool calls and 30 minutes, stated to the model, and four trials run at once. The grader runs the candidate on the hidden fixtures in the sandbox. The score is the fraction of rule areas whose fixtures all pass.

```bash
npm run harness -- --plan experiments/e2-calibration-2026-10/calibration.eval.json
```

## Runs

- `82f84f8a` (2026-10-18, task 0.1.0, 300,000 tokens per trial). Superseded. Both valid deepseek and glm trials stopped at the token limit after about 11 responses, so the budget was raised to 800,000; most of the spend is context resent with each request. Five trials lost their workspaces to an operator cleanup command during the run and are infrastructure failures, not model results. Details in the task's `calibration.md`.
- `044fa08d` (2026-10-19, task 0.2.0, `sheet` only, 800,000 tokens per trial). Stopped at 4 of 12 trials when the deepseek key was rejected, and superseded by task 0.3.0 rather than resumed. glm resolved `sheet` with 799,914 tokens, step reached 88% and the token limit, and luna scored 82% with 38,212 tokens.
- Task 0.3.0 (three items, two repetitions, 800,000 tokens per trial): pending the deepseek key.

The deepseek API key was rejected on 2026-10-19. `*-without-deepseek.eval.json` runs the same plan on the other three models in the meantime. deepseek follows later under the same task version and budget, and the item analysis combines the runs.

## Result (run `c2bbe2e5`, task 0.3.0, without deepseek, 18 trials)

| Item | glm-5.3 | step-5-preview | gpt-6-luna |
| --- | ---: | ---: | ---: |
| sheet | 97% (1 of 2 resolved) | 50% (1 of 2) | 82% (0 of 2) |
| ledger | 100% (2 of 2) | 100% (2 of 2) | 77% (1 of 2) |
| recur | 100% (2 of 2) | 100% (2 of 2) | 100% (2 of 2) |

- **sheet still separates the models.** Its first rule-precise implementation is the hard part.
- **ledger separates only luna.** In one trial a local variable shadowed a function, so the program crashed on six of thirteen fixtures.
- **recur is saturated** and stays as an easy anchor.
- **Every deduction is the model's own:** a crash, an output of `{}`, a reference skipped after an earlier error, `AA1` as a reference, and one step trial that exceeded the per-response output limit before writing a file.
- **Token use:** glm and step used 550,000–840,000 tokens per trial, luna 27,000–53,000.

A new deepseek key works from 2026-10-19. The `*-deepseek.eval.json` plans add deepseek under the same conditions.

## sheet and query (task 0.4.0, 2026-10-20)

`sheet-query.eval.json` runs the two items that separate the models, `sheet` and the new `query`, twice on five models, qwen3.8-flash at its default thinking included. The budget is 1,200,000 tokens per trial: at 800,000, deepseek, glm and step used nearly all of it on `sheet` alone, and `query` is the larger specification.

```bash
npm run harness -- --plan experiments/e2-calibration-2026-10/sheet-query.eval.json
```

Run `e2277944` (`sheet-query.eval.json`) showed that the 32,768-token limit on a single response was too tight for `query`. deepseek, glm and step each tried to write the whole program in one response and stopped at that limit after 36,000–44,000 tokens, in both repetitions. `query.eval.json` reruns `query` with responses of up to 131,072 tokens (each model's own output limit applies when lower) and 60 minutes per trial. The `sheet` results of `e2277944` stand: no `sheet` trial reached that limit.
