# qwen-round3 Independent Verification Report

Date: 2026-09-30. This report summarizes offline engineering and visual-task research. No credentials were read, no paid model was called, no upload or Git push occurred, and all prototypes used copied reference implementations in isolated temporary directories. Every result is tied to a local artifact or log; blocked work is identified rather than inferred.

## Engineering negative cases

### eng-001 CSV import validator

The independent suite passed 10/10 against the reference and rejected seven targeted mutants. It checks complete database rows, upsert behavior, unique conflicts, all-or-nothing writes, dry-run integrity, original cell values, physical line numbers, output order, exact summaries, and fatal-error shape.

The previous acceptance approach could miss a wrong non-key database value and unsorted errors because it checked only row counts/IDs and sorted both sides before comparison. The independent suite detects both gaps. See eng-001-negatives/ and its self-calibration log.

### eng-003 submitted server

The prototype separately imports the submitted service and starts the submitted server. The good submission passed store and HTTP checks. A submission with a working store but no server and a server with a missing POST route were rejected. Process cleanup required both termination and port rebindability. Browser UI review remains blocked without a rendering backend.

### eng-002 interruption recovery

A deterministic black-box probe used 5,000 inputs and killed the process after observing 50 processed lines. The journal had 164 completed entries at interruption. Published outputs were complete, the journal did not lead the outputs, no .part files remained, and resume reached the correct 5,000-item state.

A black-box kill during a single output's partial write could not be reproduced reliably. That requires a white-box fault injection or a much larger single output; random sleeps are not reliable evidence.

## Visual checker boundary

Two targeted frontend mutations exposed limitations in the static checker. It rejected a valid wrapping label, and it accepted a declared palette even though a hard-coded hero color had contrast of about 1.35:1. Static checks are structural signals, not proof of computed contrast or behavior. Browser rendering and human review are needed.

## Source and license review

Task fixtures and reference materials were authored for this project; no third-party source code or prose was copied. External license details were not rechecked online in this round. Exact terms for any future third-party task material must be verified before use. See license-source-audit/audit.md.

## Candidate precedents

The fourth-round notes record public engineering-tool precedents for dependency management, dry-run validation, and CSV export. They are design references only, not copied task content. See candidates-round4/precedents.md.

## Limits

These offline prototypes assess checker behavior and contract boundaries, not model capability, benchmark validity, or production-provider behavior. No model API was called.
