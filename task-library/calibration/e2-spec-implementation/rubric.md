# Rubric: E2 Specification Implementation

Each item is one self-contained specification with hidden fixtures. The candidate's program runs on every fixture in the bubblewrap sandbox: no network, and only a fresh copy of the program and its input are writable. The program has 10 seconds per fixture. Its JSON output is compared with the expected output.

## Checks

- One critical check per rule area. A check passes when every fixture in it produces exactly the expected output. Numbers compare within 1e-9, except in the `rounding` and `number-format` checks, which test the output rule itself: there, integral values must be JSON integers and other numbers must match within 1e-12.
- `readme` (critical): a README.md is delivered, as the specification asks.
- The score is the fraction of checks passed; the item is resolved when all pass.

## Items

| Item | Specification | Checks |
| --- | --- | --- |
| sheet | A small spreadsheet evaluator: parsing, precedence, types, functions, error propagation, dynamic cycles, output formatting | 16 rule areas and a README |

## Changes

- Grader 1.1.0 (2026-10-19, task 0.1.0): the `division` check no longer tests `=0^-1`. The specification did not say whether zero to a negative power is `#DIV/0!` (as in Excel) or `#NUM!`, and three of four calibration models chose `#DIV/0!`.
- Task 0.2.0, grader 1.2.0 (2026-10-19): the specification states that zero to a negative power is `#DIV/0!`, and the `division` check tests it again, with `=0^0` as well.
