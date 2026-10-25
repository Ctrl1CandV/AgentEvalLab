# v2 Task Library

What the library contains, where each family's difficulty comes from, and how tasks are authored, split and refreshed.

## 1. Tiers

| Tier | Purpose | Admission | Exit |
| --- | --- | --- | --- |
| **basic** | reliability: exact procedure-following, tool discipline, format, long-horizon consistency. High scores are expected and informative. | a passing grader verification; a cheap budget | retired when it no longer catches regressions |
| **core** | the main discrimination | a capability card; offline baselines showing a real gap; grader verification; a dev pilot with spread; a validation run | demoted to basic when saturated (VALIDATION §6) |
| **frontier** | headroom for future models | raw objective with external anchors, uncapped | promoted to core when the pool spreads on it without saturating; never forced |
| **retired** | history only | — | — |

## 2. Disposition of the existing packages

| Package | v1 role | v2 tier | Reason |
| --- | --- | --- | --- |
| t1-evidence-recovery 0.6.0 (T1) | evidence chains, F4/F5 | **basic** | Content near 100% for strong models; useful reliability and format signal. Keep a small fixed set; fix the format and content split in reports. |
| t2-finance-desk 0.3.0 (T2) | ledger operations and payment plan | **basic** (operations); the plan as an AP **bridge** | Operations saturate. Fix the coverage hole first (PLAN-007 Phase 0). Keep its global final-state check as a new resolved criterion. |
| t2-service-desk 0.4.0 | shift tickets | **retired** | superseded by the finance desk |
| eng-005 0.5.0 (E3) | seven-stage maintenance | **basic** | 90% and 94% at a sufficient budget; keep as a long-horizon consistency check |
| e4-terminal-tasks 0.5.0 (E4) | speedup and compress | speedup **basic**; compress **bridge** in core engineering | Compress still spreads; report raw bytes. Speedup is near its ceiling. |
| e2-spec-implementation 0.5.0 (E2) | routes and other items | routes **bridge** (open-ended); others **basic** | Report raw route value |
| r3-logic-grid 0.3.0 (R3) | logic grids L5–L7 | **core** (reasoning, answer-only) | Has spread. Headline is the resolved rate; cell accuracy and constraint validity are diagnostic. Output-limit stops are reported as their own column. |
| ae-heuristic-contests 0.1.0 (AE) | — | **frontier** | Human-anchored, uncapped; needs raw reporting and a validation run |
| vis-001-original-landing 0.3.1 (VIS) | one brief, tournament | superseded by **VIS v2** (core) | one brief is one structure group |
| eng-001 0.3.2 | import validator | **basic** | — |
| eng-004 0.3.0 | resource index | **basic** (baseline for E1, if E1 is ever built) | — |
| r1-rostering, rsn-001, rsn-002, tool-001 | v1 tasks | **retired** | saturated; history only |
| candidates eng-002, eng-003 (no manifests) | — | **retired** | never runnable |

"Bridge" tasks stay unchanged across the v1–v2 boundary, so that a v2 report can be linked to the v1 history. They are scored by the v2 model, and their v1 numbers stay under v1.

## 3. New and rebuilt families

Each section is the seed of the family's capability card. The implementer completes the card before building.

### 3.1 ER: live repository repair (core, engineering)

- **Sources.** Each instance gives the repository and base commit, the issue text, the gold patch, the gold test patch, the FAIL_TO_PASS and PASS_TO_PASS tests, a test command, a log parser, and the creation date. Checked on 2026-10-24:
  - **SWE-bench-Live** (`SWE-bench-Live/SWE-bench-Live`, MIT): 1,888 instances created up to **2025-09-02**.
  - **SWE-rebench leaderboard** (`nebius/SWE-rebench-leaderboard`, CC BY 4.0): monthly splits up to **2026-03**.

  Both may predate the training of the 2026 models in the pool. So:
  - **dev**, and the building of the pipeline, use these pools.
  - **validation and holdout** come from **our own mining**, by the same method: merged pull requests that fix a linked issue and change tests, in permissively licensed Python repositories, merged after the newest pool model's release date. We validate them locally exactly like the pool instances. Public GitHub data over HTTPS is reachable; the unauthenticated API (60 requests per hour) is enough for tens of tasks, and git clones need no API.
  - No per-model contamination flags (user decision, 2026-10-25): a task is judged by its own evaluative value; its provenance and dates are recorded as data, nothing more.
- **Selection.**
  - Python repositories under permissive licences.
  - Dependencies installable from wheels, so they can be vendored offline: no native builds needing apt, and no services.
  - Tests that run in under 5 minutes on this machine.
  - Mined fixes recent enough that their tests are current (merged since 2026-06-01 for v2.0).
  - Prefer multi-file fixes. Record the gold patch size (files, lines) as a difficulty covariate.
- **Task.**
  - The workspace holds the repository at the base commit without its history: a fresh single-commit `.git`, so the fix cannot be read from the history.
  - The model gets the issue text and the repository, and the dependencies through a read-only runtime mount.
  - It may run the tests.
- **Grading.**
  - As in SWE-bench, the grader applies the instance's `test_patch` (the gold tests) over the delivered workspace. Files that patch touches are first restored, so edits the model made to them do not count.
  - It then runs the instance's test command, in the sandbox with the runtime mount, and parses FAIL_TO_PASS and PASS_TO_PASS by the instance's `log_parser`.
  - **resolved** = every FAIL_TO_PASS passes and no PASS_TO_PASS fails.
  - **Diagnostic:** the share of FAIL_TO_PASS passing, and regressions in PASS_TO_PASS.
- **Environments.** SWE-bench-Live ships a Docker image and test commands per instance, but no pip recipe. The builder derives an install from the repository's packaging metadata (`pip install --target` of the package and its test extras, from vendored wheels). It keeps only instances whose validation passes on this machine.
- **Validation per task, before admission:**
  - the gold patch resolves it;
  - the base commit fails every FAIL_TO_PASS;
  - three runs agree, so flaky tests are dropped;
  - a null agent does not resolve it.
- **Headroom.** Real issues of varied difficulty. The paper reports about 19% for the best agent at release. Refresh adds new months.
- **Cheapest shortcut.**
  - Reading the fix from history (blocked).
  - Editing the tests (restored before grading).
  - Recall of a public fix: limited by mining recent fixes.
- **Size.** Dev 10 tasks from at least 5 repositories; validation 30 from repositories not in dev; holdout 30. Structure group = repository.

### 3.2 AR: abstraction and reasoning (core, reasoning)

- **Source.** ARC-AGI-1 (400 public evaluation tasks) and ARC-AGI-2 (120 public evaluation tasks), both Apache-2.0. ARC-AGI-2 tasks were each solved by at least two people in a controlled test; the average human score was 66%.
- **Protocols.**
  - **answer-only:** no tools. The task's training pairs and test inputs are in the prompt, and the answer is a JSON object of output grids.
  - **with code:** workspace and Python. A separate family row, never averaged with answer-only.
- **Grading.** Exact match per test output, two attempts per test input (pass@2, as ARC prescribes), both given in one reply. A task is resolved when every test output is matched; the task score is the share of test outputs matched.
- **Headroom.** ARC-AGI-2 is far from saturated for current models, and ARC-AGI-1 gives the lower part of the scale. The mix and the split are by version and by task.
- **Contamination.** Public evaluation sets may be in training data; record this. The structure group is the task; the split is drawn by task.
- **Size.** Dev 40 (20 ARC-1, 20 ARC-2). Validation 80 (30 ARC-1, 50 ARC-2). Holdout 80 (30 ARC-1, 50 ARC-2). Disjoint; this uses all 120 public ARC-AGI-2 evaluation tasks. ARC-AGI-1's public evaluation set has been public since 2019 and ARC-AGI-2's since 2025, so report the two versions as separate rows as well as together.

### 3.3 R3: logic grids (core, reasoning; existing)

- No new content for v2.0.
- The headline becomes the resolved rate; cell accuracy and constraint validity are diagnostic.
- Output-limit stops get their own column.
- Splits are drawn by size and clue structure, and fixed before the next run.

### 3.4 AP: sequential decisions under uncertainty (core candidate, agentic tool use)

This is the one new family we author, because no external source fits the single-model, tool-using setting. It must avoid the v1 failure mode: difficulty comes from **decisions under uncertainty with an unreachable optimum**, not from rules.

- **Environment.** A simulated operation behind a command-line tool:
  - `observe`;
  - `act` (with side effects, some irreversible);
  - `advance` (time moves; random events arrive from a seeded generator the model cannot see).

  Examples to choose from:
  - inventory and orders with lead times and uncertain demand;
  - incident handling with dependencies, retries and idempotency;
  - capacity scheduling with arrivals.
- **Rules.** Public and complete. The only hidden things are the future events, as in reality.
- **Score.** The realised objective (profit, cost, service level) on paired seeds, normalised through anchors:
  - a myopic policy (0);
  - a strong heuristic policy with far more compute (1);
  - reported against the **hindsight optimum** of the realised scenario, computed offline, as a bound.
- **Hard constraints.** Duplicate side effects, invalid actions and broken invariants. They are checked over the whole run and recorded; the card declares their penalty.
- **Why it resists shortcuts.** The future is not observable, so no search over the scenario is possible. A program the model writes must still choose a good policy.
- **Admission.** The offline baselines must show a gap of at least 0.3 normalised between the myopic and the strong policy, and the strong policy must stay clearly below the hindsight bound. Otherwise the environment is changed before any paid run.
- **Size.** One environment for the prototype, with 10 dev seeds. Three environments and 30 tasks for validation. Structure group = environment.

### 3.5 VIS v2: visual design (core, visual)

- **Briefs.** At least eight briefs of different kinds:
  - an information-dense dashboard;
  - an editor;
  - a multi-step form;
  - a landing page for each of two different brands;
  - a mobile-first page;
  - a data table with filters;
  - an empty or error state set.

  Each brief is written by us and reviewed by the user.
- **Functional checks.** Extend the existing renderer (`scripts/render_frontend.mjs`: playwright-core and a headless Chromium shell, already sandboxed, which today captures viewports and form states) with a scripted interaction flow per brief: clicks, inputs, navigation, expected states and responsive breakpoints.
- **Aesthetics.** Pairwise blind judging with both orders and same-vendor avoidance (the existing tournament), against fixed anchor pages per brief. Ratings use Bradley–Terry with intervals by bootstrap over briefs.
- **Calibration.** A small set judged by the user, to check judge agreement.
- **Size.** Structure group = brief. Dev 3 briefs, validation 5 briefs.

### 3.6 AE: algorithm engineering (frontier; existing 0.1.0)

v0.2.0 changes:

- **Raw values.** The headline is the raw AtCoder performance, normalised through anchors (naive reference 0, the contest's median contestant 0.5, the winner 1), uncapped. Rungs are labels only. Beating the winner shows as a value above 1, extrapolated from the performance table's top slope and marked as an extrapolation.
- **Seeds.**
  - **Official private seeds:** comparable with the human standings.
  - **Fresh seeds** drawn by us: generalisation; reported separately, never ranked against humans.
  - Both are marked "public contest" for contamination.
- **References.** A naive and a greedy reference for every problem, not only the four in the 0.1.0 calibration. Validation uses the ten short contests; long contests with relative scoring come later.

### 3.7 Later candidates (not in v2.0)

- **LR, library rebuild** (Commit0, MIT). Scored by behaviour groups (modules), not by raw test counts. Limit memorisation by preferring mid-popularity libraries, and flag it.
- **RC, reasoning certificates.** Novel rule systems; answers with machine-checkable certificates; unsatisfiable and insufficient-information cases included.
- **EC, constructed recovery.** Services with fault-injection hidden tests (idempotent retries, partial failures). Build it only if ER lacks such issues.

## 4. Authoring workflow (every family)

1. **Capability card** (`docs/templates/CAPABILITY_CARD.md`), reviewed against the principles in README §3.
2. **Source and licence** recorded. Provenance for every task:
   - source;
   - publication date;
   - licence;
   - exposure: `public`, `private-to-runs` or `generated`.
3. **Offline baselines:**
   - the cheapest shortcut (try it);
   - a naive strategy;
   - a strong strategy where one exists.

   The card records their scores. A family where the cheapest shortcut scores near the top is redesigned.
4. **Grader verification** (VALIDATION §1): references, null agent, mutants, alternative valid solutions, adversarial submissions, coverage invariants, noise.
5. **Splits** assigned by structure group and fixed in the manifest (`split` per item).
6. **Dev pilot** (PROTOCOL §1 dev pool) with the budget curve. Audit every failure, and a sample of successes.
7. **Freeze**: task version, grader version, anchors, budget.
8. **Validation run**, then holdout after the release freeze.

## 5. Refresh

- **ER:** add a dated batch when SWE-bench-Live publishes one and at least two months have passed since the pool's newest model release. Each batch is a new family version.
- **AE:** add problems when ALE-Bench adds contests.
- **AR:** fixed; ARC releases new public sets rarely.
- **AP, VIS:** new environments and briefs by version.
- Refreshed material starts in dev or validation, never directly in a release row.

## 6. Layout

```
task-library/
  basic/      t1-evidence-recovery, t2-finance-desk, eng-005-long-cycle-maintenance, e4-terminal-tasks, e2-spec-implementation, eng-001-..., eng-004-...
  core/       er-live-repair, ar-abstraction, r3-logic-grid, ap-<environment>, vis-v2
  frontier/   ae-heuristic-contests
  retired/    t2-service-desk, r1-rostering, rsn-001-..., rsn-002-..., tool-001-..., vis-001-original-landing
  research/   (unchanged)
```

Moving a package changes its path, not its id or version. Plans pin by path and manifest hash, so moved packages get re-pinned in new plans; historical plans keep their old paths and stay readable through the frozen worktrees of their runs.
