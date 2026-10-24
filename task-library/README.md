# Task Library

Packages sit in tier directories (PLAN-007 WP2.1, `docs/design/v2/TASK_LIBRARY.md` §1, §6):

- `basic/`: reliability families; high scores are expected and informative (T1, T2, E3 eng-005, E4, E2, eng-001, eng-004).
- `core/`: the main discrimination (R3; AR, ER, AP and VIS v2 follow in Phase 3).
- `frontier/`: high-ceiling families anchored outside the project (AE, ALE-Bench heuristic contests).
- `retired/`: history only; no v2 suite uses them (t2-service-desk, r1-rostering, rsn-001, rsn-002, tool-001, vis-001, and eng-002 and eng-003, which never had manifests).
- `research/`: exploratory prototypes and historical evidence.

Each package directory holds the package (manifest, instruction, `public/`, `private/`, `items/` or `stages/`), and beside it the task card (`task-card.md`, `candidate-task-card.md` where the candidate card differed), the capability card (`card.md`, hashed in a v2 manifest), the calibration record and its logs. Moving a package changed its path, not its id or version: current plans were re-pinned to the new paths, historical plans keep the old ones and stay readable through their runs' frozen worktrees. `_CONVENTIONS.md` holds the package conventions; the former candidate index and the math and physics review are in `docs/archive/task-library/`.

Read each package manifest and calibration record before using a task. Candidate status is not evidence that a task is ready for model comparison.
