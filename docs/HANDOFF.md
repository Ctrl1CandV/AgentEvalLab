# Project Handoff

Updated 2026-10-25 (PLAN-007 Phases 0–3 done; Phase 4, the first paid run, awaits the user's decisions).

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

**The v1 task design has reached its end.** Three hardening rounds (2026-10-20 to 2026-10-23) left the strong flash models at 90–100% on most families, or below that only because of budgets. The numbers, each with its task and grader version, protocol and run, are in the evidence table [`evidence/V1_EVIDENCE.md`](evidence/V1_EVIDENCE.md):

- **T1 0.6.0 F4/F5** (grader 1.7.1): deepseek 94.3%; qwen 85%, with every field right (the loss is the format deduction).
- **T2 finance 0.3.0 at 6M per day:** deepseek 98.1%, qwen 67.9% (a budget stop), mimo 9.4% under grader 1.2.0; 98.0/67.6/8.8 under 1.1.0.
- **E3 0.5.0 at 5M per stage and 25M per trajectory:** deepseek 90%, qwen 95% under grader 2.3.0; 90/94 under 2.2.0.

A third-party review ([`reviews/2026-10-24-third-party-evaluation-review.md`](reviews/2026-10-24-third-party-evaluation-review.md)) traced the overflow to task design, scoring, process and coverage, not to the execution core. **The user decided on 2026-10-24 to restructure the whole project**: design in [`design/v2/`](design/v2/README.md), plan [PLAN-007](plans/PLAN-007-v2-restructure.md).

**PLAN-007 progress** (reviews: [phase 0](reviews/2026-10-24-v2-phase-0.md), [phase 1](reviews/2026-10-24-v2-phase-1.md), [phase 2](reviews/2026-10-24-v2-phase-2.md), [phase 3](reviews/2026-10-24-v2-phase-3.md)):

- **Phase 0** (evidence and corrections): local tag `v1-final`; the evidence table (`npm run evidence`); the T2 coverage hole fixed (grader 1.2.0); success audits (`npm run audit`, `docs/audits/`), with E3 grader 2.3.0 and E4 grader 1.5.0 fixing what they found; append-only trajectory re-grading.
- **Phase 1** (the measurement layer): manifest v2 and grader result v2; `src/scoring/` (outcome records, uncapped anchors, structure caps, cluster bootstrap, paired comparisons); `outcome.json` beside every v2 score run; report v2 and suite v2; proved on R3 and AE without model runs (`docs/evidence/v2-proof/`).
- **Phase 2** (library and harness):
  - packages by tier in `task-library/basic/`, `core/`, `frontier/`, `retired/`; v2 suites `suites/basic.json`, `core-dev.json`, `frontier-dev.json`, all passing their dry runs;
  - every retained package on manifest v2 with a capability card (`card.md`); grader fixes with re-grades: eng-001 1.2.0 (a missing delivery is graded), E4 1.6.0 (speedup by CPU time; compress headlined by its size through LZMA and reference anchors), E2 1.7.0 (routes headlined by `routeShare`, valid when it solves an instance; README not critical), E3 2.4.0 (S6 by CPU time); noise tests in each package's `logs/`;
  - R3 0.4.0: validation and holdout in twelve never-piloted grid shapes, and the answer-only `none` profile;
  - harness: read-only runtime mounts, the `none` profile, repository workspaces (single-commit history, the change as a patch), per-item headlines (`primaryByItem`, item-scoped metric groups and metrics).
- **Phase 3** (new families, built and verified offline; `suites/core-dev.json` dry run passes for all eight families):
  - AR 0.1.0 (ARC-AGI-1/2 public evaluation, pass@2; answer-only and with code as its own row); AP stockroom 0.1.0 prototype (decisions under uncertainty through a simulator tool); AE grader 2.1.0 (a greedy reference per problem, fresh-seed judging);
  - VIS v2 0.1.0: eight briefs, executed interaction checks in headless Chromium, a reference and a plain anchor per brief, `scripts/judge-tournament-v2.ts` (ratings per brief against the anchors; judging is paid, Phase 4);
  - ER 0.1.0: dev 12 (SWE-bench-Live), validation 31 and holdout 3 mined since 2026-06-01; every task reviewed against its issue (`private/review.json`); one test-result parser with whole ids for builder and grader;
  - harness: external assets and archived runtimes (`npm run prepare`), the `workspace-simulator` profile.
- **Open for the user** (Phase 2 review): E2 routes fails its noise gate because its contract limit is wall time (options a/b/c in the review); budgets for E2's contract items and eng-004 (never run at their versions).
- vis-001's two false passes become VIS v2 negative tests (Phase 3); the AE calibration table correction lands with AE 0.2.0's references (WP3.5).

## Key files

| File | What it is |
| --- | --- |
| [design/v2/README.md](design/v2/README.md) | Why v1 overflowed, the goals and principles of v2, the architecture, what stays and what goes |
| [plans/PLAN-007-v2-restructure.md](plans/PLAN-007-v2-restructure.md) | The phases, work packages, acceptance criteria, token envelopes and user decisions |
| [design/v2/MEASUREMENT.md](design/v2/MEASUREMENT.md), [PROTOCOL.md](design/v2/PROTOCOL.md), [TASK_LIBRARY.md](design/v2/TASK_LIBRARY.md), [VALIDATION.md](design/v2/VALIDATION.md), [CODE.md](design/v2/CODE.md) | Binding design |
| [templates/CAPABILITY_CARD.md](templates/CAPABILITY_CARD.md) | The card every family fills in before it is built |
| [reviews/2026-10-24-third-party-evaluation-review.md](reviews/2026-10-24-third-party-evaluation-review.md) | The evidence-based review the plan answers |
| [evidence/V1_EVIDENCE.md](evidence/V1_EVIDENCE.md) | Every recorded result with its versions, protocol, coverage and run (`npm run evidence`) |
| [audits/](audits/) | Success audits per family (`npm run audit`) |
| [reviews/2026-10-24-v2-phase-0.md](reviews/2026-10-24-v2-phase-0.md), [phase-1](reviews/2026-10-24-v2-phase-1.md), [phase-2](reviews/2026-10-24-v2-phase-2.md) | PLAN-007 phase reviews, one note per work package |
| `task-library/<tier>/<package>/card.md` | Each family's capability card, hashed in its manifest |
| [reviews/2026-10-22-hardening-round-3.md](reviews/2026-10-22-hardening-round-3.md) | The last v1 round, with results |
| `design/V1_EVALUATION.md`, `design/IMPLEMENTATION_CONTRACTS.md`, `SPEC.md` | v1 protocol and contracts; still valid for the execution core |

## Next step

Phase 4 (the first paid runs: budget curves on the dev splits, then the dev round) starts when the user has decided the open points listed at the end of the [phase 3 review](reviews/2026-10-24-v2-phase-3.md) (D1–D7, E2 routes noise, budgets, E3 headline, the VIS briefs, model release dates). Mechanical work (mining, re-runs, packaging, self-calibration) may be delegated to a general-purpose model under a written brief; decisions on tasks, graders and scoring stay with the reviewer.

## Operating rules

- **Packages.** After changing anything under `task-library/`, rebuild the package (its builder, or `python3 scripts/task_packages.py rehash <package>`, which also re-pins the current plans), and run `python3 scripts/task_packages.py check --plans <current plans>`. calibration.md, rubric.md and card.md are pinned too. Historical plans keep the old paths of packages moved in Phase 2; a plain `check` without `--plans` therefore reports them.
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
- **Re-grading.** A grader fix keeps the task version so that trials can be re-graded. Bump the grader version everywhere the package declares it, re-grade with the current plan (or a copy of the run's plan) carrying the new pin (`npm run harness -- --plan <copy> --regrade <trial> --reason "..."`, or `--regrade-trajectory <trial> [--scope final]` for a trajectory), then rebuild the suite report with `npm run suite -- --resume runs/suites/<id>` and the evidence table with `npm run evidence`.
- **Baselines.** Keep the ENG-005 and ENG-004 baselines in their `baseline.bundle`. `npm ci` and every `npm test` restore them.
- **Workspaces.** Never delete `evaluation-*` workspaces while a run is active.
- **Tools.** Rust is installed under `~/.local/share/{rustup,cargo}` (used by the AE builder). The ALE-Bench archives are cached in `~/.cache/agenteval/ale-bench/`, and their compiled tools in `~/.cache/agenteval/ale-tools/`.
