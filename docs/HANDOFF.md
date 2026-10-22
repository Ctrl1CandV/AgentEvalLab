# Project Handoff

Updated 2026-10-22.

## Current state

The repository contains a Pi Agent evaluation harness with single-run and continuous-trajectory execution, versioned task packages, trusted graders, tool evidence, snapshot recovery, append-only regrading, and aggregate reports. The current focus is reliable single-model evaluation; agent and harness comparisons come later.

M1, M2, M2L, and the scoped M2R reliability work have offline implementation evidence for earlier task versions. On 2026-10-13 all six manifest packages were re-pinned to new versions because their task text had changed after calibration; see [PLAN-004](plans/PLAN-004-model-evaluation-baseline.md). The runtime is pinned in `environment.yml`, and recalibration under it passed for every package; eng-004's missing baseline was rebuilt as a project-owned bundle on 2026-10-20. PLAN-004 phase 3 is complete: candidate sandboxing, per-trial clones, objective verdicts with human review, plan schema 3, batch containment, repetitions and per-task reports, and a live provider check.

The 2026-10 pilot ran in two rounds on 2026-10-14 and 2026-10-15: luna-medium with glm-5.3-flash, then with glm-5.3-max. See the [pilot results](reviews/2026-10-15-pilot-results.md). Token use is counted in fixed units without prices and capped per trial and per model. The pilot found and fixed eight defects, among them a tool-001 grader that could not credit any read, budget stops left out of pass rates, and an unstated eng-001 output rule. Pilot results calibrate budgets; they are not model capability results.

PLAN-006 was carried out on 2026-10-21/22; see the [round-2 review](reviews/2026-10-22-hardening-round-2.md).

- **Suite runner.** `npm run suite` runs every family from a frozen worktree with one report.
- **The families now in the suite:**
  - E4 0.5.0 adds `compress`, scored on a continuous scale, and a `speed-8` gate on `speedup`;
  - T1 0.5.0 has a depth ladder (D2–D8);
  - T2 0.3.0 asks for the least-cost resolution within the policy;
  - eng-005 0.4.0 (E3) adds a sixth stage, scale, and no longer credits an untouched project.
- **deepseek-flash** scores R3 72%, E2 71%, E4 85%, T1 95%, T2 95% and E3 98%. T1, T2 and E3 did not harden and await the user's decision.

## Key files

- [Root README](../README.md): setup and command entry points
- [Evaluation design](design/V1_EVALUATION.md): core protocol
- [Implementation contracts](design/IMPLEMENTATION_CONTRACTS.md): package, grader, and recovery behavior
- [Long-horizon engineering design](design/LONG_HORIZON_ENGINEERING.md): continuous multi-stage task (six stages since eng-005 0.4.0)
- [Current plan](plans/PLAN-006-suite-runner-and-hardening-round-2.md): the suite runner and hardening round 2 (done; decisions pending)
- [Suite files](../suites/): `dev.json` (dev-run policy enforced) and `full.json`

## Next steps

1. **The user decides** on the review's open points:
   - T1, T2 and E3 as reliability families, rebuilt around continuous objectives, or retired;
   - whether E4 at 85% is acceptable;
   - MiMo runs of compress (4M) and E3 0.4.0 (8M);
   - relay balance for glm, step and luna.
2. **Dev rounds** use `npm run suite -- --suite suites/dev.json --models deepseek:deepseek-flash,<references> --families <changed>`, as one background command; accept from `runs/suites/<id>/report.md`. deepseek-flash plus about two references, at most one from the airy.work relay; no pro models; one repetition.
3. **Audit every failure** before counting it. This round's audits found seven defects in graders, tasks, the runner and budgets (see the review).
4. **History.**
   - [PLAN-005](plans/PLAN-005-discriminating-attributable-evaluation.md) set the scoring rules.
   - The [2026-10-20 review](reviews/2026-10-20-hardening-round.md) found that detail does not harden a family.
   - The [2026-10-22 review](reviews/2026-10-22-hardening-round-2.md) found that depth and scale under a well-specified brief do not either. Ladders over reasoning depth and continuous engineering objectives do.
5. **eng-004 0.3.0** has a rebuilt baseline and is the starting point for E1, which is not scheduled.
6. **Limit conclusions** to the observed task versions, models, prompts, tools and budgets: these are one-trial dev runs.

## Operating rules

- Run `python3 scripts/task_packages.py check --plans <current plans>` after changing anything under `task-library/`, calibration.md and rubric.md included (manifests pin them). Without `--plans` it also reports historical plans' stale pins. Use `rehash` only together with a task version bump and a calibration note.
- A grader fix keeps the task version so that trials can be regraded. Bump the grader version in every place the package declares it. Regrade with a copy of the run's plan carrying the new pin, then rebuild the suite report with `npm run suite -- --resume runs/suites/<id>`.
- Dev rounds: deepseek-flash plus about two references, at most one from the SuperAI relay (airy.work: glm, step, luna); no pro models; one repetition. Run preflight before launching, and accept from the report after the completion notification.
- Keep the pinned ENG-005 and ENG-004 baselines in their packages' `baseline.bundle`; `npm ci` (and every `npm test` or `npm run harness`) restores the local Git checkouts through `scripts/prepare-baselines.mjs`.
- Do not commit `.env` or other credential files.
- Use `--validate-only` for plan preflight when no API call is intended.
- Treat task fixtures as test inputs and preserve their pinned content and commits.
- Never delete `evaluation-*` workspace directories while a run is active; they are live trial workspaces.
- A run is pinned to its Git commit. Suites freeze their own worktree under `runs/suites/<id>/worktree`. To resume a plain run after later commits, use `git worktree add --detach <commit>` with `node_modules`, `.env` and `runs` symlinked in.
