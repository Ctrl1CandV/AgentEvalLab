# v2 Code Architecture

What the code keeps, what it adds, the v2 schemas, and how to migrate without losing the v1 history. The aim is a working v2 with the smallest risk, not a rename of every module.

## 1. What stays

These modules carry the evidence of the v1 results and have tests. They stay in place and change only where a v2 feature needs them.

| Module | Role |
| --- | --- |
| `src/harness/pi.ts`, `profiles.ts`, `tools.ts`, `budget-notice.ts`, `provider-errors.ts` | Pi 0.87.1 sessions, tools, budget notices, error classes |
| `src/sandbox.ts`, `scripts/sandbox_exec.py`, `src/command.ts` | bubblewrap isolation, commands |
| `src/evaluation/run.ts`, `trajectory.ts`, `trajectory-snapshot.ts`, `batch.ts`, `provider-slots.ts`, `workspace.ts`, `artifacts.ts` | trial execution, trajectories, batch policy, workspaces, artifact snapshots (links skipped since 838a90d) |
| `src/evaluation/manifest.ts`, `items.ts`, `evaluator.ts`, `grader.ts`, `regrade.ts`, `preflight.ts`, `condition.ts`, `validate.ts` | packages, items, grader protocol, append-only re-grading, preflight, condition fingerprints, plan validation |
| `src/suite/*` | the frozen-worktree suite runner: freeze, generate, preflight, smoke, launch, retry, resume, runtime guard |
| `src/visual/*`, `scripts/judge-tournament.ts` | visual rendering and pairwise judging |

## 2. What is added

| Module (new) | Contents |
| --- | --- |
| `src/scoring/model.ts` | Builds the task outcome record (MEASUREMENT §2) from a validated grader result and the manifest's `scoreModel`: groups, resolved, diagnostic, metrics, normalised, primary, format |
| `src/scoring/anchors.ts` | Piecewise-linear normalisation through anchors, uncapped above, floored at 0; flags extrapolation |
| `src/scoring/aggregate.ts` | Task means over repetitions; family means with structure-group caps; capability means with declared weights; saturation indicators |
| `src/scoring/bootstrap.ts` | Seeded cluster bootstrap over structure groups (2,000 resamples); paired differences by task |
| `src/analysis/evidence.ts` | The evidence table, from v1 suite reports and run records (by version, protocol, coverage, n) and from v2 outcome records |
| `src/analysis/report-v2.ts` | The suite report v2 (MEASUREMENT §7), as Markdown and JSON |
| `scripts/evidence-table.ts` | CLI for the evidence table over `runs/` |
| `scripts/audit.ts` | Samples resolved and perfect trials per family (VALIDATION §2) and runs the family's audit suite on their snapshots; writes `docs/audits/...` |
| runtime mounts | Read-only dependency directories declared by a package, mounted by `execute_command` and by graders, with declared environment variables (§4) |
| answer-only profile | `toolProfiles: ["none"]`: no tools, a single reply (AR answer-only, R3); needs no trusted execution |
| repository workspaces | Projection of a package repository as a fresh single-commit git repository (ER) |

`src/evaluation/statistics.ts` stays (`pairedDifference`, Wilson, pass@k) and is used by `src/scoring/bootstrap.ts` for cross-checks. `src/suite/score.ts` and `src/suite/report.ts` keep producing the v1 report for v1 families. v2 families get the v2 report, and a suite with both shows both sections until v1 families are migrated.

## 3. Schemas

All new fields are validated as strictly as the v1 ones: unknown keys are refused, ranges checked, ids identifiers.

### 3.1 Manifest v2 (`schemaVersion: 2`)

All v1 fields stay, plus:

```jsonc
{
  "schemaVersion": 2,
  "tier": "basic" | "core" | "frontier",
  "capabilities": ["engineering"],            // primary first; from: engineering, reasoning, agentic, visual
  "card": "card.md",                          // capability card, hashed as a trusted file
  "scoreModel": {
    "primary": { "kind": "resolved" } | { "kind": "metric", "metric": "performance" } | { "kind": "rating" },
    "groups": [
      { "id": "fail-to-pass", "weight": 0.7, "critical": true, "rule": "all", "checkIds": ["..."] },
      { "id": "no-regression", "weight": 0.3, "critical": true, "rule": "fraction", "checkIds": ["..."] }
    ],
    "metrics": [
      { "id": "performance", "unit": "AtCoder performance", "direction": "higher",
        "anchors": { "version": "1", "points": [ { "name": "naive", "maps": 0 }, { "name": "median-contestant", "maps": 0.5 }, { "name": "winner", "maps": 1 } ] } }
    ],
    "format": { "checkId": "answer-format", "penalty": 0.2 },
    "structureCap": 0.2
  },
  "items": [
    { "id": "...", "level": "...", "files": [], "activeRequirementIds": [],
      "split": "dev" | "validation" | "holdout",
      "structure": "repo:pallets/click",          // structure group
      "provenance": { "source": "SWE-bench-Live", "published": "2026-08-14", "license": "BSD-3-Clause", "exposure": "public" },
      "anchors": { "performance": { "naive": 723, "median-contestant": 1310, "winner": 3390 } } }  // per-item anchor values
  ],
  "runtime": { "mounts": [ { "path": "runtime/py", "env": { "PYTHONPATH": "{mount}/site" } } ] }
}
```

- A package without items (eng-001, a trajectory such as E3) is one task: its `split`, `structure`, `provenance` and `anchors` sit in a top-level `"task"` object instead (added in PLAN-007 WP1.1).
- Per-item headlines (added in PLAN-007 WP2.2): `scoreModel.primaryByItem` maps an item id to its own primary, and a metric group may name the `items` it applies to (every item when omitted). A package that holds contract items and an open-ended one (E4: the terminal tasks and compress) keeps one grader, and the suite splits it into families by items. A suite family whose items have different headlines is refused (`SUITE_FAMILY_MIXED_PRIMARY`). Anchors are required only for the metrics a task is scored on: its headline metric and the metric groups that apply to it. A metric may name the `items` whose grading reports it (every item when omitted); a grader must report it for those items, and a task may be scored only on metrics its grading reports (`INVALID_SCORE_ITEMS`).
- Repository items (PLAN-007 WP2.4, §5): `"repository": { "archive": "private/repos/<name>.tar", "directory": "repo" }` on an item; the archive is a hashed trusted file. `"mounts": ["runtime/<name>"]` on an item selects the runtime mounts it binds (all of them when omitted).
- Every file under `runtime/` is hashed as a trusted file (no cache exception), and a mount is one directory `runtime/<name>`.
- A v1 manifest (`schemaVersion: 1`) still loads, and its family is reported by the v1 rules. A v1 manifest carrying any v2 field is refused.
- `scoring.weights` (v1) and `scoreModel` (v2) never appear in the same manifest.
- `task_packages.py` validates the v2 fields:
  - the card file exists and is hashed;
  - the splits are assigned and disjoint by structure;
  - the anchors are complete;
  - the groups cover every check of every active requirement (the format check apart), and each check is in one group only;
  - runtime mounts and repository archives are hashed, and items name only declared mounts.

### 3.2 Grader result v2 (`schemaVersion: 2`)

The v1 fields stay, plus:

```jsonc
{ "metrics": [ { "id": "performance", "value": 1547, "unit": "AtCoder performance" }, { "id": "total", "value": 289391 } ] }
```

- Metric values are finite numbers.
- Each metric the manifest's `scoreModel` names is required (for the items it names, when it names some).
- Other metrics are recorded as diagnostic.

### 3.3 Plan (`schemaVersion: 3`, extended, backward compatible)

New optional fields:

```jsonc
{
  "protocol": { "track": "fixed" | "curve", "split": "dev" | "validation" | "holdout", "label": "fixed-B" },
  "repetitionSubset": { "repetitions": 3, "items": ["..."] }
}
```

- `commandLimits` already exists (b46c859).
- A plan whose items mix splits is refused. A holdout plan needs `"protocol.track": "fixed"`, and its family must be frozen: the manifest hash is listed in the release file.

### 3.4 Suite v2 (`schemaVersion: 2`)

```jsonc
{
  "schemaVersion": 2,
  "name": "core-validation",
  "release": "v2.0-rc1",
  "split": "validation",
  "providerConcurrency": { "*": 6 },
  "policy": { },
  "capabilityWeights": { "engineering": { "ER": 0.8, "E4-compress": 0.2 } },
  "composite": null,
  "families": [ { "id": "ER", "kind": "single", "tier": "core", "capability": "engineering", "template": "...", "openEnded": false } ]
}
```

- The `target` (v1 "deepseek below 80%") is removed.
- The report flags saturation and headroom (MEASUREMENT §6) instead.

### 3.5 Outcome and report files

- **Outcome file.** Each trial directory gets `outcome.json` (MEASUREMENT §2), written when the score run is appended. Re-grading appends a new outcome alongside the new score run.
- **Report files.** The suite report v2 is `report-v2.json` plus `report.md`.

## 4. Runtime mounts (ER, later LR)

- **Mounts.** A package may ship `runtime/<name>/`: a Python site directory built by its builder from vendored wheels, with `pip install --target` and no network at run time.
- **Inside the sandbox.**
  - `execute_command` and the graders bind every declared mount read-only, at `/runtime/<name>` inside the sandbox.
  - They set the declared environment, with `{mount}` replaced by that path.
  - `scripts/sandbox_exec.py --mount SOURCE:/runtime/<name> --env NAME=VALUE`; the harness passes both through `isolatedCommand(..., runtime)`. Graders get the same in the request's `runtime` field (`mounts` with `source` and `target`, and `env`) and pass them to the launcher.
  - Without the sandbox (`isolation: "host"`, an explicit opt-out), nothing is bound and the environment names the source directories.
  - Mounts are bound in single-session trials; a trajectory package with mounts is refused at preflight.
- **Size and hashing.** Runtime mounts can be large. A small one is a directory `runtime/<name>` whose every file is hashed as a trusted file. A large one (PLAN-007 WP3.2) is one tar archive declared as `{"path": "runtime/<name>", "archive": "assets/<file>.tar", "env": {...}}`: the archive is a hashed trusted file, and the harness unpacks it once into a cache keyed by its hash (`~/.cache/agenteval/runtime/<sha256>/`, or `AGENTEVAL_RUNTIME_CACHE`) and binds that directory at `/runtime/<name>`.
- **External assets.** Trusted files under `assets/` (runtime archives, repository archives) are kept out of Git (`.gitignore`): builders store them in a content-addressed cache (`~/.cache/agenteval/assets/<sha256>`), and `scripts/prepare-assets.mjs` restores them into their packages by hard link, verifying each hash. `npm ci` runs it, and the suite runs it in its frozen worktree (`FREEZE_ASSETS_FAILED` when one is missing). The harness and `task_packages.py` check that `assets/` holds exactly the declared files.
- **Disk.** Keep each runtime under about 200 MB. Share one runtime between tasks of the same repository and version, as a directory referenced by several items.

## 5. Repository workspaces (ER)

- The builder stores each task's repository as a tarball of the working tree at the base commit, without `.git`. The tarball is a trusted file.
- At projection, the harness (`src/evaluation/repository.ts`):
  1. unpacks the repository into the item's `directory` (`repo/`);
  2. runs `git init`;
  3. commits every file of the archive once (ignored files too) under a fixed author and date (`agenteval`, 2000-01-01), so the same tree always gives the same commit;
  4. keeps a bare copy of that commit outside the workspace.

  The issue text is item material: `items/<id>/prompt.md` (appended to the prompt) and `items/<id>/public/ISSUE.md` (projected as `public/ISSUE.md`, beside `repo/`). This gives the model a clean history and the grader a clean diff.
- The delivery is the change, not the tree. After the session the harness reads the working tree against the single commit through its own bare copy (new files included, files the repository's `.gitignore` names excluded, the model's own commits counted), whatever the model did to the workspace's `.git`. It is saved as `submission.patch` beside the trial (at most 10 MB; larger is a resource-limit failure of the delivery), and the repository directory is left out of the artifact snapshot.
- The grader request carries `patchRef` (the patch, under the evidence root) and `runtime` (§4). The grader unpacks the archive afresh, applies the patch, restores every file the gold test patch touches to its base version and applies the gold test patch, so edits the model made to those files do not count, then runs FAIL_TO_PASS and PASS_TO_PASS in the sandbox with the runtime mount. `tests/runtime-workspace.test.ts` holds a fixture grader that does exactly this.

## 6. Target layout

```
src/
  harness/      (unchanged)
  evaluation/   (unchanged roles; manifest v2, grader v2, runtime mounts, repository workspaces)
  scoring/      (new) model.ts anchors.ts aggregate.ts bootstrap.ts
  analysis/     (new) evidence.ts report-v2.ts saturation.ts
  suite/        (suite v2; v1 path kept until migration ends)
  visual/       (unchanged; VIS v2 briefs are package data)
task-library/   basic/ core/ frontier/ retired/ research/   (TASK_LIBRARY §6)
suites/         basic.json core-dev.json core-validation.json frontier-dev.json (+ v1 dev.json/full.json kept until migration ends)
docs/           design/v2/  plans/  audits/  evidence/  reviews/  archive/
```

Do not move or rename stable modules only for tidiness. Move a file when its role changes.

## 7. Migration

1. **Tag** the last v1 commit as `v1-final`, locally, without pushing.
2. **Schema and scoring** (PLAN-007 Phase 1) land with dual-read support, so v1 packages and runs keep working.
3. **Packages move tier by tier** (Phase 2). Each move:
   - rebuilds the manifest only if its content changed;
   - re-pins the current plans;
   - leaves historical plans and runs untouched.
4. **Retired packages** stay readable under `task-library/retired/`. Suites stop referencing them.
5. **v1 suites and reports.** `suites/dev.json` and `suites/full.json` remain until every family they use is migrated or retired, then move to `docs/archive/`.

## 8. Tests (added with each work package)

- Scoring:
  - anchors: uncapped, floored, extrapolation flag;
  - groups: rules `all`, `fraction`, `metric`;
  - structure caps;
  - bootstrap: seeded determinism, n too small;
  - paired differences.
- Manifest v2 validation: each new field, refusals, v1 still accepted.
- Grader result v2: metrics required by the score model.
- Report v2: golden-file test on a fixture suite with v1 and v2 families.
- Evidence table: fixture runs of v1 suites, with dry runs excluded.
- Runtime mounts: a mount visible read-only in the sandbox, not writable, with its environment set.
- Repository workspaces: a fresh single-commit history; test files restored before grading.
- AR: grading of pass@2 and of malformed replies.
- T2 coverage invariant: negative tests for an unknown request, actions before the first `begin`, a request reopened, and requests out of order.
- Every new family's self-calibration is run by `npm test` when it is fast (under 2 minutes). Otherwise it is listed in `docs/audits/` with its last result.
