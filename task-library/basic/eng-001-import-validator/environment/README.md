# eng-001 Runtime and Execution Plan

## Fixed environment

The task requires Python 3.13 and the standard library; SQLite is provided through sqlite3. Historical calibration used the direct interpreter at C:\Program Files\LibreOffice\program\python-core-3.13.15\bin\python.exe (3.13.15). The PATH python was Anaconda 3.12.4 and did not meet the task requirement. The manifest checks the direct interpreter before credential loading or model calls.

The grader starts the candidate using sys.executable. A temporary candidate directory contains only the entry point, a generic schema, generic input, and any database the candidate creates. Private fixture paths are not passed through argv or cwd. No third-party package, network installation, or external database is used.

## Flow

1. The candidate receives instruction.md and public/ and builds import_validator.py in an empty workspace.
2. The Harness exports a read-only candidate snapshot and hashes each file and the manifest.
3. The external Python grader receives request.json; private fixtures and the oracle remain in the trusted package.
4. Each check runs the candidate CLI and validates its exit code, strict JSONL, and database state. Stored evidence contains check IDs, pass/fail, and stable reason codes.
5. The grader returns structured result.json; the Harness validates identity, version, checks, and evidence references before writing a separate score-run directory.

Each candidate process is limited to five seconds and 200 KB combined stdout/stderr. The planned total grader timeout is 180 seconds and grader log limit is 20 KB. A small pilot must set any final budget.

## Commands

From the repository root:

- Run Python calibration with the pinned interpreter and private/acceptance.py --self-calibrate.
- Run the Harness preflight with npm run harness -- --plan examples/eng-001.eval.json --validate-only.

The host tsx launcher encountered uv_os_get_passwd ENOMEM; the equivalent temporary compiled Node command passed. This is a host launcher issue, not a task-runtime result.

## Limits

No real model API has been used. The evaluator runs as a trusted local process. Path restrictions and output limits are not OS isolation; a candidate may try to access host-readable resources or spawn child processes. Review isolation and cost separately before production evaluation.
