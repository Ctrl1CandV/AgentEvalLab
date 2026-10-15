# PLAN-004: Reproducible Model-Evaluation Baseline

Updated 2026-10-13. Supersedes the remaining-work list in [PLAN-003](PLAN-003-v1-evaluation.md).

## Scope

Make single-model, task-level evaluation reliable before any agent- or harness-comparison work. Agent evaluation is out of scope for this plan.

## Decisions

- The English task material in this repository is the canonical baseline. There is no earlier source text to reconcile against, and the project no longer depends on the reference project it started from.
- Task versions were bumped because instruction and documentation bytes changed after the previous calibration. Earlier calibration logs remain historical evidence for the earlier versions only.
- Graders and public checkers resolve `python3` from PATH and require Python 3.13 (minor version, not an exact patch). Node.js 22 remains required.
- Task-library bytes are protected from line-ending conversion by `.gitattributes`, because manifests pin them by SHA-256.
- `scripts/task_packages.py` is the Node-free integrity tool: `check` mirrors preflight hashing and file-set rules, and `rehash` re-pins manifests, metadata digests, and example plans.
- Pi Agent stays at 0.87.1. Model evaluation needs only the basic agent loop; newer Pi versions add nothing the project needs. The version is still recorded in every run fingerprint.
- Pilot models: `deepseek:deepseek-flash` (OpenAI-compatible protocol) and `aliplan:qwen3.8-flash` (Anthropic-compatible protocol). The pilot calibrates budgets and verifies provider usage and error reporting; it is not a model comparison.

## Phase 1: Repository consistency (done 2026-10-13)

- Re-pinned all six manifest packages: eng-001 0.3.0, eng-004 0.2.0, rsn-001 0.3.0, rsn-002 0.3.0, tool-001 0.3.0, eng-005 0.2.0. Example-plan pins updated.
- Added the missing `toolEvidenceMaxBytes` limit to `examples/eng-001.eval.json`.
- The CLI now reports stable error codes instead of one generic failure line.
- eng-001 mutants `always_exit0`, `dryrun_writes`, and `insert_only` imported `ref_impl_a.py`. The grader copies only the candidate script into isolation, so these mutants crashed on import and scored 0/22 without exercising their defects. They are now generated as self-contained scripts by `private/make_mutants.py`. Under Python 3.10 they score 7/22, 20/22, and 21/22 again, matching the historical record.

## Phase 2: Re-establish offline evidence (done 2026-10-13, except eng-004)

- Environment: conda `agenteval` from `environment.yml` (Python 3.13.15, Node.js 22.23.2).
- `npm run check` passes; `npm test` passes 43 of 44, the remaining failure being eng-004.
- All grader self-calibrations pass under Python 3.13.15 except eng-004; new per-version logs are in each package's `logs/`. eng-005 replay calibration passes and its log matches the current manifest.
- Fixed: eng-005 reference READMEs (they failed the S5 check), a mis-specified Unicode paging test, and npm scripts that the sandbox could not run.
- Still open: rebuild the eng-004 baseline. The pinned commit `3b43f3c6…` was an unresolvable Git link to the reference project. Create a project-owned baseline, ship it as a bundle restored by a prepare script (as for eng-005), and release it as a new task version.

## Phase 3: Fix pre-pilot blockers (done 2026-10-14, except the AliPlan live check)

Status:
- WP0, checkpoint commits: `076b6a7` through `8063533`.
- WP1, workspace per trial: `8ebf366`.
- WP2, bubblewrap sandbox: `6008d5e`.
- WP3, verdict and review: `48a7993`.
- WP4, plan schema 3: `c1a4438`.
- WP5, batch containment: `96397d5`.
- WP6, repetitions and reports: `1b14106`.
- WP7, provider check: DeepSeek passed every check. AliPlan's token-plan quota is exhausted until 2026-10-19 16:00 UTC. See [the provider check](../reviews/2026-10-14-provider-check.md).

Work packages follow the [benchmark alignment review](../reviews/2026-10-13-benchmark-alignment-review.md); finding IDs are given in brackets. Every package lands with tests. Any package that changes graders, checkers, or manifests bumps the affected task versions once, re-pins with `scripts/task_packages.py rehash`, and reruns that package's calibration.

### WP0. Checkpoint commit

Commit the phase 1 and phase 2 work, with user approval, so phase 3 diffs can be reviewed on their own. Exclude the sandbox placeholder files at the project root (`.bashrc`, `.gitmodules`, `.idea`, `.mcp.json`, and similar character devices) through `.git/info/exclude`.

### WP1. Workspace per trial [F2]

- Replace the shared detached worktree with a private `git clone --no-hardlinks` of the pinned commit inside the trial's temporary root.
- Collect the submission as the diff from the pinned commit to the final working tree, whatever HEAD points to.
- Cleanup removes only the owned temporary root.
- Tests: a candidate commit is graded; the baseline repository's refs and objects are unchanged afterwards; the existing ownership and tamper tests still pass.

### WP2. Candidate isolation with bubblewrap [F1]

- Add one launcher, `src/sandbox.ts`, plus a small executable wrapper for graders. It runs a command with:
  - the workspace bound read-write as the working directory;
  - system directories and the pinned runtime bound read-only;
  - a private `/tmp`, no `/home`, and no network (`--unshare-all`);
  - `--die-with-parent`, and the existing environment allowlist.
- `execute_command` runs through the launcher.
- Graders and public checkers that start candidate code receive the launcher in the grader request, or as a checker argument, and prefix their single spawn point with it. The spawn points are:
  - eng-001 `_run_bounded`;
  - eng-004 `subprocess.run`;
  - eng-005 `invoke` and the five checker `run` functions.
- Preflight fails if bubblewrap is unavailable. Unsandboxed execution is allowed only through an explicit plan setting that is recorded in the fingerprint.
- Tests:
  - the review probe that read eng-001's `private/oracle.json` through `execute_command` now fails;
  - network access fails;
  - workspace writes succeed;
  - every reference and mutant calibration result is unchanged.

### WP3. Objective verdict separated from human review [F3]

- Compute `passed` and `failed` from critical checks only.
- Missing non-critical checks set a separate review status (pending or complete) instead of `unscored`. `unscored` stays reserved for missing critical checks.
- Add an append-only command that imports a human review file as a new score run against the frozen snapshot.
- Tests: rsn-002 with correct certificates passes with review pending; importing a review completes it without changing the original record.

### WP4. Plan schema 3: limits and evaluated condition [F4, F8]

Change the plan schema once, to version 3, and update all example plans:

- Add a separate `maxToolResultChars` budget. An oversized tool result becomes a recoverable tool error returned to the model; it no longer ends the run.
- Add an explicit model-options block (thinking level, temperature) instead of the constants in `src/harness/pi.ts`.
- Declare per-model metadata in `src/providers.ts`: context window, output limit, reasoning support, and optional prices per million tokens. Without prices, `costUsd` stays null.
- Extend `experiment.json` with:
  - the git commit and dirty flag;
  - Node, Python, and Pi package versions;
  - a digest of each tool profile's names, descriptions, and schemas;
  - the system prompt and model options.
- Remove the unreachable unknown-tool branch from `beforeToolCall`.

### WP5. Batch containment [F14]

- Add a bounded retry (default 2) for retryable provider errors (429, 5xx, network) that arrive before any streamed output. Each attempt is recorded, and retries do not consume the model-call budget.
- Stop the batch on authentication or balance errors, or after a configurable run of consecutive infrastructure failures. Remaining trials are recorded as `not_run`.
- Add a batch token ceiling, and a cost ceiling when prices are declared. The batch stops scheduling new trials once a ceiling is reached.
- Add `--resume <run>`. It reruns only missing or infrastructure-failed trials and refuses to run if the fingerprint differs.
- Classify provider context-length errors as `CONTEXT_LIMIT`, a recorded outcome of the evaluated condition, so long eng-005 sessions that overflow are not reported as infrastructure failures.

### WP6. Repetitions and reporting [F5, F6, F7]

- Add a plan-level `repetitions` count. Trial order is interleaved across models with a recorded seed.
- Report per model × task:
  - n and passes;
  - pass^1, and unbiased pass@k and pass^k estimates;
  - per-check pass rates and Wilson intervals;
  - the malformed-answer count.
- Report paired model differences with task-clustered intervals. Drop the cross-task pass rate.
- Answer-graded graders (rsn-001, rsn-002, tool-001) gain a non-critical answer-format check, so format failures are counted separately. Scoring stays strict.
- Add a report command that merges several run directories with the same fingerprint.

### WP7. Provider verification [F15]

An offline-first checklist, plus one tiny live request per pilot model under a hard request cap. It needs credentials and runs only with user approval. For each model, check:

- usage is reported and non-zero;
- a forced small output cap yields `stopReason: length`;
- the default thinking behaviour with thinking off;
- a multi-turn tool call round trip;
- an invalid key is classified as an authentication error that stops the batch.

Record the results and the corrected model metadata.

### Ordering

WP0 first. WP1 and WP2 both change the workspace and execution layer, so WP1 comes before WP2. WP3 and WP4 are independent. WP5 and WP6 build on WP4's schema, and WP7 needs WP4 and WP5. Batch the grader-side edits in WP2 (launcher prefix) and WP6 (format check), so each affected task gets one version bump and one recalibration.

### Exit criterion

All tests pass, and every runnable package recalibrates under the sandbox. The review probes for F1 and F2 behave as intended. A validate-only run of every example plan passes, except eng-004 until its baseline is rebuilt.

## Phase 4: Pilot and first frozen set

1. **Pilot protocol.** [experiments/pilot-2026-10](../../experiments/pilot-2026-10/README.md), with null-agent baselines run. The user confirmed its conditions on 2026-10-14. Round 1 (luna-medium, glm-5.3-flash) and round 2 (luna-medium, glm-5.3-max, under per-trial and per-model token caps) are complete. Results, fixed defects, budget recommendations, and open decisions are in [the pilot results](../reviews/2026-10-15-pilot-results.md).
   - **Models:** `supergpt:gpt-6-luna` with reasoning effort `medium`, and `supercn:glm-5.3-flash` with `provider-default` thinking (always on), both at temperature 0. The second pilot model changed because AliPlan's quota is exhausted until 2026-10-19.
   - **Condition decision (user, 2026-10-14):** thinking levels need not match across models, because each provider controls thinking differently. Each model runs at a stated level, and reports append the level to the model label, as public leaderboards do. Temperature is the same for all models. The pilot budgets stay generous, because the pilot's job is to measure token use before budgets are set.
   - **Scope:** rsn-001, rsn-002, tool-001, and eng-001, with 3 repetitions each, under token ceilings totalling 6M (about 3M per model). eng-005 is excluded until its cost is estimated from the pilot.
   - **Use of results:** set per-task budgets. Inspect outliers for harness or grader bugs before trusting any score (ABC T.10).
2. Mark the calibrated tasks `pilot`, freeze the first task set, then run the multi-model comparison.
3. Add instance generators for the reasoning and tool families and canary strings (F10, F11). Null-agent baselines (F12) are available through `scripts/null-agent-baseline.ts`.
4. Convert the manifest-less packages afterwards: eng-002 first, then eng-003. vis-001 needs browser rendering and human review, so it comes last.

## Evidence limits

Phase 1 smoke checks used Python 3.10; phase 2 repeated them under the pinned Python 3.13.15 and Node.js 22 runtime. All results are offline calibration of graders and harness behavior. None measures model capability.
