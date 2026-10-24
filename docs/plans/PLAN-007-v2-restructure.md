# PLAN-007: The v2 Restructure

Status: proposed, 2026-10-24. Design: `docs/design/v2/`. The third-party review `docs/reviews/2026-10-24-third-party-evaluation-review.md` is binding evidence for this plan.

## Rules for carrying it out

- **One kind of change at a time.**
  - Phases 0–3 make no paid model runs.
  - Phase 4 runs families one by one, or merges families whose smoke tests passed.
  - The task design, weights, models, budgets and session policy never change together. Then every change in results has a known cause.
- **Every work package ends with a commit.** Tests are green, `python3 scripts/task_packages.py check --plans <current plans>` passes, and a short note goes in the phase's review document.
  - Commit only; never push.
  - Use the identity `-c user.name=liuyijie -c user.email=126372470+Ctrl1CandV@users.noreply.github.com`.
  - Check `git diff --cached --name-only | grep '/\.'` for sandbox placeholders before committing.
- **Audit failures and successes.** Every failure is audited before it counts (PLAN-005). Every pilot gets a success audit (VALIDATION §2).
- **Report in Chinese** to the user at the end of each phase: what was done, the results, and what needs their decision.

## Phase 0: v1 baseline, evidence and hygiene (no paid runs)

| WP | Work | Done when |
| --- | --- | --- |
| 0.1 | Tag the current HEAD `v1-final` (local tag). Write `docs/evidence/README.md` explaining the evidence folder. | The tag exists. |
| 0.2 | **Evidence table.** `scripts/evidence-table.ts` reads `runs/suites/*/suite.json` and `report.json`, plus the plain runs cited by the reviews. It writes `docs/evidence/V1_EVIDENCE.md` with, per family and model: task and grader version, protocol (budget, context policy, thinking), items and trials, coverage, score, completion status, run directory. Dry runs, interrupted runs and configurations never run (such as T2 at 10M) are listed as such. | Every number in the review's §2 table can be found in the table with its provenance. Dry runs are not shown as results. |
| 0.3 | **T2 coverage hole** (review §3.7). In `t2-finance-desk`: every state-changing command must belong to exactly one legal request of the day. Unknown request ids, commands before the first `begin`, a reopened request and out-of-order requests each make the global resolved criterion fail and are listed in the evidence. Add a **global end-state check**: the final books from the original start equal the oracle's books for a correctly handled day. Keep the per-request diagnostic. Add negative tests for each case to the self-calibration. Bump the grader version, then re-grade every T2 finance trial (all models) into new score runs. | The review's `R999` reproduction no longer scores full marks. Legitimate alternative flows still pass. Re-grades are recorded in the evidence table. |
| 0.4 | **Success audits of the high-scoring v1 families**, offline, on their stored snapshots: T1 F4/F5 full-score trials; T2 fn1/fn2 of deepseek and qwen; E3 final snapshots; E4 speedup; VIS functional passes. Write `docs/audits/<family>/2026-10-xx.md` with findings classified as in VALIDATION §2. | Each audited family has a record. Any false pass is fixed with a version bump and a re-grade. |
| 0.5 | **Document sync.** HANDOFF states the v1 final state and points to v2. `FRONTIER_TASKS.md` is marked superseded by `docs/design/v2/`, and its percentile wording corrected. The AE calibration table's "634.5 of 583" becomes "rank 634.5 (performance rank) of 682 contestants", folded into AE 0.2.0 so the package is rebuilt only once. | No document contradicts the code or the evidence table. |

## Phase 1: measurement layer (no paid runs)

| WP | Work | Done when |
| --- | --- | --- |
| 1.1 | **Manifest v2** (CODE §3.1) in `src/evaluation/manifest.ts`, with v1 still accepted. v2 checks in `scripts/task_packages.py`: card hashed, splits disjoint by structure, anchors complete, groups covering every active check. | Validation tests for every field and refusal pass; every v1 package still loads. |
| 1.2 | **Grader result v2** (CODE §3.2), with metrics required by the score model. | Protocol tests pass. |
| 1.3 | **`src/scoring/`**: `model.ts`, `anchors.ts`, `aggregate.ts`, `bootstrap.ts` (CODE §2, MEASUREMENT §2–6). | Unit tests: uncapped anchors and the extrapolation flag; group rules; structure caps; seeded bootstrap; "n too small"; paired differences. |
| 1.4 | **`outcome.json`** written with every new score run, by run, trajectory and regrade. | Fixture runs produce outcomes; re-grading appends a new outcome. |
| 1.5 | **Report v2 and suite v2** (MEASUREMENT §7, CODE §3.4). The v1 `target` is removed from v2 suites; saturation and headroom indicators added. The v1 report path stays for v1 families. | Golden-file test on a fixture suite with v1 and v2 families. |
| 1.6 | **Prove the layer on two real families, without model runs.** AE (metric primary, per-item anchors, uncapped; its references as trials) and R3 (resolved primary, cell accuracy diagnostic) as manifest v2. R3 by re-grading its stored v1 trials where the task text is unchanged; otherwise reported only from new runs. | `report-v2.md` for a fixture suite shows both correctly, with intervals and saturation indicators. |

## Phase 2: library reorganisation and harness features (no paid runs)

| WP | Work | Done when |
| --- | --- | --- |
| 2.1 | Move packages into `basic/`, `core/`, `frontier/` and `retired/` (TASK_LIBRARY §2, §6). Re-pin current plans. Write suites `basic.json`, `core-dev.json` and `frontier-dev.json` (suite v2). | Dry runs of the three suites pass preflight and the null-agent smoke. Historical runs still load in the evidence table. |
| 2.2 | Capability cards (`card.md`) for every retained family. Basic-tier cards may be short, but §4 "where the difficulty lies" must be honest; for basic, "reliability" is an answer. | Every non-retired package has a card hashed in its manifest. |
| 2.3 | Splits for R3, AE and the bridge tasks, by structure group (VALIDATION §3). | The manifests carry `split` and `structure`; the package check enforces them. |
| 2.4 | Harness features for Phase 3 (CODE §4–5): read-only runtime mounts with environment; the `none` tool profile (answer-only); repository workspaces with a fresh single-commit history. | Sandbox tests: a mount is visible and read-only, with its environment. An answer-only trial gets no tools. A repository workspace has one commit and the grader restores test files. |

## Phase 3: new families, built and verified offline (no paid runs)

Order by cost and certainty. Each family follows TASK_LIBRARY §4 up to step 5, and all its gates in VALIDATION §1 pass.

| WP | Family | Done when |
| --- | --- | --- |
| 3.1 | **AR** (ARC-AGI-1/2 public evaluation, Apache-2.0): answer-only and with-code protocols; pass@2 grading; splits by task. | Card done. References (the official solutions) resolve; null and wrong grids fail; malformed replies are graded by the format rules. 40 dev, 80 validation and 80 holdout tasks assigned. |
| 3.2 | **ER**: a builder that takes instances from the published pools (SWE-bench-Live to 2025-09, MIT; SWE-rebench leaderboard to 2026-03, CC BY 4.0) **and** from our own mining of recent merged fixes (TASK_LIBRARY §3.1). It filters them (Python, permissive licence, wheel-only dependencies, test time under 5 minutes), vendors wheels into runtime mounts, stores repositories, and validates each task: gold patch resolves, base fails, three agreeing runs, null fails. Dev comes from the pools, flagged per model; validation and holdout from mining dated after the newest pool model's release. | At least 10 dev tasks from at least 5 repositories, and at least 30 mined validation tasks from other repositories, have passed validation. The builder records why each rejected instance was rejected. Every model's release date is in the evidence table. |
| 3.3 | **AP prototype**: one environment (decision D7), its seeded event generator, the myopic and strong offline policies, and an offline hindsight-optimum solver. | The card shows a normalised gap of at least 0.3 between myopic and strong, and the strong policy clearly below the bound. Hard-constraint checks have negative tests. Otherwise redesign before Phase 4. |
| 3.4 | **VIS v2**: at least 8 briefs (decision D5); executed interaction checks; fixed anchor pages per brief; judge calibration set. | Functional checks pass on anchor pages and fail on broken ones. The tournament runs offline on anchor pages with judge agreement reported. |
| 3.5 | **AE 0.2.0**: scoring as in TASK_LIBRARY §3.6; naive and greedy references for all 10 problems; fresh-seed variant reported separately; calibration table fixed (WP0.5). | The self-calibration covers every problem. The report shows raw performance with anchors, uncapped. |

## Phase 4: dev pilots and budget curves (paid; envelope about 250M tokens)

- **Pool:** the dev pool (PROTOCOL §1).
- **Order:** AR, ER, AE, AP, VIS, then an R3 re-check. Merge into one suite launch only those families whose dry run passed.
- **Per family:**
  1. the budget curve on 3 dev tasks with the strongest dev model and one reference (PROTOCOL §2);
  2. the dev split at the chosen B;
  3. failure and success audits;
  4. fixing defects with version bumps;
  5. freezing B in the card.
- A family that shows no spread on dev is not tuned until it does. It is redesigned per its card's §4, or dropped, and the review says which.
- **Launching:** runs over about 1.5 hours are launched from the user's terminal (PROTOCOL §10), and watched with a background watcher.

Done when every core family has a frozen budget, dev results with audits, and an honest verdict: spread, no spread, or redesign.

## Phase 5: freeze and validation (paid; envelope about 400–600M tokens; needs D1 and D4)

- Freeze `v2.0-rc1`: families, versions, anchors, budgets, capability weights. Write the release file `suites/release-v2.0-rc1.json` with the manifest hashes.
- Run the validation split with the approved pool, including the repetition subsets.
- Answer the release gates (VALIDATION §4) in `docs/reviews/<date>-v2-validation.md`. One design iteration is allowed. It needs a new freeze and, ideally, fresh validation tasks.

## Phase 6: holdout and release (paid; envelope about 400–600M tokens)

- Run the holdout split on the frozen release.
- Write the release review, update the evidence table, HANDOFF and the memory notes.
- Apply demotions and promotions (VALIDATION §6).

## Decision points for the user (recommendations first)

| ID | Question | Recommendation |
| --- | --- | --- |
| D1 | The validation and holdout pool | Add one clearly stronger reference (a flagship or pro model available through the existing providers, chosen after a provider check) and one weaker one. The dev pool stays as it is. |
| D2 | Format deduction | Keep the 20% deduction as a separate `penalised` column. Use content as the headline. |
| D3 | A composite score | None in v2.0. Report the capability profile only. |
| D4 | Token envelopes per paid phase | Phase 4 about 250M; Phases 5 and 6 about 400–600M each. Re-approve when the budget curves are known. |
| D5 | VIS briefs and calibration | The user reviews the 8 briefs and judges a calibration set of about 20 pairs. |
| D6 | ARC public sets despite possible contamination | Include them, flagged. ARC-AGI-2 is far from saturated. |
| D7 | AP environment | Inventory and orders with lead times and uncertain demand: a clear objective, a computable hindsight bound, rich side effects. |

## Risks

| Risk | Mitigation |
| --- | --- |
| ER environments fail to build offline | Keep only wheel-only repositories. The builder logs every rejection. A smaller ER is better than a broken one. |
| Disk (runtime mounts, repositories) | Share runtimes per repository version; budget about 20 GB; check `df` in preflight. |
| Contamination of public sources | Date filters (ER); per-model flags; fresh seeds (AE) reported separately; never claim "unseen". |
| AP slides back into rule-following | Card §4 and the admission gap (WP3.3) are checked before any paid run. |
| Judge noise (VIS) | Both orders; anchor pages; intervals over briefs, not games; user calibration. |
| Costs overrun | Phase envelopes; worst-case preflight; breadth before budget. |
| Tuning to the dev pool | Splits fixed before pilots; validation used once per freeze; holdout only after the release freeze. |
