# PLAN-005: Attributable Scores, Stated Budgets, and Discriminating Tasks

Updated 2026-10-16. Follows [PLAN-004](PLAN-004-model-evaluation-baseline.md), whose phases 1–4 are complete; see the [pilot results](../reviews/2026-10-15-pilot-results.md).

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

### WP1. Attribution safeguards (scaled down, 2026-10-16)

The user decided that graders improve through repeated testing, so heavy up-front machinery is not warranted. What remains:

- **Failure audit after every pilot.** Each failed check is traced to model, grader, task ambiguity or infrastructure before results count, as in the 2026-10 pilot. Defects are fixed with a version bump.
- **Real traces.** A grader that reads the tool trace is tested against a trace emitted by the Pi runner, as tool-001 now is.
- **Alternative readings on demand.** When an audit finds an ambiguity, add a reference variant for the other reading, as eng-001 0.3.2 did for zero counts.

Dropped as up-front requirements:

- a verbatim instruction clause for every requirement, enforced by `task_packages.py`;
- reference variants for every open detail of every package;
- a hard gate that blocks freezing a task until every failure is labelled.

### WP2. Trial scores: format deduction and partial credit (done 2026-10-16)

Implemented in `73b8b05` (harness) and `d6408b2` (rsn-001, rsn-002 and tool-001 0.5.0) with a format penalty of 0.2, by the user's decision. Under the new graders, glm-5.3's three fenced rsn-002 answers pass every content check and score 0.8.

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

### WP3. Budgets stated to the model (done 2026-10-16)

Implemented in `9f1c66b`. The budget is stated once in the prompt. Reminders arrive after passing 50%, 75% and 90% of any limit rather than every turn, by the user's decision, so that models do not fixate on the budget. The values in the table below were set by Claude, as the user asked, and are recorded in [the budget pilot](../../experiments/budget-pilot-2026-10/README.md).

- **Budget per task**, identical for every model:
  - `maxTrialTokens`: all input and output tokens of the trial, cached input and reasoning included;
  - model calls and tool calls;
  - wall-clock timeout;
  - the per-request output cap.
- **Stated once.** The harness appends one fixed budget paragraph, the same template for every task and model, to the task prompt.
- **Reminders.** After usage first passes 50%, 75% and 90% of any limit, a short status message reports tokens, calls and time used. It is injected through Pi's steering hook, so tool results stay byte-identical and trace-based graders are unaffected. Without this feedback a model cannot act on a token budget, because it cannot count re-read context.
- **At the budget** the trial ends with `TRIAL_TOKEN_LIMIT` (or the matching limit) and is graded as it stands. This is implemented in PLAN-004 (F3, F8).
- **Setting values.** Budgets come from normal usage: about 10 times the median and at least 3 times the maximum of non-outlier pilot trials, rounded up. A budget-replay tool (the offline replay above, generalised) shows how each candidate cap would have scored past trials. Proposed values, under decision 4:

  | Task | Tokens per trial | Basis |
  | --- | --- | --- |
  | rsn-001, rsn-002 | 50K | normal maximum 9K |
  | tool-001 | 100K | normal maximum 13K |
  | eng-001 | 300K | luna maximum 60K; in the replay glm reached a correct solution within 300K in all three trials |

- **Spending fuses.** `--validate-only` prints the worst-case spend: planned trials × `maxTrialTokens`, plus at most one request each. Batch and per-model ceilings default to that figure, so they bind only on a harness bug.
- **Efficiency reporting.** Report tokens per trial, the share of trials that ran out of budget, and tokens per resolved trial. Efficiency never enters the score (user decision, 2026-10-16): it shows a problem, such as glm finishing early and spending most tokens on re-checking, but is not itself a key capability.
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
- **Follow mainstream benchmarks.** Model the task forms on established benchmarks: SWE-bench-style repository repair against hidden tests, Terminal-Bench-style command-line tasks, τ-bench-style tool use under policies, and reasoning sets with generated instances. Where raising difficulty or adding edge cases does not make a task discriminate, replace it or add new tasks instead of forcing it (user decision, 2026-10-16).
- **Other scoring criteria.** Besides completion, tasks may score further qualities that separate solutions, such as code quality or documentation, through checks or judged dimensions.
- **Design first.** This package starts with a design document that surveys task designs from established benchmarks and proposes concrete families; the user reviews it before any build. The proposal is [Task Set v2](../design/TASK_SET_V2.md), which also covers WP6.

### WP6. Visual quality through a vision-model judge

vis-001 (an original landing page) currently has static structure and contrast checks and a human pairwise review form. Rendering is still blocked, and it has no manifest. The user proposed handing aesthetic judgement to a third-party model with vision.

- **Rendering.** Headless Chromium, through Playwright (browser binaries already exist in `~/.cache/ms-playwright`), renders each submission in the sandbox. It covers fixed viewports (desktop 1440×900, phone 390×844 at DPR 2), every form state, and the long-content variant. Rendered checks (horizontal overflow, computed contrast, axe-core) become objective checks. Visual appeal never offsets them.
- **Judge skill.** A versioned judging package in the task's `private/` directory:
  - a `SKILL.md`-style instruction with the rubric (fit to brief, visual hierarchy and clarity, consistency, responsive quality, polish);
  - the procedure;
  - a JSON output schema with evidence for each judgement.

  The judge receives the screenshots and the brief, never the model's name.
- **Comparison against anchors.** Each submission is compared pairwise with fixed anchor designs of known quality, the private reference and known-weak variants, in both orders to cancel position bias. Its score is the fraction of comparisons won. This keeps grading per trial; ranking all submissions against each other can come later.
- **Independence and calibration.** The judge comes from a vendor other than the evaluated models; its model, version and prompt digest are recorded in the run condition. Before its scores count, the judge must:
  - rank the anchors in their known order;
  - be stable under order swaps;
  - agree with a small set of human pairwise labels.
- **Open points:** which vision model serves as judge, and whether the user approves adding Playwright as a dependency.


## Order

1. WP2 and WP3: done 2026-10-16.
2. Re-pilot on the current tasks with the WP4 conditions: done 2026-10-16, see [the budget pilot results](../reviews/2026-10-16-budget-pilot.md). The mechanics work, every task scored at least 93% for both models, and no failure came from a grader.
3. WP5 and WP6: the design proposal [Task Set v2](../design/TASK_SET_V2.md) awaits user review; then build, pilot, and freeze the first comparison set.

## Decisions (user, 2026-10-16)

1. **Format penalty:** 0.2. A format slip shows lapsed attention, not a large failure.
2. **Partial credit:** yes. Completion degrees count, and other criteria may be added to separate solutions.
3. **Budget status:** state the budget at the start; remind every few turns rather than every turn. Implemented as reminders after 50%, 75% and 90% of any limit.
4. **Budget values:** left to Claude, based on each task and the pilot results (WP3 table).
5. **Efficiency:** reported as a parameter, never part of the score.
6. **Graders:** improve them through testing; no heavy up-front safeguards (WP1 scaled down).
7. **Task difficulty:** follow mainstream benchmark forms; replace or add tasks where hardening does not work (WP5).
8. **Aesthetics:** a vision-model judge, written as a judging skill (WP6).
