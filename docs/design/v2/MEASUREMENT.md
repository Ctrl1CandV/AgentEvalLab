# v2 Measurement Model

How a trial becomes a task outcome, how outcomes aggregate, and what a report shows. Binding for every v2 family; v1 runs are reported under their own rules (see "Legacy results").

## 1. Units

| Unit | Meaning | Statistical role |
| --- | --- | --- |
| **Family** | a set of tasks with one capability card, one grader version and one protocol | reporting row |
| **Structure group** | tasks that share a source or template: one repository, one contest problem, one generator template, one design brief | cluster for intervals and splits |
| **Task** | an independent unit with its own public contract: an issue in a repository, an ARC task, a contest problem with its seed set, an environment with a seed, a design brief | **the sample** |
| **Trial** | one attempt by one model on one task under one protocol | repetition |
| **Check / test / cell / stage** | evidence inside a task | never a sample |

A trajectory (E3) is one task, not seven. A logic grid (R3) is one task, not 81 cells.

## 2. Task outcome record

The harness computes one record per trial from the grader result (schema in [CODE](CODE.md) §3) and the manifest's score model.

| Field | Meaning |
| --- | --- |
| `resolved` | `true`/`false`: the task's declared success criterion holds (all critical groups pass; for open-ended tasks, a valid delivery). `null` only for an unscored trial. |
| `groups` | `{id: {score ∈ [0,1], weight, critical}}`. Behaviour groups declared in the manifest. A group's score comes from its checks, by the group's rule (`all`, `fraction`, or `metric`). |
| `diagnostic` | Σ weight·score / Σ weight over groups: partial credit for locating errors, **not** the headline |
| `metrics` | raw values reported by the grader: `{id, value, unit, direction}`, e.g. contest total, AtCoder performance, runtime, bytes, reward, regret, tests passed |
| `normalised` | for each metric with anchors: the value mapped piecewise-linearly through the anchors, extended linearly above the top anchor with the last segment's slope, floored at 0; **never capped** |
| `primary` | the family's declared headline for the task: `resolved` (0/1) for contract tasks, `normalised[<metric>]` for open-ended tasks |
| `format` | `strict`, `recovered` or `missing`; a recovered answer loses the family's format deduction (10% in v2) from the primary itself, and the value before the deduction is kept (`format.content`) (user decision of 2026-10-25: following the required format is part of the ability) |
| `stop` | `done`, `budget`, `timeout`, `output_limit`, `model_error`, `infrastructure` |
| `usage` | input, cache read, cache write, output and reasoning tokens (where the provider reports them), model calls, tool calls, wall time, and tool CPU time where measured |
| `coverage` | `scored`, `unscored` (with the reason), or `not_run` |

### Primary scores by family type

| Type | Primary | Also reported |
| --- | --- | --- |
| Contract (ER, AR, R3, basic tier) | `resolved` | diagnostic; tests passed and regressions (ER); cell accuracy and constraint validity (R3) |
| Open-ended (AE, AP, E2 routes, E4 compress) | normalised objective | validity, raw objective, distance to each anchor |
| Comparative (VIS) | rating from pairwise judgements against fixed anchor pages; functional `resolved` reported separately | per-brief ratings, judge agreement, order consistency |

## 3. Anchors

- An anchor is a declared, versioned reference value for a metric:
  - **naive**: a simple valid strategy;
  - **baseline**: a competent generic method;
  - **strong**: a strong method run with far more compute than the trial budget, or a human expert;
  - **bound**: a provable bound where one exists, such as the hindsight optimum.
- A family declares which anchors it uses and the normalised value each maps to (default: naive 0, baseline 0.5, strong 1).
- An anchor that a trial exceeds stays as it is; the trial's normalised value goes above 1. A new anchor is a new version.
- Anchors from humans (AE) record their source: contest, date and number of contestants. Anchors from compute record their method, compute and date.
- Values that are not anchors are only labels: rungs, "beat x% of contestants". A label may be shown, but never replaces the value.

## 4. Aggregation

1. **Per task.** Average the primary over the task's scored trials (repetitions).
2. **Per family.** The mean of the per-task primaries, each task weighted equally. A structure group contributing more than its declared cap (default 20% of a family's tasks) is down-weighted to the cap.
3. **Per capability.** The mean over its core families with weights declared and frozen per release. Basic and frontier tiers are reported as their own rows and never averaged into the core.
4. **No single overall number by default.** A release may declare a composite with frozen weights. It is labelled "composite" and shown after the profile.
5. **Efficiency profile.** Per model and family:
   - median tokens, by kind;
   - median wall time;
   - median model calls;
   - tokens per resolved task.

   Reported, never scored.

## 5. Uncertainty and comparisons

- **Intervals** come from a cluster bootstrap over structure groups (tasks resampled by group; 2,000 resamples; percentile 95%). With fewer than five groups, report "n too small" instead of an interval.
- **Model comparisons** are paired by task. Per capability, report:
  - the mean difference;
  - a cluster-bootstrap interval;
  - the number of tasks;
  - the share of tasks where each model is ahead.

  The existing `pairedDifference` stays for task-level t intervals as a cross-check.
- **Repetitions** estimate within-task variance on a declared subset ([PROTOCOL](PROTOCOL.md) §6). They never stand in for more tasks.
- Small-sample results are labelled **exploratory** in every report.

## 6. Saturation and headroom indicators

Per family and model pool:

- the share of tasks resolved by every model ("solved by all");
- the share resolved by none ("solved by none");
- the share of open-ended tasks where the best model exceeds the strong anchor;
- the spread: best family score minus worst.

The demotion rule ([VALIDATION](VALIDATION.md) §6) reads these.

## 7. Report contents (report v2)

A suite report, in order:

1. **Header.**
   - Release, suite, commit and protocol track.
   - The model pool, with labels, thinking levels, temperature and the model snapshot information available.
   - Split, budgets, context policies, command limits.
   - The label "exploratory" where it applies.
2. **Capability profile** per model: the primary per capability with interval and number of tasks, then the basic and frontier rows.
3. **Family tables.** Per model:
   - tasks and trials;
   - coverage (scored, unscored, not run);
   - resolved rate;
   - primary mean with interval;
   - diagnostic mean;
   - medians of the key raw metrics;
   - format compliance;
   - stops by kind;
   - infrastructure failures.
4. **Pairwise comparisons** per capability.
5. **Saturation and headroom indicators.**
6. **Efficiency profile.**
7. **Audit status.** For each family: date and result of the latest success audit and failure audit.
8. **Links** to every run directory and trial.

Every number traces to a trial record. A dry run is never shown as a result.

## 8. Legacy results

v1 runs keep their scores and reports. The evidence table (PLAN-007 Phase 0) lists, for each v1 result:

- task version;
- grader version;
- protocol (budget, context policy, thinking);
- models;
- the number of items and trials;
- completion status;
- the run directory.

A v1 package migrated to v2 is re-graded into a new score run. Its v2 numbers appear under the v2 version only.
