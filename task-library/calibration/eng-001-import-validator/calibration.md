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
