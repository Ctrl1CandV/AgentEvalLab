# Budget Pilot 2026-10: Results

Date: 2026-10-16. Plans: [experiments/budget-pilot-2026-10](../../experiments/budget-pilot-2026-10/README.md). Models: `supergpt:gpt-6-luna-medium` and `supercn:glm-5.3-high`, at temperature 0, with 3 repetitions. The pilot checks the PLAN-005 mechanics (WP2, WP3) on the current tasks; it does not measure difficulty.

## Runs

| Batch | Run | Commit | Trials |
| --- | --- | --- | --- |
| Reasoning (rsn-001, rsn-002 0.5.0) | `487bfcee` | `68e34c4` | 12/12 |
| Tool (tool-001 0.5.0) | `2961df25` | `68e34c4` | 6/6 |
| Engineering (eng-001 0.3.2) | `0be84fe0` | `0e9047a` | 6/6 |

The first engineering attempt was refused with `WORKTREE_DIRTY`, because a document was being edited while the batches ran in sequence. The guard worked and no request was sent. Reports were rebuilt with the final interval code (`e0c6817`).

## Results

| Task | Model | Mean score | Resolved | Tokens per trial, K (median / max) | Responses (median / max) | How trials ended |
| --- | --- | --- | --- | --- | --- | --- |
| rsn-001 | luna-medium | 100% | 3/3 | 1.9 / 1.9 | 2 / 2 | done 3 |
| rsn-001 | glm-5.3-high | 100% | 3/3 | 3.0 / 3.1 | 2 / 2 | done 3 |
| rsn-002 | luna-medium | 100% | 3/3 | 2.9 / 3.1 | 2 / 2 | done 3 |
| rsn-002 | glm-5.3-high | 93.3% | 3/3 | 6.0 / 6.3 | 2 / 2 | done 3 |
| tool-001 | luna-medium | 100% | 3/3 | 9.6 / 15.9 | 5 / 9 | done 3 |
| tool-001 | glm-5.3-high | 100% | 3/3 | 12.5 / 14.4 | 6 / 7 | done 3 |
| eng-001 | luna-medium | 93.9% | 2/3 | 70.0 / 86.0 | 9 / 13 | done 3 |
| eng-001 | glm-5.3-high | 100% | 3/3 | 312.3 / 326.8 | 13 / 18 | TRIAL_TOKEN_LIMIT 3 |

Token use over the three plans: luna-medium 268K, glm-5.3-high 1,014K.

### Mechanics confirmed

- **Format deduction.** glm-5.3 fenced one rsn-002 answer. It was graded on content, resolved, and scored 0.8, giving a task mean of 93.3%.
- **Partial credit.** luna's failed eng-001 trial scored 0.818 (18 of 22 checks), not 0.
- **Budget stops graded.** All three glm-5.3 eng-001 trials hit the 300K trial budget. They were graded on their final workspace, and all passed 22/22.
- **Reminders.** Each of the three glm-5.3 eng-001 trials received exactly three status messages, at the first turns past 50%, 75% and 90% of its token budget (for example 58%, 78% and 91%). No other trial passed 50% of any limit, so no other trial got a reminder. Both endpoints accepted the messages.
- **Bounded spending.** The largest overshoot of the trial budget was 26.8K tokens, one request, as designed.
- **Intervals.** Mean-score intervals use the Wilson interval of the score sum. Three perfect trials give 43.9–100%, not a zero-width interval (the fix in `e0c6817`).

### Failures checked against the task

- **luna, eng-001 rep 2: model error.** The trial failed 4 of 22 checks, all with `exit_code_mismatch`, and the cause is one bug. Its `parse_value` returns `(None, "type_mismatch")` for a malformed value, but the caller tests `value is None` first and treats the value as empty. A type error in a non-required column therefore produces no error at all: `age=notanint`, `active=maybe` and `score=abc` all pass.
- **glm-5.3, rsn-002 rep 1: format.** It fenced its JSON against the instruction "without Markdown fences". The 20% deduction applies.

No failure in this pilot came from a grader or the harness.

## Observations

- **The tasks are saturated.** Every task scored at least 93% mean for both models. This confirms PLAN-005 WP5 and [Task Set v2](../design/TASK_SET_V2.md).
- **Stating the budget did not make glm economise.** In each eng-001 trial, glm-5.3-high had a correct script well before the budget ran out, yet it kept writing probes and patches through every reminder until the budget stopped it. One trial wrote and ran `patch.py` after the 91% reminder. Its token use per trial fell from about 1M (max effort, no stated budget) to the 300K cap, because the cap now stops it. Its largest single response had about 5.5K characters of thinking, against 115K–135K at `max`.
- **luna used more tokens than in the first pilot**: 63K–86K against 24K–60K, with 9–13 responses against 6–9. The budget statement may encourage more self-testing when the budget is generous. Three trials cannot settle this.
- **Tokens per resolved eng-001 trial**, reported as efficiency and not scored: luna 110K, glm-5.3 316K.

## Consequences

- The budget values hold: no normal trial came close to its budget on reasoning or tool tasks. On eng-001 the budget bound only glm's over-verification, and did not cut it off before it had a correct solution.
- The next work is the harder task set; further budget tuning is not needed until those tasks exist.
