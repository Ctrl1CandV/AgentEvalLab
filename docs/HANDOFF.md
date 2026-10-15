# Project Handoff

Updated 2026-10-15.

## Current state

The repository contains a Pi Agent evaluation harness with single-run and continuous-trajectory execution, versioned task packages, trusted graders, tool evidence, snapshot recovery, append-only regrading, and aggregate reports. The current focus is reliable single-model evaluation; agent and harness comparisons come later.

M1, M2, M2L, and the scoped M2R reliability work have offline implementation evidence for earlier task versions. On 2026-10-13 all six manifest packages were re-pinned to new versions because their task text had changed after calibration; see [PLAN-004](plans/PLAN-004-model-evaluation-baseline.md). The runtime is pinned in `environment.yml`, and recalibration under it passed for every package except eng-004, whose baseline is missing. PLAN-004 phase 3 is complete: candidate sandboxing, per-trial clones, objective verdicts with human review, plan schema 3, batch containment, repetitions and per-task reports, and a live provider check.

The 2026-10 pilot ran on 2026-10-14 and 2026-10-15; see the [pilot results](reviews/2026-10-15-pilot-results.md). The reasoning and tool batches are complete. The engineering batch stopped after one trial per model, because one glm-5.3-flash trial used 2.7M tokens. The pilot found and fixed six defects, among them a tool-001 grader that could not credit any read and budget stops that were left out of pass rates. Pilot results calibrate budgets; they are not model capability results.

## Key files

- [Root README](../README.md): setup and command entry points
- [Evaluation design](design/V1_EVALUATION.md): core protocol
- [Implementation contracts](design/IMPLEMENTATION_CONTRACTS.md): package, grader, and recovery behavior
- [Long-horizon engineering design](design/LONG_HORIZON_ENGINEERING.md): continuous five-stage task
- [Current plan](plans/PLAN-004-model-evaluation-baseline.md): decisions, phases, and remaining gates

## Next steps

1. Get the user's decisions listed in the [pilot results](reviews/2026-10-15-pilot-results.md#decisions-for-the-user): the tool-001 Q3 rule, more glm engineering trials, the eng-001 per-call output cap, and how batch ceilings count cache reads.
2. Complete the engineering trials as decided, then set per-task budgets and freeze the first task set.
3. Rebuild the eng-004 baseline as a project-owned bundle; the previously pinned commit is unavailable.
4. Limit conclusions to the observed task versions, models, prompts, tools, and budgets.

## Operating rules

- Run `python3 scripts/task_packages.py check` after changing anything under `task-library/`; use `rehash` only together with a task version bump and a calibration note.
- Keep the pinned ENG-005 baseline in `baseline.bundle`; `npm ci` restores the local Git checkout from this bundle.
- Do not commit `.env` or other credential files.
- Use `--validate-only` for plan preflight when no API call is intended.
- Treat task fixtures as test inputs and preserve their pinned content and commits.
