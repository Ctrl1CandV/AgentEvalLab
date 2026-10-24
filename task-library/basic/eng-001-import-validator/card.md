# Capability Card: eng-001 CSV import validator 0.3.2

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP2.2), for grader 1.2.0 on the unchanged task 0.3.2.

## 1. Identity

- Tier: basic.
- Capabilities: engineering.
- Protocol: the workspace with command execution (`workspace-basic`); one session; fixed budget track, 300,000 tokens per task (the last v1 configuration, `experiments/budget-pilot-2026-10/engineering.eval.json`).
- Primary score: resolved (all 22 acceptance checks pass).

## 2. What it measures

Building a small command-line tool from an empty directory against a precise written contract: CSV parsing with its edge cases (quoted multiline fields, BOMs, physical line numbers), typed validation with stable error ordering, an exact JSON-lines output protocol, and all-or-nothing, idempotent writes to SQLite.

## 3. What it does not measure

- Working in an existing code base, or design under ambiguity: the contract fixes every interface.
- Algorithmic difficulty: nothing is hard to compute.
- Speed or style: time and tokens are reported, not scored; the README is not graded.

## 4. Where the difficulty lies

Reliability, not depth. Each rule is stated; the work is following all of them at once without slips: the record index against the physical line where a multiline record ends, error order by (record, field), the original cell text in `value`, counts by code, a dry run that never creates a database, and apply that writes nothing when any record fails. Strong models resolved most trials in v1 (glm-5.3 3/3, gpt-6-luna 2/3 at 0.3.2); a slip on one rule is what separates them.

## 5. Cheapest shortcut

- An empty or crashing script, or no script: 0/22 (the targeted mutants pass 0–21 of 22 and are all rejected).
- Always exiting 0, or splitting lines naively: 7/22 and 5/22.
- Reading the hidden fixtures: they stay evaluator-side; candidate code runs in the sandbox without the package.

## 6. Anchors and headroom

No metric anchors: a contract task with a resolved headline. Headroom is small by design (basic tier): it catches regressions in careful contract-following.

## 7. Source, licence and provenance

Original project design and fixtures (`metadata.json` lists the domain references consulted: csvkit, Python's csv and sqlite3 documentation); no code or data copied. Exposure: private to runs.

## 8. Task contract and grading

- The model receives `instruction.md` and `public/` (a schema and sample CSVs) and delivers `import_validator.py`.
- 22 critical checks: one per hidden case (output protocol, fatal codes, validation codes, line numbers, apply semantics) and idempotency, each run in the sandbox with a 5-second limit and a 200 KB output cap.
- Score model: one group `acceptance` (rule fraction, critical); resolved when every check passes; diagnostic = the share passed.
- No delivery fails every check (grader 1.2.0); before, the grader refused the request, which would have made a non-delivery unscored.
- Equivalent solutions: any implementation; only behaviour is checked. Reference implementations A and B differ in structure and both pass.

## 9. Splits and size

One task (no items): split dev, structure group `package:eng-001`. It has been run and inspected in v1, so it is dev only; as a basic family it has no validation or holdout split.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: references A and B 22/22, also A with zero-count codes | `python3 private/acceptance.py --self-calibrate`, `logs/self-calibration-0.3.2-grader-1.2.0.log` |
| Null agent | pass: no delivery 0/22, graded (grader 1.2.0) | self-calibration; the basic suite smoke |
| Mutants | pass: five targeted mutants rejected | self-calibration |
| Alternative valid solutions | pass: two independent references | self-calibration |
| Adversarial | pass: candidate code runs in the sandbox, without the package or the network | grader 1.1.0 onwards |
| Coverage invariant | n/a | — |
| Global end state | covered by the apply checks (all-or-nothing, idempotency) | — |
| Noise | n/a: per-process time limits only, generous (5 s) | — |
| Determinism | pass: repeated reference runs agree | self-calibration |

## 11. Budget

300,000 tokens per task (the v1 budget pilot); strong models finished within it.

## 12. History

- 0.2.0–0.3.2: see `calibration.md`.
- Grader 1.2.0 (2026-10-24): a missing deliverable fails every check instead of being refused; manifest v2. The 0.3.2 trials re-graded (every one had delivered, so their verdicts are unchanged).
