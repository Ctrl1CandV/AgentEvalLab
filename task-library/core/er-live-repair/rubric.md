# Rubric: ER 0.1.0

- `fail-to-pass` (critical): every FAIL_TO_PASS test of the task passes on the delivered change (the tests that fail at the base commit and pass with the real fix).
- `pass-to-pass` (critical): no PASS_TO_PASS test fails (the tests of the same files that pass at the base and with the fix, three times in a row).
- Before the tests run, the delivered change is applied to a fresh copy of the base; a change that does not apply is graded as no change. Every file the real fix's tests touch is reset to its base content and the real tests are applied, so edits to those files do not count.
- Resolved: both checks. Diagnostic: 0.7 · `fail-to-pass` + 0.3 · `pass-to-pass`. Raw values: `f2pShare`, `p2pRegressions`, `patchApplied`.
- Test results are read from pytest's `-rA` summary with whole test ids (parameters containing spaces included; colour codes removed).
- Every admitted task passed a review against the public contract (`private/review.json`): tasks whose tests check what the issue does not describe, or whose issue contains the fix, were excluded; where the tests need a name or wording the issue does not give, the task's prompt states it under "Names the tests use"; tests of behaviour the issue does not describe, when separable, are left unchecked.
