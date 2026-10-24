# Task: CSV Import Validator (eng-001)

Build a command-line tool from an empty directory. It reads a CSV file and a schema, validates all records in dry-run mode, or applies the records to SQLite. All acceptance-relevant interfaces and semantics below are fixed; internal design is yours.

## Runtime

- Python 3.13, standard library only (including csv, sqlite3, json, argparse, datetime, re, and math). No third-party dependencies.
- Deliver a standalone UTF-8 script named import_validator.py at the submission root.

## Command line

    python <script> --schema <schema.json> --input <data.csv> [--db <out.sqlite>] [--encoding utf-8|utf-8-sig] (--dry-run | --apply)

- Exactly one of --dry-run and --apply is required.
- --apply requires --db. --db is optional for --dry-run, and dry-run must never create or modify a database file.
- --encoding defaults to utf-8; utf-8-sig is supported for BOM-prefixed input.

## Exit codes

- 0: dry-run has no validation errors, or apply succeeds.
- 1: one or more record-level validation errors. If any validation error exists, apply writes nothing.
- 2: fatal usage, file, schema, header, or CSV-structure error.

## Schema

    {
      "primary_key": "<column_name>",
      "columns": [
        {"name": "id", "type": "int", "required": true, "unique": true},
        {"name": "email", "type": "str", "required": true, "unique": true, "maxlength": 254},
        {"name": "age", "type": "int", "required": false, "min": 0, "max": 150},
        {"name": "signup_date", "type": "date", "required": false, "format": "YYYY-MM-DD"},
        {"name": "active", "type": "bool", "required": false},
        {"name": "score", "type": "float", "required": false}
      ]
    }

- Supported types: int, str, float, date, bool. required and unique are optional and default to false. Numeric columns may define min/max; str columns may define maxlength.
- Invalid schema (invalid JSON, missing columns, unknown type, duplicate column names, or primary_key not naming a column) exits 2 with code=schema_error.

## Output protocol

- Emit one JSON line per record-level error to stdout:
  {"record": <int>, "line": <int>, "field": <str>, "code": <str>, "value": <str|null>}
  - record is a zero-based data-record index, excluding the header.
  - line is the one-based physical line where that record ends; the header is line 1. A quoted multiline field may make line greater than record+2.
  - code is one of missing_required, type_mismatch, constraint, unique_violation.
  - value is the original cell text, possibly an empty string.
- Emit errors in stable ascending (record, field) order.
- End with one summary line:
  {"summary": {"ok": <bool>, "records": <int>, "errors": <int>, "by_code": {<code>: <int>}}}
- Fatal errors (exit 2) emit exactly one line:
  {"error": {"code": <str>, "message": <str>}}
  Do not emit a summary for fatal errors. Fatal codes are usage, schema_error, empty_input, header_mismatch, duplicate_header, parse_error, db_error.

## Parsing and validation rules

- The first CSV row is the header. Its column-name set must exactly equal the schema column-name set; order may differ and records are matched by name.
  - Duplicate header names exit 2 with duplicate_header.
  - Missing or extra columns exit 2 with header_mismatch.
- A zero-byte file with no header exits 2 with empty_input. A header-only file is valid: records=0 and exit 0.
- CSV structural errors, such as an unclosed quote or a data row with a different field count, exit 2 with parse_error. Support RFC 4180 quoted commas, quoted newlines, and escaped quotes ("").
- A cell that is empty after trimming whitespace is NULL. If the column is required, emit missing_required; otherwise store NULL without an error.
- Before parsing, trim surrounding whitespace for non-str columns. Preserve str values exactly.
  - int must match ^[+-]?\d+$; otherwise type_mismatch.
  - float must parse with float(), but nan, inf, -inf, +inf, infinity, and -infinity (case-insensitive) are rejected as type_mismatch.
  - bool accepts true/1 and false/0, case-insensitive; all other values are type_mismatch.
  - date must match ^\d{4}-\d{2}-\d{2}$ and be a valid ISO calendar date; otherwise type_mismatch.
  - str accepts arbitrary text.
  - Numeric min/max and str maxlength violations produce constraint. maxlength uses the original, untrimmed str value.
- For every unique=true column, including the primary key:
  - A repeated non-empty value in the same input produces unique_violation on the later record.
  - During apply, a non-primary unique value matching a row with a different primary key produces unique_violation. Matching the existing row with the same primary key is an update and is not an error.

## Apply semantics

- Use a SQLite table named records. Map int to INTEGER, float to REAL, str to TEXT, bool to INTEGER (0/1), and date to TEXT (ISO). The primary key is PRIMARY KEY; other unique columns have UNIQUE constraints.
- All or nothing: validate every record first. Any record-level error exits 1 and must not create or modify the database. Write only if all records pass.
- Upsert by primary key (INSERT ... ON CONFLICT(<pk>) DO UPDATE ... or equivalent). Applying the same input repeatedly must leave the same rows and values, with no duplicates.

## Deliverables

1. A runnable script meeting this contract.
2. README.md documenting usage, exit codes, error protocol, and assumptions about unspecified details.
3. Optional self-checks using public examples are recommended.

## Public materials

- public/schema.json: example schema in the format above.
- public/data_clean.csv: three valid records.
- public/expected_dry_run_clean.jsonl: expected dry-run summary for data_clean.csv.

## Out of scope

Database selection and performance, large-scale data, UI, network access, and third-party libraries are out of scope. Internal implementation is unrestricted.
