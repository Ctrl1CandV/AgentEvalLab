# Capability Card: T2 finance desk 0.3.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP2.2), for the unchanged task 0.3.0 and grader 1.2.0.

## 1. Identity

- Tier: basic (the ledger operations). The two-week payment plan, the day's one open-ended request, is reported here as a diagnostic group; as an AP bridge it waits for AP (PLAN-007 Phase 3).
- Capabilities: agentic (a stateful tool, a long manual, a queue of requests).
- Protocol: `workspace-basic` with command execution; one session per day; fixed budget track, 10,000,000 tokens and four hours per day (user decision 2026-10-23; `experiments/t2-finance-2026-10/dev.eval.json`), stated to the model.
- Primary score: resolved (every request handled exactly as the manual says, the day's changes attributed and ordered, the books at the correct end state).

## 2. What it measures

Following a long operating manual through a stateful tool over a queue of eleven requests during a month-end close: receipts and their allocation, credit notes, vendor invoices, revaluation, deferred revenue, and a payment plan; changing the books only through `ledger.py`, one request at a time, and replying in the manual's JSON form.

## 3. What it does not measure

- Accounting knowledge beyond the manual: every rule is in `MANUAL.md`.
- Optimisation as the headline: the payment plan's quality is a diagnostic here (and an AP bridge later).
- Efficiency: tokens and calls are reported, not scored.

## 4. Where the difficulty lies

Reliability across a long queue. Each request is ordinary, but each has its own manual section with exceptions (allocation order, rounding, which account), the books carry state from one request to the next, and a single wrong command leaves the day's end state wrong. The payment plan is a real search problem, but the strong models solve it exactly (deepseek-flash and qwen3.8-flash reached the optimum on fn1 with random restarts and annealing in the 0.3.0 pilot); what separated models was finishing the queue: qwen ran out of budget after spending 4M tokens on the plan, mimo-v2.6-flash stopped early or handled nothing.

## 5. Cheapest shortcut

- Doing nothing: every request check and `end-state` fail.
- Writing the books directly instead of through `ledger.py`: the integrity check compares the books with the audit log.
- Changes under an unknown request number, or outside the order (the third-party review's hole): `coverage` and `end-state` fail (grader 1.2.0).
- A reply in another form: the content is still graded, less 10% of the primary (user decision of 2026-10-25, grader 1.3.0).

## 6. Anchors and headroom

No anchors for the headline (contract task). The payment plan's rungs (25–100% of the way from a naive plan to the best known plan) are labels in the diagnostic group `plan`.

## 7. Source, licence and provenance

Project-authored manual, books, tool and requests (`private/finance.py`, seeds `t2-finance-2026-10:fn1`–`fn4`); the task form follows tau-bench and tau2-bench, no text copied. Exposure: generated, private to runs.

## 8. Task contract and grading

- The model receives `instruction.md`, the day's request queue (`prompt.md`) and `public/` (`MANUAL.md`, `ledger.py`, the books), and ends with the JSON reply the manual describes.
- Checks per request: `outcome`, and `allocation`, `amounts`, `clean` as the request kind needs; for the plan, `outcome`, `clean` and seven rungs; per day: `coverage` and `end-state`.
- Score model: `requests` (rule fraction, critical, weight 2) over every request check except the plan rungs; `day` (rule fraction, critical, weight 1) over `coverage` and `end-state`; `plan` (rule fraction, not critical, weight 1) over the rungs. Resolved when both critical groups pass in full; diagnostic over all three. Format `answer-format`, its 0.2 deduction reported separately.
- Equivalent solutions: any command sequence that leaves the same books under the right requests, in order; repeated `begin`, a begun request that changes nothing, and a plan revised before the next request all keep every check.

## 9. Splits and size

- Structure group: the generator (`generator:finance-day`): the four days come from one template, so the family has one group and no interval.
- All four days are dev (fn1 and fn2 have been run; fn3 and fn4 are of the same template). Basic tier: no validation or holdout. The basic suite runs fn1 and fn2.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: the oracle day keeps every check | `python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.3.0-grader-1.2.0.log` |
| Null agent | pass: nothing done fails every request | self-calibration; the basic suite smoke |
| Mutants | pass: modelled misreadings (oldest-first allocation, no discount, no write-off, revaluing now, ...) change the requests they should; a misbooked or held request loses exactly its own checks and `end-state`; due-date and greedy plans lose the upper rungs | self-calibration |
| Alternative valid solutions | pass: markers repeated or absent, an unknown request begun without changes, the plan revised | self-calibration |
| Adversarial | pass: unknown request numbers, changes before the first `begin`, reopened requests, requests out of order | `tests/t2-coverage.test.ts`, self-calibration |
| Coverage invariant | pass: `coverage` (grader 1.2.0) | rubric |
| Global end state | pass: `end-state` (grader 1.2.0) | rubric |
| Success audit | pass: no false pass, no false fail over the six 0.3.0 trials (72 units) | `docs/audits/T2/2026-10-24.md` |
| Noise, determinism | n/a: nothing timed; grading is a function of the books and the audit log | — |

## 11. Budget

10,000,000 tokens and four hours per day (user decision 2026-10-23). Never run at this budget yet; at 6M two of six trials stopped on the budget.

## 12. History

- 0.1.0–0.3.0: see `calibration.md`.
- Grader 1.2.0 (2026-10-24): `coverage` and `end-state`; every 0.3.0 trial re-graded.
- 2026-10-24: manifest v2 with this card; the plan rungs, critical under v1 (where every check counted), are a non-critical diagnostic group, so a day handled correctly with a plan short of the optimum is resolved. Task and grader unchanged.
