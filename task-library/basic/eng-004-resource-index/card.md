# Capability Card: eng-004 resource index maintenance 0.3.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP2.2), for the unchanged task 0.3.0 and grader 1.2.0.

## 1. Identity

- Tier: basic.
- Capabilities: engineering.
- Protocol: an existing two-commit TypeScript repository (the pinned baseline `0bd1eda`) with command execution; `workspace-basic` or `workspace-augmented`, chosen per plan (the package exists partly to compare the two); one session; fixed budget track. **No budget stated yet**: no model has run this version.
- Primary score: resolved (all seven acceptance checks pass).

## 2. What it measures

A small maintenance change in an unfamiliar code base: reading the repository and its contract, adding a `search` command with filtering, default pagination and code-point ordering, rejecting bad arguments with the documented errors, repairing CSV export to RFC 4180, and keeping the existing `index` behaviour.

## 3. What it does not measure

- Large-repository navigation: the repository is a few files.
- Library knowledge: Node.js 22 built-ins only, no dependencies.
- Speed: reported, not scored.

## 4. Where the difficulty lies

Reliability. Every behaviour is in `public/task-contract.md`; the work is getting all of it right together in an existing code base, including the details that trip careless changes: Unicode code-point order rather than locale order, pagination boundaries, CSV quoting and CRLF line endings, and leaving `index` untouched. It is not expected to separate strong models; it catches slips and regressions.

## 5. Cheapest shortcut

- An untouched workspace: 0/7 (grader 1.2.0 guards the two checks the baseline would pass on its own).
- Hard-coding the public catalogue: the hidden catalogues differ.
- Editing the tests: the grader runs its own hidden checks against the CLI, not the repository's tests.

## 6. Anchors and headroom

No metric anchors (contract task). Little headroom by design.

## 7. Source, licence and provenance

Project-authored baseline (`private/baseline-source`, built reproducibly by `private/build_baseline.py` into `baseline.bundle`), contract and references. Exposure: private to runs (never run by a model yet).

## 8. Task contract and grading

- The model receives the baseline repository at `0bd1eda`, `instruction.md` and `public/task-contract.md`, and changes the repository.
- Seven critical checks: `search-filter`, `default-pagination`, `unicode-codepoint-order`, `pagination-boundaries`, `invalid-pagination`, `csv-rfc4180`, `index-compatibility`; candidate code runs in the sandbox.
- Score model: one group `acceptance` (rule fraction, critical); resolved when every check passes.
- Equivalent solutions: any implementation; the references overlay different `search.ts`, `cli.ts` and `export.ts` and both pass.

## 9. Splits and size

One task: split dev, structure group `package:eng-004`. Basic tier, no validation or holdout.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: both references 7/7, three times | `logs/self-calibration-0.3.0.log` |
| Null agent | pass: the untouched baseline earns nothing | self-calibration |
| Mutants | pass: three mutants rejected | self-calibration |
| Alternative valid solutions | pass: two references | self-calibration |
| Adversarial | pass: candidate code runs in the sandbox | grader 1.1.0 onwards |
| Coverage invariant, global end state | n/a | — |
| Noise | n/a: nothing timed | — |
| Determinism | pass: three repeated reference runs agree | self-calibration |

## 11. Budget

None stated: the package has never run with a model. It is in the basic tier but not in `suites/basic.json` until a budget is set (PLAN-007 Phase 2 review).

## 12. History

- 0.1.0–0.3.0: see `calibration.md` (0.3.0 rebuilt the lost baseline).
- 2026-10-24: manifest v2 with this card; task and grader unchanged.
