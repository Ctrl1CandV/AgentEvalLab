# v2 Validation

How we establish that a family measures what its card says, and that a difference between models is real.

## 1. Grader verification gates (before any paid run)

Every family passes all of these offline, and its self-calibration script checks them on every rebuild.

| Gate | Requirement |
| --- | --- |
| References | Every reference solution, and every gold patch for ER, gets its expected outcome: resolved, or its expected anchor value. |
| Null agent | An untouched workspace or an empty reply scores 0 (not resolved; normalised 0). |
| Mutants | At least one wrong solution per behaviour group fails that group. |
| Alternative valid solutions | At least two independently written correct solutions per family pass. This guards against over-specified checks. |
| Adversarial | Attempts to cheat change nothing: editing tests, tampering with judge files, reading private material, writing outside the workspace, faking a score. |
| Coverage invariant | Every state-changing action the model can take is attributed to exactly one graded unit, or makes the task fail. There are negative tests for unattributed or out-of-order actions. This is the lesson of the T2 `R999` hole. |
| Global end state | Families with state check the final state from the original start, beside any local diagnostic grading. |
| Noise | Timing-sensitive families judge the same submission on a quiet and on a loaded machine, with identical verdicts and a rank change within the declared tolerance. |
| Determinism | Grading the same snapshot twice gives identical records. |

## 2. Audits

**Failure audits** (unchanged practice): every failure in a dev pilot is read before it counts. Defects in the task, grader or harness are fixed with a version bump and a re-grade of every model.

**Success audits** (new):

- After every dev pilot and validation run, sample per family:
  - all resolved trials, if there are at most 10;
  - otherwise 10, plus every trial with a perfect score.
- Re-check each with an **audit suite** that is not part of scoring. It holds independent tests written from the public contract: property tests, boundary cases, state-sequence checks, and the hidden-test variants of ER (the full repository test suite).
- Record each finding as one of:
  - **true pass**;
  - **false pass** (the grader missed a defect);
  - **false fail** (found in failure audits);
  - **beyond contract**: the audit tests something the contract does not require; it never changes a score.
- A false pass is a grader defect. Fix it with a version bump and re-grade every model.

Audit records live in `docs/audits/<family>/<date>.md` with a JSON twin. A report shows each family's latest audit date and result (MEASUREMENT §7).

## 3. Splits

- Assign **dev**, **validation** and **holdout** in the manifest, by structure group (TASK_LIBRARY §4), before the first pilot of the family.
- **dev:** inspect freely; tune the task and the grader.
- **validation:** run once per freeze. Results may lead to one more design iteration, which uses a new freeze and, ideally, fresh validation tasks.
- **holdout:** run only after the release freeze. Its results are reported as they are; there is no tuning afterwards.
- The validation and holdout task contents are not opened while designing. Only their structure metadata (counts, sizes) may be read.

## 4. Release gates (v2.0 and later releases)

A release is published only when the following questions are answered and the answers recorded in the release review.

1. **Success audits.** Do resolved submissions pass the audit suites, with no false passes outstanding?
2. **Contract.** Does every hidden check trace to the public contract, and do alternative valid solutions pass?
3. **Holdout.** Do the differences seen on validation hold on holdout? Report the pairwise intervals per capability, not one rank.
4. **Source of differences.** Are differences driven by content, rather than format, infrastructure or provider refusals? Report coverage and format separately.
5. **Headroom.** Do simple strategies, strong strategies and the best models differ materially on at least part of each core family? What are the saturation indicators?
6. **Budget.** Does quality still rise with budget (the budget curve), or is the budget mostly buying repeated context?
7. **Coverage.** Are engineering, reasoning, agentic tool use and visual design each covered by at least one validated core family, and not only by optimisation?

A "no" is fixed at its cause. Scores are never rescaled, normalised within the board, or given ad hoc thresholds to land in a target range.

## 5. Versioning

- **Versions.** Task, grader and anchor versions are separate. A change to any of them makes a new version and a new manifest hash.
- **Re-grading.** A grader fix that keeps the task version re-grades every model's affected trials into new score runs (append-only). Reports show the new version, and the old one stays readable.
- **Releases** (v2.0, v2.1, ...) freeze a suite, its families' versions, its budgets and its composite weights, if any.
- **Bridge tasks** (TASK_LIBRARY §2) run in every release, so that releases can be linked. They are never re-scored under another release's rules.

## 6. Demotion and promotion

**Demotion.** A core family moves to basic when, on the current pool and at least one validation run:

- at least 60% of its tasks are resolved by every model;
- or, for open-ended families, at least 60% of tasks have every model above the strong anchor.

The release notes say so. New material for that capability is added to the core.

**Promotion.** A frontier family moves to core when the pool spreads on it, with a pairwise interval that excludes 0 for at least one pair, and when at most 20% of its tasks are solved by every model.
