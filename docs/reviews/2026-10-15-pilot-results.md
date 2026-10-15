# Pilot 2026-10: Results and Findings

Dates: 2026-10-14 to 2026-10-15. Plans: [experiments/pilot-2026-10](../../experiments/pilot-2026-10/README.md). All conditions run at temperature 0.

The pilot calibrates budgets and checks the harness, graders, and reports under real traffic. It is not a model comparison: with two or three trials per task, the intervals are too wide to rank models.

The pilot ran in two rounds:

- **Round 1:** `supergpt:gpt-6-luna-medium` and `supercn:glm-5.3-flash-default`.
- **Round 2:** after round 1, the user replaced glm-5.3-flash with `supercn:glm-5.3`. It runs at `max`, its vendor default, sent explicitly. Round 2 also counts tokens in fixed units without prices and caps them per trial and per model.

## Runs

Run directories are under `runs/` (not in Git).

| Round | Batch | Run | Commit | Trials | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Reasoning | `98f72b9f` | `b22424b` | 12/12 | Complete |
| 1 | Tool (tool-001 0.4.0) | `7326b704` | `97510b0` | 6/6 | Superseded: grader defect F1 |
| 1 | Tool (tool-001 0.4.2) | `adcd4c3a` | `9e1b9b0` | 6/6 | Complete |
| 1 | Engineering | `0256bbde` | `9e1b9b0` | 3 of 6 | Stopped to rerun with fixes F3 and F6 |
| 1 | Engineering | `dbc400ce` | `e760d31` | 2 of 6 | Stopped at the token budget |
| 2 | Reasoning | `5abe9e77` | `57caa07` | 12/12 | Complete |
| 2 | Tool | `2c7244a6` | `57caa07` | 6/6 | Complete |
| 2 | Engineering (eng-001 0.3.1) | `3b76c93a` | `57caa07` | 5 of 6 | glm-5.3's third trial not run: per-model token ceiling |

## Round 2 results

| Task | Model | Passed / decided | Model calls (median / max) | Output tokens, K | Input tokens, K (all) | Duration, s | How trials ended |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rsn-001 | luna-medium | 3/3 | 2 / 2 | 0.3 / 0.4 | 1.2 / 1.3 | 9.4 / 9.8 | done 3 |
| rsn-001 | glm-5.3-max | 3/3 | 2 / 2 | 1.0 / 1.2 | 1.5 / 1.5 | 24.8 / 26.9 | done 3 |
| rsn-002 | luna-medium | 2/3 | 2 / 2 | 0.6 / 0.8 | 1.8 / 1.8 | 12.0 / 16.6 | done 3 |
| rsn-002 | glm-5.3-max | 0/3 (3 malformed) | 2 / 2 | 3.9 / 4.9 | 2.1 / 2.2 | 65.0 / 70.8 | done 3 |
| tool-001 | luna-medium | 3/3 | 5 / 5 | 0.4 / 0.4 | 7.7 / 7.7 | 14.4 / 18.9 | done 3 |
| tool-001 | glm-5.3-max | 3/3 | 4 / 6 | 0.5 / 0.6 | 6.5 / 11.0 | 25.5 / 34.6 | done 3 |
| eng-001 | luna-medium | 2/3 (3/3 under 0.3.2) | 7 / 8 | 3.3 / 3.5 | 22.7 / 22.7 | 57.4 / 81.4 | done 3 |
| eng-001 | glm-5.3-max | 2/2 | 23 / 23 | 53.4 / 59.0 | 992.0 / 1,000.1 | 887.6 / 902.6 | TRIAL_TOKEN_LIMIT 2 |

Input counts every context token a request processed, cached or not. Whether input hits a cache is the endpoint's business, so cache reads are shown in the reports but not here.

- **glm-5.3 on rsn-002: every answer was wrapped in a Markdown fence.** The instruction says "Emit one JSON object only, without Markdown fences", so strict scoring stands, as decided for F6 of the [alignment review](2026-10-13-benchmark-alignment-review.md). As a diagnostic only, the three answers were re-scored offline with the fence removed: all three passed every content check. glm-5.3's 0/3 is a format failure, not a reasoning failure.
- **glm-5.3 on eng-001: both trials reached the 1M-token trial cap while still testing their own code.** Both were graded on their final state and passed. In each trial, one early response produced about 28K output tokens, mostly thinking (115K–135K characters per trial), over 7–8 minutes. That thinking then stays in the context, as Zhipu requires during tool calls, and is read again on every later turn. Peak context reached 60K–70K tokens, against 5K for luna. The third trial did not start, because it could have crossed the 2.3M per-model ceiling.

### Round 1 in brief

| Task | luna-medium | glm-5.3-flash-default |
| --- | --- | --- |
| rsn-001 | 1/3 | 3/3 |
| rsn-002 | 3/3 | 3/3 |
| tool-001 | 3/3 | 3/3 |
| eng-001 | 2/3 over two stopped runs | 1/2 over two stopped runs |

One glm-5.3-flash eng-001 trial passed after 35 turns, 26 minutes and 2.70M tokens; 2.46M of those were cache reads. Its other trial hit the 32,768-token per-call cap in a single thinking response and wrote nothing. glm-5.3-flash used 1.4–3 times luna's tokens on reasoning and tool tasks.

### Failures checked against the task (ABC T.10)

Every failure was traced to its evidence before it was accepted as a model error:

- **luna, rsn-001 instance A (round 1, 2 of 3).** The answer gave `{coverage, per_person_max}` as the minimal conflict set. Without availability, Alice can work, and three people at two days each cover five days. That set is therefore feasible and is not a conflict set.
- **luna, rsn-002 (round 2, 1 of 3).** The limit certificate gave 5.108 for the student formula's speed as theta approaches 90 degrees; the recomputed value is 5.6.
- **luna, eng-001 (round 1).** The script calls `sqlite3.connect(db)` before validation ends, which creates the database file even when validation then fails; the instruction forbids this.
- **luna, eng-001 (round 2, 1 of 3).** It failed 14 checks because its summary listed zero counts. This was a grader defect (F7), not a model error.
- **Superseded round-1 tool run.** Re-scored offline with grader 1.1.2: 4 of 6 pass. luna once answered Q1 "insufficient evidence", and glm-5.3-flash once fenced its JSON.

## Defects found and fixed

| ID | Defect | Effect | Fix |
| --- | --- | --- | --- |
| F1 | The tool-001 grader read tool arguments from `execution_returned`; the harness records them on `execution_started`. Self-calibration and both integration tests used hand-built traces in the grader's assumed shape. | No read could be credited: Q1 and Q3 failed in all 6 trials although the answers were correct. | Grader 1.1.1 joins returns to starts by `toolCallId`. Both tests now grade the trace the Pi runner emits (`2491191`). |
| F2 | Grader 1.1.1 accepted Q3 evidence only from a `read` of the production config. | A search that returned `config/prod/settings.toml: timeout_ms = 3500` failed, although the instruction accepts "any valid recovery path". | Grader 1.1.2 also accepts that search match (`9e1b9b0`). **Needs your confirmation.** |
| F3 | Every execution not ending `done` was graded `skipped`, which removed budget stops from pass rates. | A model that ran out of budget had its pass rate inflated, contrary to the contract ("candidate timeout is a task outcome"). | Budget, timeout and model-side stops are graded; only infrastructure failures are skipped (`8c94376`). |
| F4 | Paired-difference intervals were unbounded. | −456.9% to 390.2% with two tasks. | Clipped to ±100% (`97510b0`). |
| F5 | `task_packages.py` ignored pins in `experiments/`. | A rehash left the pilot plans stale. | Included (`e500925`). |
| F6 | Usage was one token total per trial, without a per-content breakdown. | Where glm's tokens went was invisible. | Reports give output, all input, cache reads and peak context (`a2937a9`); requests record thinking, text and tool-call characters (`e760d31`). |
| F7 | The eng-001 grader required every `by_code` count to be at least 1, which the instruction never states. | A luna submission that lists zero counts failed 14 of 22 checks; it scores 22/22 under the fix. | Grader 1.1.1 (package 0.3.2) reads a zero count as an absent code (`d9d51ed`). **Needs your confirmation.** |
| F8 | The batch token ceiling was shared by all models and could not stop a running trial. | One heavy model could use up the batch and starve the other, and a ceiling could be overshot by a whole trial. | Per-model ceilings and an optional per-trial cap, reserved before each trial starts (`5940532`). |

Round 2 ran eng-001 at version 0.3.1. Regrading only works within one task version, so its recorded verdict for the affected luna trial stays `failed`; the next run uses 0.3.2.

## Token use

Tokens are fixed units: every reported token counts once, cached input included, and no prices are used (user decision, 2026-10-15).

| Round | Model | Output | Input (all) | Total |
| --- | --- | --- | --- | --- |
| 1 | gpt-6-luna-medium | 21K | 172K | 193K |
| 1 | glm-5.3-flash-default | 149K | 2,699K | 2,849K |
| 2 | gpt-6-luna-medium | 14K | 99K | 113K |
| 2 | glm-5.3-max | 124K | 2,019K | 2,143K |

Round-1 totals include superseded runs and the recorded requests of stopped trials. On eng-001, glm-5.3-max generated about 16 times luna's output tokens and processed about 44 times its input.

## Why glm uses so many more tokens

Taking one eng-001 trial of each model:

1. **Thinking volume (model).** glm-5.3-max produced 53K–59K output tokens, mostly thinking, against 3.3K–3.5K for luna-medium at `medium`.
2. **Thinking kept in the context (vendor protocol).** Zhipu requires that reasoning be returned with tool results, so every thinking token is read again on each later turn. luna's reasoning is not returned through Chat Completions. In round 1, about 1.47M of glm-5.3-flash's 2.46M cache reads were resent thinking.
3. **More turns (model).** 22–35 turns against 6–9, mostly self-testing and rewriting whole files. eng-001 offers no edit tool, so each fix rewrites the file into the context.
4. **Multiplication.** Input grows roughly as turns times context size, so a 16-fold difference in output becomes a 44-fold difference in input.

The harness follows each vendor's documented protocol and applies identical budgets. The difference is therefore part of each model's evaluated cost, not a harness artefact. The protocol asymmetry in point 2 is recorded for later harness comparisons.

## Budget recommendations for the first frozen set

Budgets stay identical for all models, because they are part of the evaluated condition. The figures are about twice the largest observation and remain provisional.

| Task | Model calls | Tool calls | Timeout | Tokens per trial | Basis |
| --- | --- | --- | --- | --- | --- |
| rsn-001, rsn-002 | 6 | 6 | 5 min | 50K | max 3 calls, 2 tool calls, 9K tokens, 86 s |
| tool-001 | 15 | 20 | 5 min | 50K | max 6 calls, 9 tool calls, 13K tokens, 41 s |
| eng-001 | 60 | 80 | 45 min | see decision 2 | luna: 9 calls, 60K tokens; glm-5.3-max: capped at 1M after 23 calls and 15 minutes, still passing |

## Decisions for the user

1. **Grader changes F2 (tool-001 Q3 search evidence) and F7 (eng-001 zero counts).** Both make a grader accept an output that the instruction allows. The alternative is to keep each rule and state it in the instruction.
2. **glm-5.3's level for the comparison, and the eng-001 trial cap.** At `max`, glm-5.3 needs more than 1M tokens per eng-001 trial, though both capped trials passed. The options:
   - keep `max` with a 1M cap, so the cap is part of the condition and binds;
   - raise the cap to about 2M, which costs about 2M tokens per trial;
   - run glm-5.3 at `high`.
3. **Format diagnostic.** Should reports also show, for answer-graded tasks, whether a malformed answer's content would have passed? This is like Aider's well-formed rate: strict scores stay official, and format failures become distinguishable from wrong answers. It was 3 of 3 glm-5.3 rsn-002 trials in round 2.
4. **Per-call output cap (32,768).** glm-5.3-max's largest responses reached 28.7K, close to the cap; glm-5.3-flash once hit it.
5. **eng-005 cost.** At round-2 rates, a five-stage trajectory would cost roughly 0.15–0.3M tokens for luna and 5M or more for glm-5.3-max. This is an extrapolation, not a measurement.
