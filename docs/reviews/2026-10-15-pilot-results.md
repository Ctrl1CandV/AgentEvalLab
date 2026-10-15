# Pilot 2026-10: Results and Findings

Dates: 2026-10-14 to 2026-10-15. Plans: [experiments/pilot-2026-10](../../experiments/pilot-2026-10/README.md). Models: `supergpt:gpt-6-luna-medium` (reasoning effort `medium`) and `supercn:glm-5.3-flash-default` (thinking always on), both at temperature 0.

The pilot calibrates budgets and checks the harness, graders, and reports under real traffic. It is not a model comparison: with one to three trials per task, the intervals are too wide to rank models.

## Runs

Run directories are under `runs/` (not in Git).

| Batch | Run | Commit | Trials | Status |
| --- | --- | --- | --- | --- |
| Reasoning (rsn-001, rsn-002) | `98f72b9f` | `b22424b` | 12/12 | Complete; kept |
| Tool (tool-001 0.4.0) | `7326b704` | `97510b0` | 6/6 | Superseded: grader defect (F1) |
| Tool (tool-001 0.4.2) | `adcd4c3a` | `9e1b9b0` | 6/6 | Complete; kept |
| Engineering (eng-001) | `0256bbde` | `9e1b9b0` | 3 of 6 | Stopped to rerun with the grading fix (F3) and content counts (F6) |
| Engineering (eng-001) | `dbc400ce` | `e760d31` | 2 of 6 | Stopped at the token budget (see "Token use") |

Report files of all five runs were rebuilt with the final report code (`5800d10`); trial records and score runs are unchanged.

## Results

| Task | Model | Passed / decided | Model calls (median / max) | Tool calls | Tokens per trial, thousands (median / max) | Duration, s (median / max) |
| --- | --- | --- | --- | --- | --- | --- |
| rsn-001 | luna-medium | 1/3 | 2 / 2 | 2 / 2 | 1.5 / 1.7 | 6.7 / 6.9 |
| rsn-001 | glm-default | 3/3 | 3 / 3 | 2 / 2 | 3.9 / 4.7 | 28.7 / 42.6 |
| rsn-002 | luna-medium | 3/3 | 2 / 2 | 1 / 1 | 2.7 / 2.7 | 11.6 / 12.6 |
| rsn-002 | glm-default | 3/3 | 2 / 2 | 1 / 2 | 8.0 / 9.1 | 85.5 / 85.9 |
| tool-001 | luna-medium | 3/3 | 5 / 5 | 8 / 8 | 8.1 / 8.8 | 10.9 / 16.1 |
| tool-001 | glm-default | 3/3 | 5 / 6 | 8 / 8 | 11.2 / 12.7 | 39.9 / 40.8 |
| eng-001 | luna-medium | 1/1 | 9 | 8 | 45.5 | 89.7 |
| eng-001 | glm-default | 1/1 | 35 | 38 | 2,701.2 | 1,584.5 |

The stopped engineering run `0256bbde` adds three observations under the same task and model conditions. luna-medium passed once (24K tokens, 38 s) and failed once (60K tokens, 75 s). glm-default stopped with `OUTPUT_TOKEN_LIMIT` after 4 calls and wrote no file; that run's code skipped grading, but under the current rule (F3) it would be graded and fail.

All rsn-002 trials leave two non-critical human-review checks pending (explanation quality, formula equivalence) by design; the verdict rests on the critical checks.

### Failures checked against the task (ABC T.10)

Every failure was traced to its evidence before being accepted as a model error:

- **luna, rsn-001 instance A (2 of 3).** The answer gave `{coverage, per_person_max}` as the minimal conflict set. Without availability, Alice can work, and three people at two days each cover five days, so that set is feasible and is not a conflict set. The reference set of all three constraints is correct.
- **luna, eng-001 (run `0256bbde`).** Check `case_mixed_apply_all_or_nothing` failed with `database_presence_mismatch`. The script calls `sqlite3.connect(db)` to look for uniqueness conflicts before validation ends, which creates the database file even when validation then fails. The instruction forbids creating or modifying the database when any record has an error.
- **Superseded tool run `7326b704`.** Re-scored offline with grader 1.1.2: 4 of 6 pass. luna answered Q1 "insufficient evidence" once, and glm wrapped its JSON in a Markdown fence once, against "Emit JSON only".

## Defects found and fixed

| ID | Defect | Effect | Fix |
| --- | --- | --- | --- |
| F1 | The tool-001 grader read tool arguments from `execution_returned` events, but the harness records them on `execution_started` (unchanged since the first commit). Self-calibration and both integration tests built traces by hand in the grader's assumed shape. | No read could be credited: Q1 and Q3 failed in all 6 trials although the answers were correct. | Grader 1.1.1 joins returns to starts by `toolCallId`; both tests now grade the trace the Pi runner emits (`2491191`). |
| F2 | Grader 1.1.1 accepted Q3 evidence only from a `read` of the production config. One trial searched `config/*` and got `config/prod/settings.toml: timeout_ms = 3500` from the actual file. | A valid recovery path failed, although the instruction accepts "any valid recovery path". | Grader 1.1.2 also accepts a search match on the production file (`9e1b9b0`). **Needs your confirmation.** |
| F3 | Every execution not ending `done` was graded `skipped`, and pass rates count only passed and failed trials. | Budget stops and timeouts left the denominator, inflating the pass rate of a model that runs out of budget. The contract already said a candidate timeout is a task outcome. | Budget, timeout and model-side stops are graded on their final state and count; only infrastructure failures are skipped (`8c94376`). |
| F4 | Paired-difference intervals were not bounded. | With two tasks: −456.9% to 390.2%. | Clipped to ±100% (`97510b0`). |
| F5 | `task_packages.py` checked and refreshed pins only in `examples/`. | A rehash left the pilot plans with stale pins. | Experiment plans included (`e500925`). |
| F6 | Reports gave one token total per trial, and responses were not broken down by content. | 91% of glm's 2.70M engineering tokens were cache reads; whether its long responses were thinking or truncated tool calls was invisible. | Usage tables split uncached input, cache reads and output (`5800d10`); each request records thinking, text and tool-call characters (`e760d31`). |

## Model behaviour that affects budgets

**glm-5.3-flash thinks at great length on engineering work.** In the completed trial, request 4 produced 32,042 output tokens over 9 minutes, of which 129,315 characters were thinking, 166 text and 2,069 tool-call arguments. In the stopped run, a similar response reached the 32,768-token per-call cap and the trial ended with nothing written. The trial that passed then took 35 turns over 26 minutes (the timeout is 30), testing its own script thoroughly. Each turn resends the whole context (107K tokens by the end), which the relay serves from cache:

| glm eng-001 trial | Uncached input | Cache reads | Output | Total |
| --- | --- | --- | --- | --- |
| Tokens | 153K | 2,456K | 92K | 2,701K |

On reasoning and tool tasks, glm used 1.4–3 times luna's tokens and 4–7 times its wall-clock time.

## Token use

| Model | Total | Uncached input | Cache reads | Output |
| --- | --- | --- | --- | --- |
| gpt-6-luna | 193K | 88K | 84K | 21K |
| glm-5.3-flash | 2,849K | 182K | 2,517K | 149K |

Totals include superseded runs and the recorded requests of the two stopped trials. One glm request was cut off mid-response when run `0256bbde` was stopped; its usage is unknown (up to about 35K tokens). The engineering batch was stopped during glm's second trial: after 2.75M tokens in the batch, another trial of the same size would have taken glm well past the approved budget of about 3M tokens per model. The batch ceiling (3.5M) only stops new trials from starting and does not cut off a running one.

## Budget recommendations for the first frozen set

Budgets stay identical for all models, because they are part of the evaluated condition. The figures are about twice the largest observation and remain provisional where trials are few.

| Task | Model calls | Tool calls | Timeout | Output tokens per call | Basis |
| --- | --- | --- | --- | --- | --- |
| rsn-001, rsn-002 | 6 | 6 | 5 min | 32,768 | max 3 calls, 2 tool calls, 86 s |
| tool-001 | 15 | 20 | 5 min | 32,768 | max 6 calls, 8 tool calls, 41 s |
| eng-001 | 70 | 80 | 60 min | see decision 3 | glm: 35 calls, 38 tool calls, 26 min in its one completed trial |

## Decisions for the user

1. **Accept the tool-001 Q3 change (F2)?** The alternative is to keep requiring a `read` and say so explicitly in the instruction.
2. **More glm engineering trials?** Each costs about 2.7M tokens, 91% of them cache reads. Whether that is affordable depends on how SuperCN bills cache reads, which is visible in the relay console. Two to three more glm trials are needed before eng-001's budget can be frozen. They need a new run: `--resume` refuses run `dbc400ce`, because the fingerprint includes the commit, which has changed since.
3. **Per-call output cap for eng-001.** glm's thinking once hit 32,768 tokens in one response. Raising the cap to 65,536 (glm's documented maximum is 131,072) gives long thinking room but raises cost. Keeping it makes long thinking a failure under the condition.
4. **Should batch ceilings count cache reads at full weight?** Counting them overstates cost by up to about 10 times for long glm runs. Weighting them needs the relay's cache price.
5. **eng-005 cost.** Five stages in one continuous session suggest roughly 0.3–0.5M tokens per luna trajectory and possibly 10M or more per glm trajectory. This is an extrapolation from one engineering trial each, not a measurement.
