# Project Handoff

Updated 2026-10-13.

## Current state

The repository contains a Pi Agent evaluation harness with single-run and continuous-trajectory execution, versioned task packages, trusted graders, tool evidence, snapshot recovery, append-only regrading, and aggregate reports. The current focus is reliable single-model evaluation; agent and harness comparisons come later.

M1, M2, M2L, and the scoped M2R reliability work have offline implementation evidence for earlier task versions. On 2026-10-13 all six manifest packages were re-pinned to new versions because their task text had changed after calibration; see [PLAN-004](plans/PLAN-004-model-evaluation-baseline.md). The runtime is pinned in `environment.yml`, and recalibration under it passed for every package except eng-004, whose baseline is missing. PLAN-004 phase 3 is complete: candidate sandboxing, per-trial clones, objective verdicts with human review, plan schema 3, batch containment, repetitions and per-task reports, and a live provider check.

The only live model requests so far are the small provider checks of 2026-10-14. Existing calibration logs are task-specific development evidence, not model capability results.

## Key files

- [Root README](../README.md): setup and command entry points
- [Evaluation design](design/V1_EVALUATION.md): core protocol
- [Implementation contracts](design/IMPLEMENTATION_CONTRACTS.md): package, grader, and recovery behavior
- [Long-horizon engineering design](design/LONG_HORIZON_ENGINEERING.md): continuous five-stage task
- [Current plan](plans/PLAN-004-model-evaluation-baseline.md): decisions, phases, and remaining gates

## Next steps

1. Choose the second pilot model: wait for the AliPlan quota reset (2026-10-19 16:00 UTC) and rerun `npm run provider-check`, or check a replacement. See the [provider check](reviews/2026-10-14-provider-check.md).
2. Run the pilot (PLAN-004 phase 4) with a batch token ceiling, then set budgets and freeze the first task set.
3. Rebuild the eng-004 baseline as a project-owned bundle; the previously pinned commit is unavailable.
4. Limit conclusions to the observed task versions, models, prompts, tools, and budgets.

## Operating rules

- Run `python3 scripts/task_packages.py check` after changing anything under `task-library/`; use `rehash` only together with a task version bump and a calibration note.
- Keep the pinned ENG-005 baseline in `baseline.bundle`; `npm ci` restores the local Git checkout from this bundle.
- Do not commit `.env` or other credential files.
- Use `--validate-only` for plan preflight when no API call is intended.
- Treat task fixtures as test inputs and preserve their pinned content and commits.
