# Capability Card: ER live repair 0.1.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-25 (PLAN-007 WP3.2), before any model run.

## 1. Identity

- Tier: core.
- Capabilities: engineering (repository-scale repair of real issues).
- Protocol: `workspace-augmented` (workspace tools with command execution in the sandbox); the repository at the base commit in `repo/` with a fresh single-commit `.git`, the issue in the prompt and in `public/ISSUE.md`, the project's test dependencies through a read-only runtime mount; no network. Fixed budget track, provisional 3,000,000 tokens and one hour per task until the budget curve (Phase 4).
- Primary score: `resolved` (every FAIL_TO_PASS test passes and no PASS_TO_PASS test fails), as SWE-bench.

## 2. What it measures

Repairing real software from a real report: reading an unfamiliar repository, reproducing the problem, locating the cause, and changing the code without breaking what worked, in Python projects of many kinds (web frameworks, parsers, CLIs, numeric and data libraries, async runtimes).

## 3. What it does not measure

- Writing the tests: the hidden tests are the real fix's tests; the model may write its own, they do not count.
- Environment setup: dependencies are installed (read-only), so no time goes to installing.
- Speed: tokens and time are reported, not scored.

## 4. Where the difficulty lies

The tasks are real merged fixes for real issues, so their difficulty is whatever the issue demanded: some need a one-line guard once the cause is found, others a change across several modules (the gold patch's files and lines are recorded as covariates). The checks are the project's own tests from the real fix (FAIL_TO_PASS) and the tests of the same files that already passed (PASS_TO_PASS), so any correct fix that makes the project behave as its maintainers specified passes; a fix that only silences the symptom fails the behaviour tests, and a fix that breaks other behaviour fails PASS_TO_PASS. Published agents resolved about 19% of SWE-bench-Live at its release; there is no ceiling short of 100%.

## 5. Cheapest shortcut

- Reading the fix from history: the workspace has a fresh single commit, without the project's history.
- Editing or deleting the tests: every file the real tests touch is reset to its base content before the real tests are applied.
- Recalling a public fix: the validation and holdout tasks are mined from fixes merged since 2026-06-01, and every task created before a model's release date is flagged per model as possibly seen (release dates in the evidence table).
- Doing nothing: fails FAIL_TO_PASS (each task's base fails every FAIL_TO_PASS test, checked three times).
- Guessing hidden names: none are needed; the review (`private/review.json`) states in the prompt every new name or exact wording a task's tests use that the issue does not give, and leaves unchecked the separable tests of behaviour the issue does not describe.

## 6. Anchors and headroom

Contract family: no anchors. The gold patch resolves every task (self-calibration); no change resolves none.

## 7. Source, licence and provenance

- Dev: SWE-bench-Live instances (MIT), created up to 2025-09, flagged per model as possibly seen.
- Validation and holdout: our own mining of merged pull requests that close a linked issue and change tests, in permissively licensed (MIT, BSD, Apache, ISC, MPL) Python repositories, merged since 2026-06-01; repositories in dev are excluded.
- Each repository and runtime is stored as a content-addressed archive under `assets/` (kept out of Git, restored by `npm run prepare`); `private/selection.json` records every candidate and why each rejected one was rejected.

## 8. Task contract and grading

- The model gets `instruction.md`, the issue and the repository; it may run the project's tests.
- The grader (`private/grader.py`): the delivered change (the harness's diff of `repo/` against its single commit) is applied to a fresh copy of the base; every file the gold tests touch is restored and the gold test patch applied; the task's test files run with pytest in the sandbox with the runtime mount; results are parsed per test.
- Checks: `fail-to-pass` and `pass-to-pass`, both critical. Raw values: `f2pShare`, `p2pRegressions`, `patchApplied`.
- Equivalent solutions: any change that makes the tests pass.

## 9. Splits and size

Structure group = repository; no repository in two splits. See `calibration.md` for the counts of this build.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| Admission (per task) | the gold patch resolves; the base fails every FAIL_TO_PASS; three runs agree (flaky tests dropped); tests under 5 minutes | `private/builder.py`, `private/selection.json` |
| Contract review (per task) | every hidden check traces to the issue or to the prompt's "Names the tests use"; tasks whose issue contains the fix or whose tests check what the issue does not describe are excluded | `private/review.json` (decision and reason per task) |
| Stability | FAIL_TO_PASS and PASS_TO_PASS recomputed from five base and five gold runs with whole test ids; a test whose outcome varies is in neither list | `private/builder.py relabel`, the records' `relabel` field |
| References | see `calibration.md` | `python3 private/grader.py --self-calibrate --launcher scripts/sandbox_exec.py` |
| Null agent | no change resolves no task | self-calibration; suite smoke |
| Negative tests | weakened tests alone resolve nothing (the restore undoes them); a change that does not apply is graded as no change | self-calibration |
| Adversarial | no history in the workspace; tests restored before grading; candidate code runs in the sandbox without network | harness (CODE §5) |

## 11. Budget

Provisional 3,000,000 tokens and one hour per task; commands up to 5 minutes. The budget curve comes first in Phase 4.

## 12. History

- 0.1.0 (2026-10-25): the first build; no model run.
