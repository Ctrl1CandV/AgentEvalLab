# Project Handoff

Updated 2026-10-20.

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

1. Follow [PLAN-005](plans/PLAN-005-discriminating-attributable-evaluation.md). As of 2026-10-19:
   - partial-credit scoring with a 20% format deduction is done, and budgets are stated to the model with reminders at 50%, 75% and 90%;
   - [Task Set v2](design/TASK_SET_V2.md) is approved. R1, R3, T1, E2 and vis-001 model judging are built, and their first calibration is in the [calibration review](reviews/2026-10-19-task-set-v2-calibration.md);
   - the deepseek key was replaced on 2026-10-19 and every missing deepseek run is complete; overall scores per model are in the review's last addendum;
   - later that day:
     - R1 was retired from the comparison set;
     - T1 0.2.0 added L5;
     - E2 0.3.0 added `ledger` and `recur`;
     - E4 0.1.0 was built and saturated.
     - Runs without deepseek are recorded in the experiment READMEs.
   - on 2026-10-20 (see the [hardening round](reviews/2026-10-20-hardening-round.md)):
     - the user's target is 30–80% for every family. Two MiMo V2.6 models were added at their default thinking;
     - hardening by adding detail failed: T2 0.2.0, E3 eng-005 0.3.0, E4 0.2.0 and 0.3.0 (codec) and T1 L7 stayed above 90% for the strong models;
     - what separates them is a ladder: R3 L5–L7 by puzzle size, and two continuous engineering items, E2 `routes` (optimisation, scored against a best-known cost) and E4 `speedup` (time against an optimised reference);
     - the harness now stops only the failing provider, grades budget-stopped trajectory stages, continues a session past a transient mid-stream error, and lets only the task budget stop a model (responses of 131,072 tokens and 524,288 characters).
   - results and the open decisions are in the [hardening round](reviews/2026-10-20-hardening-round.md): R3, E2 `routes` and (offline) E4 `speedup` 0.4.1 spread the models; T1 L7 still saturates the top two; E3 and T2 need a decision between a ladder and keeping them as reliability families.
   - next: the user's decisions on E3 and T2; an E4 0.4.1 speedup run; resume every new item for glm, step and luna once the airy.work relay has balance.

   Background: after the pilot the user set its principles: deductions must be attributable to the model; a recoverable format slip is deducted, not failed; there is one generous budget per task, stated to the model; thinking runs at a middle level; and the tasks must become harder. The user settled its open decisions on 2026-10-16.
2. The pilot's own decision list is superseded by PLAN-005.
3. eng-004 0.3.0 has a rebuilt baseline (`private/baseline-source`, `private/build_baseline.py`); it is the starting point for E1.
4. Limit conclusions to the observed task versions, models, prompts, tools, and budgets.

## Operating rules

- Run `python3 scripts/task_packages.py check` after changing anything under `task-library/`, calibration.md and rubric.md included (manifests pin them); use `rehash` only together with a task version bump and a calibration note.
- Keep the pinned ENG-005 and ENG-004 baselines in their packages' `baseline.bundle`; `npm ci` (and every `npm test` or `npm run harness`) restores the local Git checkouts through `scripts/prepare-baselines.mjs`.
- Do not commit `.env` or other credential files.
- Use `--validate-only` for plan preflight when no API call is intended.
- Treat task fixtures as test inputs and preserve their pinned content and commits.
- Never delete `evaluation-*` workspace directories while a run is active; they are live trial workspaces.
- A run is pinned to its Git commit. To resume one after later commits, use `git worktree add --detach <commit>` with `node_modules`, `.env` and `runs` symlinked in.
