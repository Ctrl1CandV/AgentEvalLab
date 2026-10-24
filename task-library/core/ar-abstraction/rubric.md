# Rubric: AR 0.1.0

- `test-<n>` (critical, one per test input): attempt 1 or attempt 2 of entry `n` equals the expected output grid exactly, dimensions included. Later attempts and extra entries are ignored.
- `answer-format` (not critical): the reply is exactly one JSON object of the stated form. A reply whose last JSON object (fenced or not) has the form is graded on its content and fails this check; the deduction (0.2) is reported separately (decision D2).
- Resolved: every `test-<n>`. Diagnostic: the share of test outputs matched (`testShare`). `wellFormed` is 1 when every given attempt is a grid of 1–30 rows and columns of digits 0–9.
- A reply with no such object fails every check.
