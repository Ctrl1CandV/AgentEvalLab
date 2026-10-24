# Calibration Record: eng-001 Import Validator v0.2.0

Family: eng-data-validation. This is a development-calibration task, not a frozen evaluation set. The fixed contract is in instruction.md; weights and draft human criteria are in rubric.md.

## Current implementation

- The manifest fixes 22 check IDs, the Python grader, and full SHA-256 hashes for task files. schemaVersion 2 is intended to pin the manifest hash.
- Preflight checks task hashes and the direct Python 3.13.15 interpreter before loading credentials.
- The candidate workspace receives only instruction.md and public/. Hidden oracles, fixtures, reference implementations, and graders stay private.
- A request.json/result.json protocol separates candidate failures from grader failures.
- Checks strictly validate JSONL shape and ordering, duplicate errors, record indices, physical line numbers, original values, codes, and summary counts.
- Apply checks SQLite columns, types, primary and unique constraints, every typed row, all-or-nothing failure, dry-run behavior, and idempotence.
- Each candidate process is capped at five seconds and 200 KB combined stdout/stderr. The grader timeout is fixed by the plan.

## Offline calibration evidence

Python 3.13.15 and the standard library with SQLite were used. Three independent self-calibration runs returned exit code 0 and were repeatable. Reference implementations A and B each passed 22/22. The targeted implementations naive_split, always_exit0, dryrun_writes, insert_only, and empty scored 5/22, 7/22, 20/22, 21/22, and 0/22 respectively and were rejected.

The Pi integration exercised a synthetic offline loop using injected streams and a synthetic key. It made no provider API calls. Type checking and offline Node checks were recorded as passing in the historical calibration. The default tsx launcher encountered a host uv_os_get_passwd ENOMEM issue; a temporary compiled Node CLI passed validate-only.

## Limits and status

No real model requests, capability, cost, speed, or production routing have been measured. The maintenance-change task and budget pilot remain pending. The host execution is not a strong OS sandbox and does not guarantee termination of child process trees. Status: not frozen; formal measurement, budget selection, and user confirmation remain separate gates.


## Version 0.3.0 (2026-10-13)

The English task material in this repository is the canonical baseline; there is no earlier source text to reconcile against. Version 0.2.0 recorded digests for earlier bytes of the instruction and documentation files, so the package no longer passed preflight. This version re-pins every file digest and resolves the grader and public checkers as `python3` from PATH (Python 3.13 required) instead of a host-specific interpreter path. Grader logic is unchanged; only the TASK_VERSION constant in private/acceptance.py changed.

Calibration results above were recorded against version 0.2.0 and remain historical. Recalibration under 0.3.0 is pending a provisioned Node.js 22 and Python 3.13 environment.


## Version 0.3.1 (2026-10-14)

Candidate code started by the grader now runs through the harness sandbox launcher (`scripts/sandbox_exec.py`, bubblewrap): only the candidate's working directory is writable, and the host home directory, the task package (including `private/`), and the network are unreachable. The launcher path comes from the grader request's `sandbox` field, which the request validator now requires; when a plan opts into `"isolation": "host"`, the field is null and candidates run as before. The task contract and check logic are unchanged; the grader version is now 1.1.0.

Recalibration under 0.3.1 is recorded in `logs/self-calibration-0.3.1.log`.


## Version 0.3.2 (2026-10-15)

In the 2026-10 pilot, one gpt-6-luna trial failed 14 of 22 checks with `output_protocol_invalid`. Its summary line listed every error code, with zero counts for codes that did not occur (`"by_code": {"missing_required": 0, ...}`). Grader 1.1.0 required every `by_code` count to be at least 1. The instruction gives `by_code` only as `{<code>: <int>}` and does not say whether absent codes are omitted; the public example's `{}` for clean input is consistent with either reading. The grader had imposed an unstated requirement, and a zero count states the same fact as an absent code.

Grader 1.1.1 accepts zero counts and treats them as absent; negative counts are still invalid. Self-calibration adds a copy of reference A that lists all codes with zero counts; it passes 22/22, and the five faulty implementations score as before (5, 7, 20, 21 and 0 of 22). The pilot trial's submission scores 22/22 under 1.1.1. See `logs/self-calibration-0.3.2.log`.

## Grader 1.2.0 and manifest v2 (2026-10-24, PLAN-007 WP2.2)

The task stays 0.3.2. A missing `import_validator.py` used to make the grader refuse the request (`GRADER_REQUEST_INVALID`), so a trial without a delivery was an error, not a failure; the v2 suite's null-agent smoke caught it. Grader 1.2.0 grades it: every check fails with `missing_deliverable`. The self-calibration adds that case (`logs/self-calibration-0.3.2-grader-1.2.0.log`: references 22/22, mutants rejected, no delivery 0/22). The manifest moves to v2 with the capability card (`card.md`), one critical group `acceptance` (rule fraction) and the task placement (dev, `package:eng-001`). The 0.3.2 trials of `runs/0be84fe0-…` were re-graded under grader 1.2.0; all had delivered, so their verdicts are unchanged, and each now has a v2 outcome.
