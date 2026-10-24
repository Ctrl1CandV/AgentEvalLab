# Candidate Task Card: eng-001 CSV Import Validator

## Identity

- ID: `eng-001-import-validator`
- Family: `eng-data-validation`
- Status: screening; development use; not frozen
- Primary capability: engineering from a clean workspace
- Secondary evidence: boundary reasoning and tool execution
- Source: original task design. Public fixtures are synthetic.

## User goal

Build a standalone CLI that validates CSV records against a schema and either reports errors or applies valid records to SQLite.

## Fixed contract

- Python 3.13 and the standard library only.
- Support `--schema`, `--input`, optional `--db`, `--encoding`, and exactly one of `--dry-run` or `--apply`.
- Parse RFC 4180 quoting, embedded newlines, escaped quotes, CRLF, and UTF-8 BOM input.
- Match headers to schema columns, report deterministic record-level errors, and distinguish validation failures from fatal input or schema failures.
- Dry-run must not create or modify a database. Apply validates the full input before writing and uses an idempotent primary-key upsert.
- Deliver the runnable script, dependency information, a README, and optional self-tests.

The calibrated package instruction and manifest define the exact JSON output, schema rules, fixtures, and acceptance checks.

## Evidence and limits

The package includes a trusted grader, public examples, hidden fixtures, two valid reference implementations, and targeted negative implementations. Offline calibration supports only the recorded contract and mutations. It does not establish model capability or production-scale reliability.
