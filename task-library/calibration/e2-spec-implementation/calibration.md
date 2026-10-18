# Calibration Record: E2 Specification Implementation

E2 is the specification-implementation family of Task Set v2 (PLAN-005 WP5). It hardens the form of eng-001 with original specifications whose behaviour has no ready-made public implementation. The specifications are full of rules that are easy to misread: right-associative powers, unary minus binding tighter than powers, error precedence, dynamic dependency cycles, and output rounding. They come with many hidden fixtures, so scores are partial and spread out.

## Version 0.1.0 (2026-10-18)

- **Item `sheet`.** A small spreadsheet evaluator, specified in `items/sheet/prompt.md` and implemented by `private/sheet/reference.py`. Its 25 hidden fixtures in `private/sheet/fixtures.py` form 16 checks.
- **Expected values written by hand.** Every fixture's expected output was written by hand and compared with the reference. The one disagreement was `="x"+1/0`: the reference returns `#DIV/0!` and the hand-written value was `#VALUE!`. The reference matched the specification. The specification gained an explicit rule that operand errors take precedence over an operator's own type error, plus a matching rule for function arguments.
- **Self-calibration** (`python3 private/grader.py --self-calibrate`, 11/11):
  - the reference passes every check, and a missing program fails every check;
  - nine mutants each fail the check they target: a left-associative power, no IF short-circuit, AVERAGE counting empty cells, case-insensitive text comparison, no output rounding, type checks before operand errors, cycles reported as `#REF!`, floats for integral values, and division by zero as `#NUM!`.
- **Comparison tolerance.** A first calibration found that numeric comparison within 1e-9 let unrounded output pass. A later run found that a strict integer-format comparison made a pure formatting slip fail 75% of the checks. Strict comparison is now confined to the `rounding` and `number-format` checks, so such a slip costs those checks and the text checks that use the number's output form, and no others.
- No model has been run yet.
