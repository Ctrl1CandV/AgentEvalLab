# Project Handoff

Updated 2026-10-21.

## Current state

The repository contains a Pi Agent evaluation harness with single-run and continuous-trajectory execution, versioned task packages, trusted graders, tool evidence, snapshot recovery, append-only regrading, and aggregate reports. The current focus is reliable single-model evaluation; agent and harness comparisons come later.

M1, M2, M2L, and the scoped M2R reliability work have offline implementation evidence for earlier task versions. On 2026-10-13 all six manifest packages were re-pinned to new versions because their task text had changed after calibration; see [PLAN-004](plans/PLAN-004-model-evaluation-baseline.md). The runtime is pinned in `environment.yml`, and recalibration under it passed for every package; eng-004's missing baseline was rebuilt as a project-owned bundle on 2026-10-20. PLAN-004 phase 3 is complete: candidate sandboxing, per-trial clones, objective verdicts with human review, plan schema 3, batch containment, repetitions and per-task reports, and a live provider check.

The 2026-10 pilot ran in two rounds on 2026-10-14 and 2026-10-15: luna-medium with glm-5.3-flash, then with glm-5.3-max. See the [pilot results](reviews/2026-10-15-pilot-results.md). Token use is counted in fixed units without prices and capped per trial and per model. The pilot found and fixed eight defects, among them a tool-001 grader that could not credit any read, budget stops left out of pass rates, and an unstated eng-001 output rule. Pilot results calibrate budgets; they are not model capability results.

## Key files

- [Root README](../README.md): setup and command entry points
- [Evaluation design](design/V1_EVALUATION.md): core protocol
- [Implementation contracts](design/IMPLEMENTATION_CONTRACTS.md): package, grader, and recovery behavior
- [Long-horizon engineering design](design/LONG_HORIZON_ENGINEERING.md): continuous five-stage task
- [Current plan](plans/PLAN-004-model-evaluation-baseline.md): decisions, phases, and remaining gates

## Next steps

1. **Follow [PLAN-006](plans/PLAN-006-suite-runner-and-hardening-round-2.md)** (approved by the user on 2026-10-21):
   - **Part A, first:** a one-command suite runner. Choose models, run every family from a frozen worktree, get one report.
   - **Part B, then the hardening round:** B1 E4 (a lossless-compression item, plus a formal speedup 0.4.1 run), B2 T1 (a depth ladder), B3 T2 0.3.0 (optimisation within the policy) and B4 E3 (a scale stage with speed tiers).
   - **Target:** deepseek-flash at about 80% or below on most families.
2. **Dev rounds** use deepseek-flash plus about two references (at most one from the SuperAI relay), one repetition, and only the families being changed. Launch once and accept from the report when it ends; do not watch runs.
3. **History.**
   - [PLAN-005](plans/PLAN-005-discriminating-attributable-evaluation.md) set the scoring and budget rules: attributable deductions, a 20% format deduction, stated budgets with reminders, middle thinking and harder tasks.
   - The [calibration review](reviews/2026-10-19-task-set-v2-calibration.md) and the [hardening round](reviews/2026-10-20-hardening-round.md) hold the results so far. Adding detail did not harden T2, E3, E4 or T1. Ladders did: R3 by grid size, E2 `routes` against a best-known cost, and E4 `speedup` against a reference time.
4. **eng-004 0.3.0** has a rebuilt baseline (`private/baseline-source`, `private/build_baseline.py`); it is the starting point for E1, which is not scheduled yet.
5. **Limit conclusions** to the observed task versions, models, prompts, tools and budgets. 2026-10-20's numbers come from development runs of one or two repetitions, not from the evaluation itself.

## Operating rules

- Run `python3 scripts/task_packages.py check` after changing anything under `task-library/`, calibration.md and rubric.md included (manifests pin them); use `rehash` only together with a task version bump and a calibration note.
- Dev rounds: deepseek-flash plus about two references, at most one from the SuperAI relay (airy.work: glm, step, luna); no pro models; one repetition. Run preflight before launching, and accept from the report after the completion notification.
- Keep the pinned ENG-005 and ENG-004 baselines in their packages' `baseline.bundle`; `npm ci` (and every `npm test` or `npm run harness`) restores the local Git checkouts through `scripts/prepare-baselines.mjs`.
- Do not commit `.env` or other credential files.
- Use `--validate-only` for plan preflight when no API call is intended.
- Treat task fixtures as test inputs and preserve their pinned content and commits.
- Never delete `evaluation-*` workspace directories while a run is active; they are live trial workspaces.
- A run is pinned to its Git commit. To resume one after later commits, use `git worktree add --detach <commit>` with `node_modules`, `.env` and `runs` symlinked in.
