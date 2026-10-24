# Task Library

The library separates candidate task cards from calibrated packages.

- `candidates/` contains task definitions still under review.
- `calibration/` contains package inputs, trusted graders, fixtures, and calibration records.
- `frontier/` contains high-ceiling families anchored outside the project (AE, ALE-Bench heuristic contests).
- `research/` contains exploratory prototypes and historical evidence.

The v2 restructure (PLAN-007 Phase 2) moves packages into `basic/`, `core/`, `frontier/` and `retired/`; see `docs/design/v2/TASK_LIBRARY.md`.

Read each package manifest and calibration record before using a task. Candidate status is not evidence that a task is ready for model comparison.
