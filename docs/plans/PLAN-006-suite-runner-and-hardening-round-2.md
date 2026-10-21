# PLAN-006: One-Command Suite Runs and Hardening Round 2

Status: approved by the user on 2026-10-21. Follows [PLAN-005](PLAN-005-discriminating-attributable-evaluation.md) and the [hardening round of 2026-10-20](../reviews/2026-10-20-hardening-round.md).

## Decisions (user, 2026-10-21)

- **Build the one-command chain first.** Choose models, run every family, get one report. Dev rounds use the same chain on the families being changed, so there is no separate round script.
- **Models for dev rounds.**
  - deepseek-flash always; it is the model to bring to about 80%.
  - About two references from mimo-v2.6-flash, qwen3.8-flash, glm-5.3 (or glm-5.3-flash) and step-5-preview, as the check needs; up to three when more control groups help.
  - At most one model from the SuperAI relay (airy.work: glm, step, luna), whose balance is small.
  - No pro models, and one repetition.
  - The full model set and repetitions wait for the real evaluation stage and the user's go-ahead.
- **Balances (2026-10-21).** deepseek and qwen ample, MiMo about half its subscription, the relay little.
- **Automation.** Preflight before launching, launch once in the background, accept the results when the completion notification arrives. Do not watch runs. On 2026-10-20 runs took six to seven hours, largely because of seven models per run and watching them.
- **Target.** deepseek-flash at about 80% or below on most families; a few slightly above is acceptable.
- **T2** moves to optimisation within the policy (below). **E3** gets a scale stage with speed tiers.

## Where the families stand

Measured on 2026-10-20 (details in the hardening review). The template is the plan a suite family is generated from.

| Family | Package version | Template plan | Scoring items | deepseek | Others | Status |
| --- | --- | --- | --- | ---: | --- | --- |
| R3 logic grids | 0.3.0 | `experiments/r3-calibration-2026-10/l5-l7.eval.json` | L5–L7 | 72% | qwen 24, mimo-pro 42, mimo-flash 28 | done |
| E2 specifications | 0.5.0 | `experiments/e2-calibration-2026-10/routes.eval.json` | `routes` (sheet, query, ledger and recur are saturated anchors) | 71% | qwen 17, mimo-pro 56, mimo-flash 58 | done |
| T1 evidence recovery | 0.4.1 | `experiments/t1-calibration-2026-10/l7.eval.json` | L7 | 96% | qwen 85, mimo-pro 36, mimo-flash 34 | B2 |
| E4 command line | 0.4.1 | `experiments/e4-calibration-2026-10/speedup.eval.json` | `speedup` (codec, the compound items and 0.1.0 are anchors) | 100% (measured offline) | qwen 36, mimo-pro 86, mimo-flash 43 | B1 |
| E3 long horizon | eng-005 0.3.0 | `experiments/e3-calibration-2026-10/trajectory-<model>.eval.json` | last graded snapshot, 41 checks | 98% | qwen 100, mimo-pro 41, mimo-flash 85 | B4 |
| T2 service desk | 0.2.0 | `experiments/t2-calibration-2026-10/v0.2.eval.json` | 12 tickets | 97.5% | qwen 100, mimo-pro 97.5, mimo-flash 91 | B3 |
| Visual (vis-001) | 0.3.1 | `experiments/vis-calibration-2026-10/calibration.eval.json`, then `scripts/judge-tournament.ts` | pairwise tournament | 83% win rate | relative ranking | good enough (user) |

Retired or not in the suite: R1 (saturated), the eng-001 to eng-005 single tasks other than E3 (anchors), and E1. eng-004's baseline was rebuilt on 2026-10-20 and is the starting point for E1 later.

## Part A: the suite runner

`npm run suite -- --suite suites/<name>.json --models <list> [--families R3,E2] [--reps 1] [--dry-run] [--resume runs/suites/<id>]`

- **Suite file** (`suites/dev.json`, `suites/full.json`). For each family it records:
  - an id and a kind: `single`, `trajectory` (one run per model, as E3 plans are) or `visual` (page run, then the tournament);
  - the template plan, which supplies the package, items or levels, budget, batch and artifact limits;
  - the items or levels that make up the family score;
  - optional overrides, such as concurrency.

  Models come only from `--models`, which accepts the plan model syntax including `thinkingLevel`, for example `deepseek:deepseek-flash?thinking=high`. Repetitions come from `--reps`.
- **Steps, all in one background command.**
  1. **Freeze.** Create a detached Git worktree of HEAD under an ignored path such as `runs/.worktrees/<suite-id>`, with `node_modules`, `.env` and `runs` linked. Every plan then runs from a clean, pinned tree, and the main tree stays free for editing. Warn when HEAD has uncommitted changes, since they are not part of the run.
  2. **Generate** one plan per family from its template with the chosen models and repetitions, written to `runs/suites/<id>/plans/` (ignored, so the tree stays clean and resume can reuse them).
  3. **Preflight.** Run `python3 scripts/task_packages.py check`, `--validate-only` for every plan, and a worst-case token estimate per provider. Write all of it to the suite directory and abort on any failure.
  4. **Smoke.** Run `scripts/null-agent-baseline.ts` on one item of each family. It sends no requests and costs no tokens, and it proves projection, sandbox, export and grading end to end. Every check must fail, and the trial must be graded, not an evaluator error.
  5. **Launch.** Single-run families start as concurrent harness processes; trajectory families start one process per model; the visual family runs its page plan and then the tournament. Cap concurrent requests per provider across all processes, so one provider is not flooded by several plans at once.
  6. **Retry pass.** When everything has ended, resume each run once for its infrastructure failures, skipping providers stopped for balance or authentication.
  7. **Report.** Write `runs/suites/<id>/report.md` and `report.json`:
     - each family's score per model (mean, 95% interval, resolved rate, median tokens, budget stops), and a cross-family table;
     - not-run trials with their reasons, and infrastructure failures with the provider's error text;
     - the most-failed checks per family with sample grader reasons;
     - flags: a family where deepseek is above 80%; a family where every model is at or above 90% (saturated); budget stops in most trials; an infrastructure rate above 10%; a provider stopped for balance.
  8. **Exit** with a status. The caller receives one completion notification.
- **Tests,** offline with injected runners: plan generation from templates, model and repetition substitution, family-score aggregation, report flags, and resume of a suite.
- **Done when:** one command runs a dev suite of two families with deepseek-flash and one reference end to end, and the report is correct against the item analyses of the same runs.

## Part B: hardening round 2

Each family change follows the same path:

1. Design and build.
2. Self-calibrate: references, mutants, and the untouched workspace earning nothing.
3. Bump the version.
4. Run one dev suite round on that family with deepseek-flash and two references.
5. Audit every failure for attribution.
6. Record the results in the package `calibration.md` and the experiment README.

Group families into the same suite round where possible.

- **B1. E4: a second continuous item.**
  - **The item:** a lossless compressor for a structured log corpus, scored by compression ratio. The lower anchor is Python's `lzma` at its strongest preset, since the standard library can reach it with no effort. The upper anchor is a structure-aware reference written for the item: column split, delta-coded timestamps and dictionaries.
  - **Checks:** at 50/80/90/97% of the way between the anchors, on hidden corpora, with exact round trip required and a time limit.
  - Run `speedup` 0.4.1 formally in the same round. E4's family score becomes speedup plus the new item.
  - **Expected:** deepseek near 80% on the family.
- **B2. T1: a depth ladder** instead of more volume. Twelve 1,300-line logs only exhausted budgets (0.4.0).
  - **New levels:** questions that follow a chain of 2, 4, 6 and 8 references (service, then upstream, then include chain, then change record, then incident), with a plausible distractor at every hop. Errors compound with depth, as grid size does in R3.
  - **Scoring:** the family score uses the new levels.
- **B3. T2 0.3.0: optimisation within the policy.**
  - **The tickets:** each has several compliant resolutions, and the policy states which one is required: for example, the resolution with the lowest cost to the shop that still meets the customer's request, or the best compensation the rules allow.
  - **The oracle:** `private/oracle.py` enumerates the compliant action sets and computes the optimum.
  - **Scoring:** compliance checks, plus optimality against the optimum (exact, within 1%, within 5%), on tickets graded by size: the number of orders, lines and alternatives.
  - Keep the integrity gate, the format rule (the reply *ends with* the JSON) and the guards.
- **B4. E3: eng-005 0.4.0 with a sixth stage, scale.**
  - **The stage:** 100,000 work orders. `list` with filters, sort and pagination, and dependency checks on a large graph.
  - **Scoring:** timed against a reference implementation at 3/1.5/1.1/0.75 times its time, like speedup, with correctness gates.
  - **The references:** ref-a and ref-b need S6 implementations.
  - **Budget:** add a stage, roughly 8M tokens per trajectory; run deepseek-flash and one reference only.

Order: Part A, then B1 and B2 (cheap, can share one round), then B3, then B4 (most expensive).

**Rough token use per model for one dev round** (2026-10-20 medians; open-ended items always use their whole budget):

| Family | Tokens |
| --- | ---: |
| R3 L5–L7 | about 2.5M |
| T1 L7 | about 5.5M |
| E2 routes | 3M |
| E4 speedup plus the new item | about 4M |
| T2 | about 1M |
| E3 | 6–8M |

Run only the families being changed.

## Pitfalls met on 2026-10-20

- A manifest pins `calibration.md` and `rubric.md` as well. After editing them, rebuild the package, update the plan's `packageManifestSha256`, and run `scripts/task_packages.py check` before committing.
- `.gitignore` excludes `*.pyc`. Files a package ships on purpose need an exception (the codec item's `lgz.pyc` has one).
- Artifact limits must allow what the task invites. Speedup models wrote test days of tens of megabytes; plans now allow 128 MiB per file.
- Only the task budget may stop a model. Plans use 131,072 output tokens and 524,288 characters of text per response.
- A trial cannot be regraded under a different task version (`REGRADE_TASK_VERSION_MISMATCH`). Changing a stated threshold therefore means a new run, so settle thresholds in self-calibration.
- Open-ended items (routes, speedup) always use their whole budget; that is their time limit, not a defect. Fixed-answer items must not: T1 L7 0.4.0 exhausted budgets without answers and was rescaled.
- A command run with its working directory inside a package creates sandbox placeholder files (`.claude/`, `.mcp.json`). They are excluded in `.git/info/exclude`, but check `git diff --cached --name-only` before committing package paths.
- Never delete `evaluation-*` workspaces while runs are active.
- A run is pinned to its commit; resume from a worktree at that commit. The suite runner's freeze step removes this chore.
- Timing checks pin one CPU core per grader process (`os.getpid() % cpu_count`). Keep timing thresholds well away from the calibration mutants' ratios.
- A relay balance error comes back as HTTP 403 with `insufficient_user_quota` and is classified as a balance failure. Such a failure stops only that provider.
