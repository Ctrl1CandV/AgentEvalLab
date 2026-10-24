# Project Handoff

Updated 2026-10-24.

## Current state

AgentEvalLab is a single-model evaluation project on Pi Agent 0.87.1. Its execution core is mature:

- versioned task packages with trusted graders;
- a bubblewrap sandbox;
- artifact snapshots (links and special files skipped);
- append-only re-grading;
- continuous and per-stage trajectories;
- batch containment;
- stated budgets with reminders;
- plan-level command limits;
- a frozen-worktree suite runner that refuses a resume under another Node major version and continues interrupted retries.

**The v1 task design has reached its end.** Three hardening rounds (2026-10-20 to 2026-10-23) left the strong flash models at 90–100% on most families, or below that only because of budgets.

- **T1:** deepseek 94.3%; qwen 85%, with 100% content.
- **T2 finance 0.3.0:** deepseek 98.0%, qwen 67.6% (a budget stop), mimo 8.8%.
- **E3 at a sufficient budget:** deepseek 90%, qwen 94%.

A third-party review (`docs/reviews/2026-10-24-third-party-evaluation-review.md`) traced the overflow to task design, scoring, process and coverage, not to the execution core. The review also found a T2 grading hole: actions under an unknown request id escape grading. That hole has not been fixed yet.

**The user decided on 2026-10-24 to restructure the whole project.**

- The design is in [`docs/design/v2/`](design/v2/README.md).
- The implementation plan is [PLAN-007](plans/PLAN-007-v2-restructure.md).
- Nothing of PLAN-007 is implemented yet.
- The AE family (algorithm engineering on AtCoder Heuristic Contest problems, `task-library/frontier/ae-heuristic-contests` 0.1.0) is built and self-calibrated, but has no model runs. Its dev pilot was prepared and deliberately not launched.

## Key files

| File | What it is |
| --- | --- |
| [design/v2/README.md](design/v2/README.md) | Why v1 overflowed, the goals and principles of v2, the architecture, what stays and what goes |
| [plans/PLAN-007-v2-restructure.md](plans/PLAN-007-v2-restructure.md) | The phases, work packages, acceptance criteria, token envelopes and user decisions |
| [design/v2/MEASUREMENT.md](design/v2/MEASUREMENT.md), [PROTOCOL.md](design/v2/PROTOCOL.md), [TASK_LIBRARY.md](design/v2/TASK_LIBRARY.md), [VALIDATION.md](design/v2/VALIDATION.md), [CODE.md](design/v2/CODE.md) | Binding design |
| [templates/CAPABILITY_CARD.md](templates/CAPABILITY_CARD.md) | The card every family fills in before it is built |
| [reviews/2026-10-24-third-party-evaluation-review.md](reviews/2026-10-24-third-party-evaluation-review.md) | The evidence-based review the plan answers |
| [reviews/2026-10-22-hardening-round-3.md](reviews/2026-10-22-hardening-round-3.md) | The last v1 round, with results |
| `design/V1_EVALUATION.md`, `design/IMPLEMENTATION_CONTRACTS.md`, `SPEC.md` | v1 protocol and contracts; still valid for the execution core |

## Next step

Carry out PLAN-007 from Phase 0. Phases 0–3 need no paid model runs. The user's decisions D1–D7 are listed in the plan, with recommendations.

## Operating rules

- **Packages.** After changing anything under `task-library/`, rebuild the package, update `packageManifestSha256` in the current plans, and run `python3 scripts/task_packages.py check --plans <current plans>`. calibration.md and rubric.md are pinned too.
- **Commits.** Commit only; never push. Use `git -c user.name=liuyijie -c user.email=126372470+Ctrl1CandV@users.noreply.github.com commit`, ending the message with the Co-Authored-By line. Never commit `.env` or the sandbox placeholders (`.claude/`, `.mcp.json`); check `git diff --cached --name-only | grep '/\.'`.
- **Model runs.** Dev rounds use deepseek-flash plus about two references, at most one from the airy.work relay; no pro models; one repetition.
  - Run a dry run first (`--dry-run`: preflight and a zero-token null-agent smoke).
  - Read its warning about uncommitted changes, and check the frozen plan.
  - The suite runs the committed HEAD.
- **Long runs.** My background tasks stop after 2 hours, and also when the session or terminal restarts. A run longer than about 1.5 hours is launched by the user from a WSL terminal:

  ```
  PATH=/home/claude-dev/.local/share/conda/envs/agenteval/bin:$PATH nohup npm run suite -- --resume runs/suites/<id> >> runs/suites/<id>/launch.log 2>&1 &
  ```

  The suite refuses a resume under the system Node 24. Watch the run with a background watcher that exits when `phases.report` is done or nothing has been written for 20 minutes. A trajectory cannot continue mid-way, so an interrupted E3 run starts again from S1.
- **Re-grading.** A grader fix keeps the task version so that trials can be re-graded. Bump the grader version everywhere the package declares it, re-grade with a copy of the run's plan carrying the new pin, then rebuild the suite report with `npm run suite -- --resume runs/suites/<id>`.
- **Baselines.** Keep the ENG-005 and ENG-004 baselines in their `baseline.bundle`. `npm ci` and every `npm test` restore them.
- **Workspaces.** Never delete `evaluation-*` workspaces while a run is active.
- **Tools.** Rust is installed under `~/.local/share/{rustup,cargo}` (used by the AE builder). The ALE-Bench archives are cached in `~/.cache/agenteval/ale-bench/`, and their compiled tools in `~/.cache/agenteval/ale-tools/`.
