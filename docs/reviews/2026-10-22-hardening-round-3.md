# Hardening Round 3, 2026-10-22

**Goal.** After round 2, deepseek-flash still scored 95–98% on T1, T2 and E3. The user and I first agreed to harden them through multi-chain structure: facts derived from other chains, branches that depend on them, and couplings between them, rather than through scale alone. Each family would be piloted on a few items before its full ladder was built.

During the round the user sharpened the goal. What matters is **discrimination between models**, so that their ratings spread; scores of 80–90% on some tasks are fine. T1 was accepted as it stands. T2 was to become substantially harder, in a corporate-finance setting.

Dev rounds used deepseek-flash with qwen3.8-flash and mimo-v2.6-flash as references, one repetition per item.

## T1: the adjudication ladder (task 0.6.0, grader 1.7.1)

Levels F2–F5 (`private/cases.py`). Each question asks how the change behind an incident must be rolled back under the snapshot's handbook: the procedure, its approver and its deadline. These follow from facts taken at the incident's start time, each found by its own chain:

- **tier**: the effective production value as the files stood then;
- **class**: with amendments, some rejected, some not yet effective;
- **freeze**: a Berlin-time calendar with tier and named exemptions;
- **reach**: the number of effective upstreams through includes and history.

Rotations with Berlin-time handovers, swaps and ownership transfers decide the approver. F5 adds what would apply had an earlier change never been made. A question is kept only when enough of twelve modelled misreadings change its conclusion. Self-calibration (2973/2973) includes an independent solver that undoes the history backwards.

**Pilot** (`runs/suites/20261022-102932-dev-87d3`, F4 and F5, two items each):

| Model | Score | Content | Deductions |
| --- | ---: | ---: | --- |
| deepseek-flash | 94.3% | 2 of 48 facts wrong | both reach |
| qwen3.8-flash | 85.0% | 100% | format only |
| mimo-v2.6-flash | 20.0% | | |

- deepseek's two errors were its own: an upstream change after the start time it did not undo, and a base.toml upstream it missed.
- mimo stopped mid-work twice and looped once.
- One grader defect: the approver's evidence was the whole rotation file, so right answers found by search failed. Grader 1.7.1 accepts the deciding lines.

The user accepted T1 as it is. The full suite runs F4 and F5, eight items.

## T2: from coupled shifts to a finance desk

**Shifts** (`t2-service-desk` 0.4.0, `sh1`–`sh4`). Each item was eight tickets handled in one workspace, under a policy that adds:

- recalls;
- a claims review counting today's earlier tickets;
- a goodwill limit;
- same-day shipping consolidation.

Each ticket was graded against the oracle on the state the model's own commands had produced. On the pilot (`runs/suites/20261022-110927-dev-4749`), deepseek and qwen scored **100%**, handling every planted trap, and mimo 82.5%. Coupling through derived conditions does not trip models that query the state and apply each rule as written.

**The finance desk** (`t2-finance-desk` 0.1.0, `fn1`–`fn4`). Failure analyses of τ-bench and τ²-bench point to where agents lose points:

- wrong arguments from numerical reasoning over complex databases, the largest class;
- compound and conditional requests;
- long, conditional procedures.

Each item is one September close day for a Dutch freight company:

- **Books**: about 45 open receivables and payables in four currencies, purchase orders with accrued receipts, subscription contracts, bank lines and an inbox.
- **Queue**: ten requests handled with `ledger.py` under `MANUAL.md`.

The hard points are the manual's rules together with planted data:

- **Receipts**:
  - carrying rates and settlement rounding;
  - named and exact-match allocation before oldest-first;
  - early-payment discounts with their VAT part;
  - write-offs within 5.00;
  - bank conversion costs;
  - prepayments.
- **Vendor invoices**:
  - duplicates under normalised numbers;
  - a three-way match with a 2% and a 50.00 EUR tolerance;
  - approval limits with segregation of duties;
  - VAT by vendor country and supply;
  - FIFO accruals;
  - a closed AP period.
- **Month-end**:
  - a credit note larger than what is open;
  - deferred revenue by day count;
  - a revaluation that counts only entries up to 30 September, with its reversal.

Grading is per request against the oracle on the request's starting state:

- **outcome**: the reply, and the status for vendor invoices;
- **allocation**: which documents were cleared, in their currencies;
- **amounts**: the net EUR per account, partner, document and period;
- **clean**: nothing posted beyond the request.

Self-calibration covers ten hand-worked examples and 56 scenarios:

- the oracle through the tool passes everything;
- the untouched books and a reply alone score 0;
- a single slip costs only its request;
- each of six misreadings costs 6–26% of the day.

**Pilot of 0.1.0:** deepseek 97.1%, qwen 100%, mimo 70%. deepseek's only loss was a mix-up between two customers' names. Every request was a specified procedure, which the strong models carry out exactly.

**0.2.0: a payment run.** The user approved one open-ended request, scored on a continuous scale between named plans:

- **0**: pay by due date;
- **0.5**: pay by worth per unit of cash;
- **1**: the best set the run allows.

On the pilot, deepseek and qwen both scored 100%. They enumerated every allowed set of payments with `itertools.combinations`: about 25 payables and at most 3–5 payments are tens of thousands of sets. The lesson: an optimum the oracle can find by enumeration, a model finds the same way.

**0.3.0: a two-week payment plan** (user's choice). R1 schedules 31–37 payables over ten business days.

- **Vendor terms:** each vendor has its own discount (3/7, 2/10 or 1/14), daily late interest and fixed late fee.
- **Cash:** each currency opens with cash and receives inflows on later days.
- **Limit:** a daily payment limit shared across currencies.

Overdue payables lose worth every day, while discount and soon-due payables keep it until a deadline. A good plan pays the first early and the others as late as their deadline allows, as the cash arrives.

- **Best plan:** a stdlib search (annealing, large-neighbourhood rebuild, polish) equals the exact MILP optimum on all four days.
- **Scale:** seven rungs, each weighing 2, about a quarter of a day's score.
- **Drawing:** a day is kept only when the greedy plan, and the greedy plan polished by single moves and swaps, fall short of the best.

Offline, plain strategies spread over the scale:

| Strategy | Place |
| --- | ---: |
| greedy | 0.5 |
| deadline-aware greedy | 0.65–0.86 |
| plus hill-climbing | 0.83–0.94 |
| a real search | 0.98–1.0 |

**Pilot of 0.3.0** (`runs/suites/20261023-050438-dev-9f16`, 6M tokens per day):

| Model | Score | fn1 | fn2 |
| --- | ---: | ---: | ---: |
| deepseek-flash | 98.0% | 100% | 96.1% (plan at ≥0.97, not 1) |
| qwen3.8-flash | 67.6% | 100% | 35.3% (budget stop) |
| mimo-v2.6-flash | 8.8% | 0 | 17.6% (budget stop) |

- deepseek and qwen wrote real searches (restarts, annealing, hill climbing) and reached the optimum.
- mimo stopped at greedy rules and bounds, reaching the 80 rung.

The plan now separates strong models from weak ones. The low scores, however, came largely from the budget:

- qwen spent 4.0M tokens solving R1 exactly, then ran out with nine requests undone;
- mimo used 5.57M before it began R1;
- 92–98% of every trial's tokens were cache reads.

Since efficiency is reported and not scored, the user raised T2 to 10M tokens per day.

## E3: S7, planning (eng-005 0.5.0, grader 2.2.0)

S7 adds `plan --crews N`: schedule the open orders on identical crews after their prerequisites, minimising Σ priority × end.

**Stores.** Five hidden stores cover cases with exact methods (exhaustive search on 7 and 9 orders, Sidney's rule on chains) and without (300 and 3,000 orders). Gateway orders make the plain greedy rule 8–23% worse than the best known.

**Scale.** Plans are placed between three anchors stated in the brief: the naive plan (0), the greedy plan (0.5) and the best known (1). Quality rungs sit at a mean place of 0.25–0.97, beside validity on the S6 scale store, read-only planning, error codes and kept fields.

**Score.** The manifest weighs the ten ladder rungs (speed and quality) as much as the 50 correctness checks, and the suite now applies manifest weights to trajectories.

**References.**

- ref-a (greedy) is placed at 0.5.
- ref-b (successor-aware ranking, exhaustive on small stores) is placed at 0.938.

Both pass every correctness check over three repetitions. Four plan mutants land where expected, and the trajectory tests pass with seven stages.

**Pilots.** Four pilots of 0.5.0 each ended in budget stops (details in the package's calibration record):

| Run | Context | deepseek | qwen | Main cause |
| --- | --- | ---: | ---: | --- |
| `20261022-142620` | one session | 59% | 59% | a stage's own budget ended the whole trajectory (fixed: the next stage follows) |
| `20261022-161703` | one session | 44% | 41% | the 23 MB S6 store exceeded the snapshot limits (raised); context growth |
| `20261023-023502` | one session (the per-stage change was uncommitted) | 80% | 59% | qwen reached S7 with 11 calls left |
| `20261023-034838` | a fresh session per stage (user decision) | 30% | 41% | see below |

Audit of the per-stage pilot:

- **deepseek, S6.** A genuine regression: its faster write path corrupts the store when two writes follow each other. That broke S6 and everything after it.
- **deepseek, S7.** It wrote `plan.ts` but ran out before wiring `plan` into the CLI.
- **qwen, S6.** A scratch symlink made the snapshot fail and ended the trajectory. That is not attributable to the model.

Harness fixes (`838a90d`, `d91b39a`, `ed910f5`):

- snapshots skip links and special files;
- artifact error codes are kept as the stop reason;
- the report sums the usage it has;
- a suite refuses to resume under another Node major version;
- an interrupted retry continues on resume.

Both models used the whole 2.5M budget of S5–S7, mostly on cache reads. The user raised E3 to 5M per stage and 25M per trajectory.

## Results

| Family | Version and protocol | deepseek-flash | qwen3.8-flash | mimo-v2.6-flash | Run |
| --- | --- | ---: | ---: | ---: | --- |
| T1 | 0.6.0, grader 1.7.1, F4/F5 | 94.3% | 85.0% (content 100%, losses are format) | 20% | `runs/suites/20261022-102932-dev-87d3` |
| T2 shifts | 0.4.0 | 100% | 100% | 82.5% | `runs/suites/20261022-110927-dev-4749` |
| T2 finance | 0.1.0 | 97.1% | 100% | 70% | see the package calibration record |
| T2 finance | 0.2.0, single-day payment run | 100% | 100% | 34.1% (fn1 only) | `runs/suites/20261023-035140-dev-a7e7` |
| T2 finance | 0.3.0, multi-day plan, 6M per day | 98.0% | 67.6% (fn2 stopped by the budget) | 8.8% | `runs/suites/20261023-050438-dev-9f16` |
| E3 | 0.5.0, one session, stage 2.5M | 80% | 59% | — | `runs/suites/20261023-023502-dev-c750` |
| E3 | 0.5.0, per stage, stage 2.5M | 30% | 41% | — | `runs/suites/20261023-034838-dev-65e9` |
| E3 | 0.5.0, per stage, stage 5M, trajectory 25M | 90.0% | 94.0% | — | `runs/suites/20261023-113824-dev-b319` |

**What the round showed.**

- **Rules make tasks longer, not harder.** Rule-based hardening (T1 adjudication, T2 couplings and finance rules) did not lower the strong models' content scores.
- **Small optimisations fell to generic methods.** The T2 0.2.0 run was enumerated, and the T2 0.3.0 plan was solved by annealing and restarts.
- **Low scores were mostly budget and harness effects.** The T2 0.3.0 and E3 per-stage lows came from budgets and from three harness defects:
  - snapshots refusing a scratch symlink;
  - a lost retry on resume;
  - a 10-second command limit not stated to the model.

  All of these were fixed (`838a90d`, `ed910f5`, `b46c859`). With a sufficient budget, E3 saturated.
- **Every result above is a single trial.** One trial per model and item on two to four items. These numbers are exploratory; per-model differences within a family are not established.

The user then decided (2026-10-23) to take new difficulty from open sources (`docs/design/FRONTIER_TASKS.md`, the AE family), and on 2026-10-24, after the third-party review, to restructure the whole project: `docs/design/v2/` and PLAN-007.
