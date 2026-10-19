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
