# Project Handoff

Updated 2026-10-10.

## Current state

The repository contains a Pi Agent evaluation harness with single-run and continuous-trajectory execution, versioned task packages, trusted graders, tool evidence, snapshot recovery, append-only regrading, and aggregate reports.

M1, M2, M2L, and the scoped M2R reliability work have offline implementation evidence. The maintained task set covers engineering, reasoning, tool use, and visual implementation.

No live model or evaluator API calls were made during this repository migration. Existing calibration logs are task-specific development evidence, not model capability results.

## Key files

- [Root README](../README.md): setup and command entry points
- [Evaluation design](design/V1_EVALUATION.md): core protocol
- [Implementation contracts](design/IMPLEMENTATION_CONTRACTS.md): package, grader, and recovery behavior
- [Long-horizon engineering design](design/LONG_HORIZON_ENGINEERING.md): continuous five-stage task
- [Current plan](plans/PLAN-003-v1-evaluation.md): completed work and remaining gates

## Next steps

1. Review English task instructions and confirm the translated contracts preserve the intended cases.
2. Complete the visual rendering and human-review workflow when its rendering environment is available.
3. Before a live model batch, specify providers, request caps, output limits, timeouts, and a cost ceiling.
4. Limit conclusions to the observed task versions, models, prompts, tools, and budgets.

## Operating rules

- Keep the pinned ENG-005 baseline in `baseline.bundle`; `npm ci` restores the local Git checkout from this bundle.
- Do not commit `.env` or other credential files.
- Use `--validate-only` for plan preflight when no API call is intended.
- Treat task fixtures as test inputs and preserve their pinned content and commits.
