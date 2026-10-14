# Project Handoff

Updated 2026-10-13.

## Current state

The repository contains a Pi Agent evaluation harness with single-run and continuous-trajectory execution, versioned task packages, trusted graders, tool evidence, snapshot recovery, append-only regrading, and aggregate reports. The current focus is reliable single-model evaluation; agent and harness comparisons come later.

M1, M2, M2L, and the scoped M2R reliability work have offline implementation evidence for earlier task versions. On 2026-10-13 all six manifest packages were re-pinned to new versions because their task text had changed after calibration; see [PLAN-004](plans/PLAN-004-model-evaluation-baseline.md). The runtime is pinned in `environment.yml`, and recalibration under it passed for every package except eng-004, whose baseline is missing.

No live model or evaluator API calls have been made. Existing calibration logs are task-specific development evidence, not model capability results.

## Key files

- [Root README](../README.md): setup and command entry points
- [Evaluation design](design/V1_EVALUATION.md): core protocol
- [Implementation contracts](design/IMPLEMENTATION_CONTRACTS.md): package, grader, and recovery behavior
- [Long-horizon engineering design](design/LONG_HORIZON_ENGINEERING.md): continuous five-stage task
- [Current plan](plans/PLAN-004-model-evaluation-baseline.md): decisions, phases, and remaining gates

## Next steps

1. Fix the pre-pilot blockers in PLAN-004 phase 3 (sandboxing, per-trial clones, objective verdicts, limits, condition fingerprint); see the [benchmark alignment review](reviews/2026-10-13-benchmark-alignment-review.md).
2. Rebuild the eng-004 baseline as a project-owned bundle; the previously pinned commit is unavailable.
3. Run the pilot with explicit request and cost caps, then freeze the first task set.
4. Limit conclusions to the observed task versions, models, prompts, tools, and budgets.

## Operating rules

- Run `python3 scripts/task_packages.py check` after changing anything under `task-library/`; use `rehash` only together with a task version bump and a calibration note.
- Keep the pinned ENG-005 baseline in `baseline.bundle`; `npm ci` restores the local Git checkout from this bundle.
- Do not commit `.env` or other credential files.
- Use `--validate-only` for plan preflight when no API call is intended.
- Treat task fixtures as test inputs and preserve their pinned content and commits.
