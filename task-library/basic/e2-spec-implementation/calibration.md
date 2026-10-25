# Calibration Record: E2 Specification Implementation

E2 is the specification-implementation family of Task Set v2 (PLAN-005 WP5). It hardens the form of eng-001 with original specifications whose behaviour has no ready-made public implementation. The specifications are full of rules that are easy to misread: right-associative powers, unary minus binding tighter than powers, error precedence, dynamic dependency cycles, and output rounding. They come with many hidden fixtures, so scores are partial and spread out.

## Version 0.1.0 (2026-10-18)

- **Item `sheet`.** A small spreadsheet evaluator, specified in `items/sheet/prompt.md` and implemented by `private/sheet/reference.py`. Its 25 hidden fixtures in `private/sheet/fixtures.py` form 16 checks.
- **Expected values written by hand.** Every fixture's expected output was written by hand and compared with the reference. The one disagreement was `="x"+1/0`: the reference returns `#DIV/0!` and the hand-written value was `#VALUE!`. The reference matched the specification. The specification gained an explicit rule that operand errors take precedence over an operator's own type error, plus a matching rule for function arguments.
- **Self-calibration** (`python3 private/grader.py --self-calibrate`, 11/11):
  - the reference passes every check, and a missing program fails every check;
  - nine mutants each fail the check they target: a left-associative power, no IF short-circuit, AVERAGE counting empty cells, case-insensitive text comparison, no output rounding, type checks before operand errors, cycles reported as `#REF!`, floats for integral values, and division by zero as `#NUM!`.
- **Comparison tolerance.** A first calibration found that numeric comparison within 1e-9 let unrounded output pass. A later run found that a strict integer-format comparison made a pure formatting slip fail 75% of the checks. Strict comparison is now confined to the `rounding` and `number-format` checks, so such a slip costs those checks and the text checks that use the number's output form, and no others.

### Calibration 2026-10-18 (task 0.1.0, 300,000 tokens per trial)

Run `82f84f8a`, four models, three repetitions each. Findings:

- **The token budget was too tight.** The only valid deepseek and glm trials both stopped at the 300,000-token limit after about 11 responses. Most of the spend is the conversation context resent with each request, not new output: deepseek's eleven requests produced about 34,000 output tokens. luna finished in 22,000–44,000 tokens.
- **One expectation was not set by the specification.** `=0^-1` was expected to be `#NUM!`, and deepseek, glm and luna all returned `#DIV/0!`, as Excel does. Grader 1.1.0 dropped the cell. Every other failed check was audited against the specification and is the model's own error: an empty cell compared with a number, a reference skipped after an earlier error, `AA1` as a reference, `10.0` printed for `10`, and crashes.
- **Five trials were lost to infrastructure.** Their workspaces were deleted during the run by an operator cleanup command, and every later tool call failed. One more trial hit a provider outage.
- Valid scores under grader 1.1.0: glm 100% (resolved; every check passed although the budget stopped it), deepseek 94% (no README before the budget stop), luna 71–94% over three trials, step 0% (one response exceeded 32,768 output tokens and wrote no file).

## Version 0.2.0 (2026-10-19)

- The specification states that zero raised to a negative power is `#DIV/0!`, and the reference implements it. The `division` fixture tests `=0^-1` again and adds `=0^0` (1).
- A tenth mutant, zero to a negative power as `#NUM!`, fails the `division` check. Self-calibration 12/12.
- The calibration budget rises to 800,000 tokens per trial; see `experiments/e2-calibration-2026-10/README.md`.

## Version 0.3.0 (2026-10-19)

- **Two more items.** One item could not give E2 a reliable score.
  - `ledger`: an account ledger with 13 hidden fixtures in 12 checks.
  - `recur`: a recurrence expander with 11 hidden fixtures in 11 checks.
  - Both specifications are original, and both are dense with rules that are easy to misread: half-even rounding where binary floating point rounds 1.365 the wrong way, holds that capture without a funds check, duplicate ids after a rejection, a stated error order, counts taken before exceptions, month-end clamping that does not apply to nth weekdays, and leap days.
- **Expected values written by hand.** Weekday facts came from a printed calendar. Both references matched every hand-written fixture at the first comparison.
- **Exact comparison.** `ledger` and `recur` output must match exactly, JSON types included.
- **Self-calibration (36/36).** Each reference passes every check, and a missing program fails every check. 11 ledger mutants and 9 recur mutants each fail the check they target, among them float conversion, half-up rounding, holds left out of the available amount, a capture checked against available funds, ids recorded only on success, frozen accounts refusing deposits, counts taken after exceptions, clamping applied to nth weekdays and an inclusive `until` treated as exclusive. See `logs/self-calibration-0.3.0.log`.

### Calibration 2026-10-19 (task 0.3.0)

deepseek-flash passed every check of all three items. On `sheet`, glm scored 97%, luna 82% and step 50%. `ledger` separated only luna, and `recur` was solved by every model. See `experiments/e2-calibration-2026-10/README.md`.

## Version 0.4.0 (2026-10-20)

- **Item `query`.** A small query language over in-memory tables: 13 rule areas, with 87 queries in 13 fixtures. It looks like SQL but differs from SQLite on purpose:
  - exact decimals, and `/` giving the exact quotient;
  - `NULL` sorting last in ascending order;
  - case-sensitive `LIKE`;
  - `TYPE_MISMATCH` for comparisons of different kinds;
  - `ROUND` half away from zero on exact decimals.

  A program that hands the work to `sqlite3`, or relies on SQL habits, fails those rules. The specification also fixes the grouping rules, join order, result column names and the order in which errors are found.
- **Expected values written by hand.** The reference matched every one at the first comparison.
- **Self-calibration (53/53).** 15 query mutants each fail the check they target:
  - NULLs first in ascending order;
  - case-insensitive `LIKE`;
  - truncating integer division;
  - floats for decimals;
  - no short-circuit;
  - comparisons across kinds;
  - two-valued `IN`, which needed one more fixture, because `WHERE` hides the difference between `NULL` and `FALSE`;
  - an integer `AVG`;
  - a LEFT JOIN treated as inner;
  - `ORDER BY` aliases unsupported;
  - grouping checked before names;
  - unchecked ordinals;
  - half-even `ROUND`;
  - ignored `AS`;
  - `HAVING` without groups.

  See `logs/self-calibration-0.4.0.log`.
- **The calibration plan** selects `sheet` and `query`. `ledger` and `recur` remain as easy anchors.

## Version 0.5.0 (2026-10-20)

**Why.** `sheet` and `query` are near saturation: deepseek and qwen pass every query category. Strong models implement a precise specification almost perfectly, however long it is. A fixed-answer item cannot place them below 80%, so 0.5.0 adds an item whose score is continuous.

**routes** is an optimisation item in the form of ALE-Bench: delivery routing with van capacity, a maximum route duration and refrigerated vans, minimising total distance.

- **Instances.** Eight hidden instances of 50–800 customers, random and clustered, with different capacities and duration limits. `private/routes/instances.py` generates them reproducibly. Two samples are public, with their costs and a checker.
- **Scale.** The baseline is nearest neighbour, which every instance is built to admit as a feasible plan. The best known cost is the best of three 15-minute runs of the reference solver (`private/routes/reference.py`, ruin and recreate with simulated annealing). It is 25–48% below the baseline.
- **Scoring.** The program has 8 seconds per instance (stopped at 10) on one CPU core, which the grader pins so that extra processes gain nothing. Each instance has four checks, at 50, 80, 90 and 97% of the way from baseline to best; the top thresholds on the largest instances are beyond an 8-second Python run.
- **Self-calibration.** `logs/self-calibration-0.5.0.log`, 60/60 with every other item:

  | Candidate | Checks | Share of the way per instance |
  | --- | ---: | --- |
  | 7-second LNS, starting from the baseline | 23/32 | 1.00 at 50 customers, 0.78 at 800 |
  | Clarke-Wright savings | 12/32 | 0.61–0.89 |
  | the baseline itself, an infeasible plan, a program that runs too long, a missing program | 0/32 | — |

  A model that combines a savings start with local search or ruin and recreate should land between these.


## Grader 1.6.0 and manifest v2 (2026-10-24, task 0.5.0 unchanged, PLAN-007 WP2.2)

**Why.** v2 reports open-ended items by a raw value through anchors, not by rungs (MEASUREMENT §3), and routes is an open-ended bridge in core engineering (TASK_LIBRARY §2).

**Change.**

- **Routes** reports `routeShare`, the mean over the eight hidden instances of `(baseline − cost) / (baseline − best known)`, each at least 0 and never capped (an infeasible, missing or late plan counts 0, as the contract says): the contract's own scale as a value. Its anchors are `baseline` (0) and `best-known` (1) on that scale. Diagnostics: `routeCost` (the total length, an instance without a feasible plan, or worse than the baseline, at the baseline's cost) and `feasibleInstances`. The 32 rung checks are unchanged and become labels in a non-critical group.
- Routes gradings run one at a time under a lock (`~/.cache/agenteval/e2-routes-grading.lock`), since the contract's limit is wall time; the noise test (`--noise`) measures what load does to the value.
- **Manifest v2**: the card; one critical group per contract item and a critical `readme`; routes headlined by `routeShare` (`primaryByItem`); every item dev, its own structure group.

**Self-calibration** (`logs/self-calibration-0.5.0-grader-1.6.0.log`, 60/60): unchanged results; LNS 22/32 rungs, savings 12/32, the baseline, an infeasible plan, a slow and a missing program none.

**Re-grade.** Every graded 0.5.0 routes trial (`runs/4e0b6c30-…`, `runs/a69d9886-…`) was re-graded under 1.6.0; trials stopped by infrastructure stay unscored.

**Noise test** (`python3 private/grader.py --noise [--load N]`, `logs/noise-0.5.0-grader-1.6.0-routes.log`, PROTOCOL §9), declared tolerance 0.03 on `routeShare`. Savings, which finishes at once, is identical under any load. The 7-second LNS, which stops by the wall clock: with 5 busy processes on 20 cores, 0.909 → 0.900 (0.009), no label changed (pass); with all 20 cores busy, 0.908 → 0.856 (0.052), three rung labels lost (fail). Two quiet runs agree to 0.001. The contract's limit is wall time, so a time-bounded search does less work when its core is shared; the lock removes contention between routes gradings but not other load. Moving the limit to CPU time would change the contract, and so the task version, which a bridge should not; this stays open for the user (PLAN-007 Phase 2 review).

## Grader 1.7.0 (2026-10-24, task 0.5.0 unchanged, PLAN-007 WP2.2)

**Why.** Re-grading the 0.5.0 routes trials under 1.6.0 showed what the v2 score model made of a critical README: 8 of the 15 graded deliveries wrote no `README.md`, and their primary was 0, deepseek-flash's at 0.904 and mimo-v2.6-flash's at 0.886 of the way included. A documentation file decides nothing about the routes the program plans, and the same holds for the contract items' implementations. The routes item also needs a validity criterion of its own, which the README was standing in for: a null delivery must not count as valid.

**Change.** A new routes check, `feasible` (`REQ-ROUTES-FEASIBLE`): routes.py printed a feasible plan for at least one of the eight hidden instances. It is the routes item's critical group (`routes-valid`); a delivery that solves no instance is not valid. The README check stays, in a non-critical group of weight 0.1, for every item. The rung checks and the raw values are unchanged.

**Self-calibration** (`logs/self-calibration-0.5.0-grader-1.7.0.log`): as under 1.6.0, plus `feasible` passing for LNS, savings and the baseline and failing for the infeasible, slow and missing programs.

**Re-grade.** Every graded 0.5.0 routes trial re-graded under 1.7.0.

## Version 0.6.0 (2026-10-25, grader 2.0.0)

Routes is measured in CPU time, not wall time.

**Self-calibration** (`logs/self-calibration-0.6.0-grader-2.0.0.log`): `RESULT: PASS (63/63)` — including `routes-timeout-earns-nothing` (the slow program: 0/32 rungs, every instance a 10.0 s CPU-time timeout) and `routes-waiting-is-not-cpu-time` (the waits program: feasible, its costs equal the baseline's).

**Noise test** (`--noise --load 20`, `logs/noise-0.6.0-grader-2.0.0-routes.log`; run twice on 2026-10-25 with the same outcome): `RESULT: FAIL (1/2), tolerance 0.03 on routeShare`. The savings solution is stable — routeShare 0.773517 quiet and busy, change 0.0000. The lns solution is not — quiet 0.915444 against busy 0.859610 (change 0.0558), with the `h5-90`, `h6-80` and `h7-80` checks passing only when quiet.

**Half load** (`--noise --load 10`, `logs/noise-0.6.0-grader-2.0.0-routes-load10.log`): `RESULT: FAIL (1/2)`; LNS 0.913139 quiet, 0.874582 with 10 of 20 cores busy (change 0.0386, labels h5-90 and h6-80 lost); savings unchanged. The two quiet LNS gradings of the day differ by 0.0023.

**Conclusion and procedure.** The CPU-time limit fixes what the contract measures (no wall-time verdicts, waiting is free), but a search bounded by CPU time still does less work per CPU second on a busy machine. Routes therefore reports `gradingLoad` (the highest 1-minute load per core while graded), and every routes delivery is re-graded on a quiet machine, load under 0.1 per core, after its run; the suite reports only quiet gradings.

