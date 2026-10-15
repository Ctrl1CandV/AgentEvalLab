# PLAN-005: Attributable Scores, Stated Budgets, and Discriminating Tasks

Updated 2026-10-15. Follows [PLAN-004](PLAN-004-model-evaluation-baseline.md), whose phases 1–4 are complete; see the [pilot results](../reviews/2026-10-15-pilot-results.md).

## Scope

The pilot showed that the harness runs reliably under real traffic. It also showed three weaknesses:

- Some deductions came from graders rather than from models.
- A format slip cost a model everything.
- The tasks are too easy to separate models.

This plan fixes the scoring and budget rules first, then rebuilds the task set for difficulty. Agent and harness comparisons remain out of scope.

## Principles (user decisions, 2026-10-15)

1. **Every deduction must be the model's fault.** A failure caused by the task or the grader is a defect. It is fixed with a version bump and never counted against a model.
2. **A format violation costs points, but not everything.** If a fixed, published recovery rule can extract the answer, the content is graded and a format deduction applies.
3. **One budget per task, the same for every model, and stated to the model.** At the budget the trial is cut off and graded as it stands. Budgets are generous: most models should finish within them. Models that overthink or keep retrying should surface and pay for it.
4. **Budgets are set from normal usage and are not raised for outliers.** glm's overthinking is treated as an individual case.
5. **Batch and per-model ceilings are spending fuses, not evaluation budgets.** They must never decide a result.
6. **Tokens are fixed units without prices** (decided earlier the same day).
7. **Thinking runs at a middle level, not the maximum:**
   - the vendor's named medium level where one exists;
   - otherwise the middle of its documented levels.

   This gives gpt-6-luna `medium` and glm-5.3 `high` (its levels are `low`, `high`, `max`).
8. **Tasks must discriminate.** Today's tasks are close to saturated, and they need a substantial redesign.

## Evidence from the pilot

- **Grader-caused failures.** Three defects made models fail for reasons the instruction does not support:
  - F1: the tool-001 trace format;
  - F2: tool-001 search evidence;
  - F7: zero counts in eng-001's `by_code`.

  The graders had been checked only against reference solutions and traces written under the same assumptions. A manual failure audit found all three.
- **Format.** glm-5.3 wrapped all three rsn-002 answers in a Markdown fence. With the fence removed, all three pass every content check.
- **Budget replay.** An offline replay re-executed each eng-001 trial's file writes and commands in the sandbox, then graded the workspace as it would stand at each token cutoff:

  | Trial | Total tokens | First reached 22/22 |
  | --- | --- | --- |
  | glm-5.3-flash, round 1 | 2,701K | by 100K |
  | glm-5.3, round 2, rep 1 | 1,031K | by 300K |
  | glm-5.3, round 2, rep 2 | 1,059K | by 50K |
  | gpt-6-luna, 5 complete trials | 24K–60K | by 50K (or never improved later) |

  Most of glm's tokens went to re-checking work that was already correct. The models ran without knowing their budget, so a stated budget may change this behaviour.
- **Ceiling effect.** gpt-6-luna passed at least 2 of 3 trials on every task. Both models passed rsn-001 and tool-001 3 of 3 in round 2. Four tasks with near-perfect scores cannot separate models.

## Work packages

### WP1. Attribution safeguards

- **Instruction traceability.** Every manifest requirement gains an `instructionClause`, a verbatim quote of the instruction sentence it enforces. `task_packages.py check` and a test fail when the quote is missing or not found in `instruction.md`. A check that enforces something no clause states is a grader defect by definition; F7 would have been caught this way.
- **Alternative-reading references.** Each package lists the details its instruction leaves open, such as listing zero counts, JSON key order and separators, or an evidence path written as `./deps.lock.json`. It also gains reference variants that take the other reading. Self-calibration requires every variant to pass.
- **Real traces.** Every grader that reads the tool trace is tested against a trace emitted by the Pi runner, as tool-001 now is.
- **Failure audit gate.** Before a task's results count, every failed critical check in its pilot is labelled in the pilot review as one of four causes:
  - model error;
  - grader defect;
  - task ambiguity;
  - infrastructure.

  A task with an open grader or ambiguity label cannot be frozen.

### WP2. Trial scores: format deduction and partial credit

- **Shared recovery rule** for answer-graded tasks (rsn-001, rsn-002, tool-001, and later families). Surrounding whitespace and exactly one enclosing Markdown code fence, optionally labelled `json`, may be removed. Nothing else is recovered: prose around the answer, several objects, or an edited structure still fails. The rule is stated in each instruction.
- **Grading.** When the strict parse fails and the recovery rule succeeds, content checks run on the recovered answer. `answer-format` then fails with reason `recovered`.
- **Trial score.**

  ```
  trial score = content score × (1 − formatPenalty), where the penalty applies only when the answer was recovered
  ```

  - The penalty is declared per task in the manifest; the proposed default is 0.25 (decision 1).
  - The content score is the weighted fraction of content checks passed, with equal weights unless the manifest says otherwise. Partial credit separates a 21/22 solution from a 0/22 one (decision 2).
- **Resolved.** A trial is resolved when every critical content check passes. pass^k and pass@k stay defined on resolved trials.
- **Reports** show:
  - mean trial score, with an interval clustered by task;
  - resolved rate;
  - format compliance rate;
  - the share of failures that are format-only.

### WP3. Budgets stated to the model

- **Budget per task**, identical for every model:
  - `maxTrialTokens`: all input and output tokens of the trial, cached input and reasoning included;
  - model calls and tool calls;
  - wall-clock timeout;
  - the per-request output cap.
- **Stated once.** The harness appends one fixed budget paragraph, the same template for every task and model, to the task prompt.
- **Stated each turn.** Before each further request, a short status message reports tokens used and remaining, calls used, and time used (decision 3). It is injected through Pi's steering hook, so tool results stay byte-identical and trace-based graders are unaffected. Without this feedback a model cannot act on a token budget, because it cannot count re-read context.
- **At the budget** the trial ends with `TRIAL_TOKEN_LIMIT` (or the matching limit) and is graded as it stands. This is implemented in PLAN-004 (F3, F8).
- **Setting values.** Budgets come from normal usage: about 10 times the median and at least 3 times the maximum of non-outlier pilot trials, rounded up. A budget-replay tool (the offline replay above, generalised) shows how each candidate cap would have scored past trials. Proposed values, under decision 4:

  | Task | Tokens per trial | Basis |
  | --- | --- | --- |
  | rsn-001, rsn-002 | 50K | normal maximum 9K |
  | tool-001 | 100K | normal maximum 13K |
  | eng-001 | 300K | luna maximum 60K; in the replay glm reached a correct solution within 300K in all three trials |

- **Spending fuses.** `--validate-only` prints the worst-case spend: planned trials × `maxTrialTokens`, plus at most one request each. Batch and per-model ceilings default to that figure, so they bind only on a harness bug.
- **Efficiency reporting.** Report tokens per trial, the share of trials that ran out of budget, and tokens per resolved trial. Whether staying within budget but spending most of it should also lower the score is decision 5.
- **Known limit.** Token counts depend on each model's tokenizer, so equal token budgets are only approximately equal work. Generous budgets keep the effect small.

### WP4. Conditions for the next runs

- Thinking at the middle level (principle 7): `supergpt:gpt-6-luna` at `medium`, and `supercn:glm-5.3` at `high`.
- Temperature 0 for all models.
- Add a third model, so item difficulty and discrimination can be estimated: `deepseek:deepseek-flash`, or `aliplan:qwen3.8-flash` once its quota resets on 2026-10-19.

### WP5. Discriminating task set (major)

- **Target.** On the pilot models, each task should land between 20% and 80% mean score. Tasks that every model saturates are retired from the comparison set.
- **Instance generators (F10).** The reasoning and tool families get parameterised generators. Difficulty knobs:
  - reasoning: number of constraints, instance size, infeasibility traps, multi-step derivations;
  - tool: snapshot size, distractors, deeper pagination, conflicting or multi-hop evidence.

  Instances are fictional and generated per run, which limits contamination. Each trial scores the fraction of instances solved.
- **Engineering.** Harder specifications with hidden edge cases, and maintenance tasks on existing code:
  - convert eng-002 and eng-003;
  - rebuild the eng-004 baseline;
  - run the eng-005 five-stage trajectory under a stated budget.
- **Difficulty calibration.** Compute per-item pass rates across at least three models, with a discrimination index. Item response theory comes once there are enough items and models.
- **Design first.** This package starts with a design document that surveys task designs from established benchmarks and proposes concrete families. The user reviews it before any build.

## Order

1. WP1 and WP2: scoring correctness. Re-calibrate the affected packages.
2. WP3: stated budgets; re-pilot on the current tasks with the WP4 conditions. This run is cheap and checks the mechanics, not difficulty.
3. WP5: design document, user review, build, pilot, and freeze the first comparison set.

## Decisions for the user

1. **Format penalty for a recoverable violation:** 0.25 proposed, so the trial keeps 75% of its content score.
2. **Partial credit:** should the trial score be the fraction of content checks passed, alongside the binary resolved rate?
3. **Per-turn budget status:** should the model see its remaining budget before each request, or only once at the start?
4. **Per-task token budgets:** 50K for reasoning, 100K for tool, 300K for eng-001 (table in WP3).
5. **Efficiency in the score:** should a model that finishes within budget but uses most of it lose points? Or should cost show only in the efficiency columns, and in the score only when the budget cuts the model off?
