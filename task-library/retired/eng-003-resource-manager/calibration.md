# Calibration Record: eng-003 Local Resource Manager v0.1.0

Family: eng-stateful-interactive. This is a development candidate, not a frozen task. The complete contract is in instruction.md.

## Historical offline results

The reference ResourceStore passed 14/14 deterministic functional scenarios using an injected clock. Coverage included add validation, partial edit, missing IDs, delete, filtering, persistence, JSON/CSV round trips, merge, replace, all-or-nothing import, duplicate IDs, malformed payloads, CSV import, and corrupt-store recovery.

An HTTP smoke check passed: POST /resources returned 201, GET /resources returned one record, and GET / served the page. Three flawed implementations were rejected: missing field validation (11/14), partial import writes (10/14), and an empty implementation (0/14). Repeated runs were consistent.

## Evaluation dimensions

Functionality is automated and black-box. Engineering quality is reviewed by people. Visual quality is also reviewed by people; automated rendering, responsive checks, and full accessibility scans are blocked without a browser backend.

## Open limits

No real model run or budget pilot has been completed. Real write-crash atomicity remains unverified. Status: not frozen; visual review, model execution, and budget selection remain future work.
