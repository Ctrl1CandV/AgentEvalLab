# Rubric: E2 Specification Implementation

Each item is one self-contained specification with hidden fixtures. The candidate's program runs on every fixture in the bubblewrap sandbox: no network, and only a fresh copy of the program and its input are writable. The program has 10 seconds per fixture. Its JSON output is compared with the expected output.

## Checks

- One critical check per rule area. A check passes when every fixture in it produces exactly the expected output. For `sheet`, numbers compare within 1e-9, except in the `rounding` and `number-format` checks, which test the output rule itself: there, integral values must be JSON integers and other numbers must match within 1e-12. For `ledger` and `recur`, output must match exactly, JSON types included, so `1` does not stand for `true`.
- `readme` (critical): a README.md is delivered, as the specification asks.
- The score is the fraction of checks passed; the item is resolved when all pass.

## Items

| Item | Specification | Checks |
| --- | --- | --- |
| sheet | A small spreadsheet evaluator: parsing, precedence, types, functions, error propagation, dynamic cycles, output formatting | 16 rule areas and a README |
| ledger | An account ledger: amount formats, overdraft limits, transfers with half-even currency conversion, holds and captures, frozen accounts, reversals, duplicate ids, a stated error order | 12 rule areas and a README |
| recur | A recurrence expander: daily, weekly, monthly and yearly rules, month-end skip or clamp, nth weekdays, leap days, counts taken before exceptions, limits, validation | 11 rule areas and a README |

## Changes

- Grader 1.1.0 (2026-10-19, task 0.1.0): the `division` check no longer tests `=0^-1`. The specification did not say whether zero to a negative power is `#DIV/0!` (as in Excel) or `#NUM!`, and three of four calibration models chose `#DIV/0!`.
- Task 0.2.0, grader 1.2.0 (2026-10-19): the specification states that zero to a negative power is `#DIV/0!`, and the `division` check tests it again, with `=0^0` as well.
- Task 0.3.0, grader 1.3.0 (2026-10-19): two more items, `ledger` and `recur`, so the family no longer rests on one specification.
