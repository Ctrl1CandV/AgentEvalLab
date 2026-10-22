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
| Whole task | 6,000,000 | 320 | 800 | 240 minutes |
| Each stage | 2,000,000 | 80 | 200 | 45 minutes |

Each response may hold 32,768 output tokens. Budget reminders come at 50%, 75% and 90% of what each stage started with.

Trajectory runs process their models one after another, so `trajectory-<model>.eval.json` runs one model each, and the five run side by side. `trajectory.eval.json` is the combined plan with the same conditions.

```bash
npm run harness -- --plan experiments/e3-calibration-2026-10/trajectory-deepseek-flash.eval.json
```

## Runs

- 2026-10-20, first launch, superseded. At 800,000 tokens per stage and 3,000,000 in total, deepseek passed stage 1 with 264,000 tokens, then hit the stage limit in stage 2 after 23 requests: every request resends the growing session, up to 46,000 tokens each. The limit was far too tight for a continuous five-stage session, so the other four runs were stopped early and the budget doubled to 2,000,000 per stage and 6,000,000 in total.
- 2026-10-20, second launch at 2,000,000 tokens per stage and 6,000,000 in total, eng-005 0.2.1:

  | Model | Reached | Private checks of S1–S4 | Ended |
  | --- | --- | --- | --- |
  | deepseek-flash | S5 | all passed | stage token limit in S5 after 2.06M tokens (5.5M in all); S5 was not graded |
  | qwen3.8-flash | S5 | all passed | stage token limit in S5 after 2.07M tokens (5.8M in all); S5 was not graded |
  | gpt-6-luna | S5, repair cycle | all passed; S5 failed ERRORS_DOCS | a provider error in the middle of a response (1.1M tokens in all) |
  | glm-5.3 | S4 | S1–S3 all passed | the supercn relay stopped answering (PROVIDER_UNAVAILABLE) |
  | step-5-preview | S1 | — | rate limit in S1 (PROVIDER_UNAVAILABLE) |

  Two findings changed the harness (commit `7e83e61`): a stage stopped by its budget is now graded, and a response lost to a transient provider error no longer ends the session. A third changed the task: the private checks of S1–S4 were too close to the public ones to separate any model, so eng-005 0.3.0 adds twenty hidden checks drawn from the stage briefs (see the package's `calibration.md`).

## eng-005 0.3.0 (2026-10-20)

The plans now pin eng-005 0.3.0, give the grader 300 seconds per stage, and include the two MiMo V2.6 models at their default thinking (`trajectory-mimo-v2.6-pro.eval.json`, `trajectory-mimo-v2.6-flash.eval.json`). Budgets are unchanged.

**Score.** A trajectory scores the share of the 41 private checks that pass in its last graded snapshot. Checks of stages it did not reach count as failed, so the score rewards both progress and keeping earlier stages working.


### Runs with eng-005 0.3.0 (2026-10-20)

One trajectory per model, each from `trajectory-<model>.eval.json` at commit `8113ebb`:

| Model | Score | Last graded | Ended | Tokens |
| --- | ---: | --- | --- | ---: |
| qwen3.8-flash | 41/41 (100%) | S5 | stage token limit in S5; the stopped stage was graded and passed everything | 6.05M |
| deepseek-flash | 40/41 (97.6%) | S5 | stage token limit in S5; failed only `docs.usage` | 5.99M |
| gpt-6-luna | 40/41 (97.6%) | S5 | completed; failed only `errors.store-invalid` | 0.88M |
| mimo-v2.6-flash | 35/41 (85.4%) | S4 | a response longer than the 32,768-character text limit after S4 passed everything | — |
| mimo-v2.6-pro | 17/41 (41.5%) | S2 | a single response of 131,540 characters of thinking and no output, cut off at the 32,768-token response limit | 0.68M |
| glm-5.3, step-5-preview | — | — | not run: the airy.work relay had no balance | — |

The twenty hidden checks did not separate the strong models: three of them passed every hidden check of S1–S4. E3 in this form is saturated, and the strong models' only weakness is cost. qwen and deepseek used the whole six-million-token budget; luna needed 0.9M. The next version must make the stages harder to reason about, not more detailed. New plans also allow responses of 131,072 tokens, as R3 and E2 do, so that the task budget, not one response, is what stops a model.

## eng-005 0.4.0: a sixth stage, scale (2026-10-21)

`trajectory.eval.json` now pins eng-005 0.4.0 with six stages. The whole task gets 8,000,000 tokens, 400 responses, 1,000 tool calls and five hours. Each stage gets 2,000,000 tokens, 80 responses, 200 tool calls and 45 minutes. Each response may hold 131,072 tokens and 524,288 characters, and the grader gets 15 minutes per snapshot. The suite runner splits the plan into one trajectory per model. See the package's calibration record for S6 and for the grader change that makes an untouched project score 0 (it scored 19.5% under 0.3.0).
