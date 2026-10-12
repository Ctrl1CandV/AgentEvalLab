# Public Scoring Rubric: eng-003

Functionality, engineering quality, and visual design are evaluated separately. Functionality uses automated black-box checks; engineering and design use human review. Automated visual rendering is currently blocked.

## Functionality

The historical reference passed 14/14 functional scenarios and an HTTP smoke check. Critical requirements include:

- Form validation, successful add, tag trimming/deduplication/limits, and no state change on invalid input.
- Partial edit, missing-id behavior, deletion, and repeated-delete behavior.
- Numeric-id ordering and tag/text filtering.
- Persistence across reload, atomic writes, and corrupt-store recovery to an empty store with a .corrupt backup and recovery flag.
- JSON/CSV export, round trips, merge and replace import, duplicate-id detection, and all-or-nothing import.
- HTTP POST, list, and homepage smoke checks.

## Engineering review

Review service/server/frontend separation, duplication, hard-coded assumptions, exception handling, and README accuracy. Rate modification effort as ready to use, minor edits, restructuring, or rewrite. Ties and inconclusive results are allowed.

## Visual review

Review clarity, completeness, usability, form states, and responsive desktop/phone layouts. Visual originality is judged through anonymous pairwise human review, not screenshot similarity or a single model score. Browser rendering and accessibility checks are blocked pending a rendering backend.

## Acceptable implementations and exclusions

Internal structure, route implementation, frontend technology, and deterministic ID allocation details are unrestricted if the fixed contract is met. Authentication, multi-user support, deployment, performance, and code-line count are not scored.
