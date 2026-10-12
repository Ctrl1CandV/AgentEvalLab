# Scoring Rubric: eng-001

This is a development acceptance contract, not evidence that the task is frozen or that model capability has been measured. Functional scoring aggregates requirements rather than weighting all 22 checks equally.

## Automated critical gates

The private acceptance runner starts the submitted import_validator.py. Oracle data and fixtures are not placed in the candidate workspace. Candidate functional failures are valid failures; Python grader crashes, timeouts, and malformed results are evaluator errors.

- Input parsing: RFC 4180 quoting, commas, line breaks, escaped quotes, and BOM handling.
- Error protocol: exact object fields, record and field ordering, duplicate errors, error codes, original values, record indices, and physical end lines.
- Summary: exact ok, records, errors, and by_code values; no extra text, blank lines, invalid JSON, or extra fields.
- Boundaries: empty input, header-only input, missing/extra/duplicate headers, malformed CSV, and invalid schema.
- Types and constraints: required values, types, finite floats, dates, min/max/maxlength, and uniqueness.
- Apply: invalid batches do not write; successful SQLite schema, column order, declared types, primary/unique constraints, and typed rows match the contract.
- Idempotence: repeated apply leaves the complete database state unchanged.
- Dry-run: cannot create a database.
- Resource limits: each candidate check is capped at five seconds and 200 KB combined output; exceeding a limit fails that candidate check.

Historical self-calibration: two structurally different reference implementations each passed 22/22. Targeted bad implementations scored 5/22, 7/22, 20/22, 21/22, and 0/22 and were rejected. This only describes checker behavior on those examples; it does not establish model performance.

## Human review draft

Potential maintainability criteria include separation of responsibilities, duplication, hard-coded fixture answers, readable error handling, README accuracy, and change size for a fixed maintenance task. Score the initial implementation separately from later changes. The maintenance task is not implemented yet.

Different internal designs are acceptable. Do not compare source code character by character or score database performance or choice.

## Claims not established

No real model run, maintainability-score validity, sample representativeness, or sufficient budget has been established. Formal calibration, a budget pilot, and user confirmation remain required before freezing.
