# Task Set v2 Calibration, 2026-10-18 to 2026-10-19

The first calibration of the five Task Set v2 families built so far: R1 rostering, R3 logic grids, T1 evidence recovery, E2 specification implementation and vis-001 with model judging ([PLAN-005](../plans/PLAN-005-discriminating-attributable-evaluation.md) WP5 and WP6). These results calibrate tasks, graders and budgets. They are not model capability results.

## Conditions

- Models: `supergpt:gpt-6-luna` (medium), `supercn:glm-5.3` (high), `deepseek:deepseek-flash` (high) and `supercn:step-5-preview` (medium), all at temperature 0, with budgets stated to the model and reminders at 50%, 75% and 90%. kimi-k3 was not run.
- Generated families run one trial per item: R1 with 8 items per level at L1–L4, R3 with 8 per level at L1–L5, and T1 with 4 per level at L1–L4. E2 and vis-001 run single items with repetitions.
- Tokens count every input and output token of every request, including context resent from earlier turns.

| Family | Runs | Budget per trial |
| --- | --- | --- |
| R1 | `e4dda9c5` | 4 responses, 100,000 tokens |
| R3 | `78ab1d6b` (L1–L3), `f1c85624` (L3–L5, stopped at 76 of 96) | 4 responses of at most 65,536 output tokens, 100,000 tokens |
| T1 | `e239c8f3` (L1–L3), `d886d0fb` (L4) | See the experiment plan; no trial reached it |
| E2 | `82f84f8a` (task 0.1.0, 300,000 tokens), `044fa08d` (task 0.2.0, 800,000 tokens, stopped at 4 of 12) | Now 800,000 tokens |
| vis-001 | `ec261ceb` (task 0.3.0, 300,000 tokens) | Now 800,000 tokens |

## Results by family

Mean score per model over all valid trials; the percentage in brackets is the share of trials fully resolved. Infrastructure failures are left out.

| Family | deepseek-flash | glm-5.3 | step-5-preview | gpt-6-luna |
| --- | ---: | ---: | ---: | ---: |
| R1 (32 items) | 100% (100%) | 89% (97%) | 97% (91%) | 86% (69%) |
| R3 (35 items) | 97% (97%) | 75% (81%) | 82% (85%) | 39% (26%) |
| T1 (16 items) | 100% (100%) | 90% (94%) | 88% (69%) | 95% (63%) |
| E2, task 0.2.0 (1 trial each so far) | not run | 100% | 88% | 82% |
| vis-001 tournament win rate | 67% | 42% | 36% | 46% |

glm's mean is below its resolved share because a format slip costs 20%: glm put prose before its JSON answer in 15 of 32 R1 trials, 20 of 32 R3 trials and 8 of 16 T1 trials.

### Which levels separate the models

- **R3 discriminates from L3 upward.** At L3 every item separates the models and none is solved by all. At L4 six of eight items separate them and two are solved by none. deepseek solves every valid L4 item, while glm and step fall to 50–56%, mostly through budget stops, and luna to 17%. L1 and L2 are close to saturated for three models; they stay as easy anchors.
- **R1 is saturated for deepseek and step.** Only luna falls below 80%, at L3, where it misses rules and proposes conflict sets that are not minimal. R1 needs harder levels or retirement from the comparison set.
- **T1 separates at L4 only.** At L4 no item is solved by all models, while L1–L3 are near saturation. deepseek answers every question at every level, so the family needs a fifth level to separate the strongest model.
- **E2 is in range.** No model has failed it completely, and only glm has resolved it, in one of one trial. The item is hard enough, but one item is too few for a reliable score: E2 needs more specification items.
- **vis-001's objective checks are saturated.** Under the fixed 0.3.1 verifier every delivered page passes all six checks. Separation comes only from the visual tournament (below).

### Token use

Median tokens per trial: R1 1,300–5,200; R3 2,700–8,700 overall, and 40,000–67,000 at L4–L5 for the thinking-heavy models; T1 19,000–82,000. E2 and vis-001 use 300,000–800,000 when the budget allows, except luna, which finishes in 38,000–45,000. luna is consistently the cheapest and, on reasoning, the weakest.

## Budget findings

- **E2 and vis-001 at 300,000 tokens were too tight.** Both valid deepseek and glm E2 trials stopped at the limit after about 11 responses, and five of seven valid vis-001 trials stopped while refining finished pages. Most of the spend is context resent with each request: deepseek's eleven E2 requests produced about 34,000 output tokens. Both budgets are now 800,000 tokens. In the first E2 trials under 800,000, glm finished just under the limit and step reached it.
- **R3 keeps its budget.** At L4–L5 most budget stops are single responses that reach the 65,536-token output cap. That cap equals step-5-preview's own output limit, and the remaining stops are mostly glm's long reasoning, which by decision does not raise budgets. deepseek stopped once in eight valid L4–L5 trials.
- **step-5-preview** twice exceeded the 32,768-character final-reply limit on R3 by reasoning in visible text. The limit is stated to the model, so the stop is its own.

## Attribution audit

Every failed check in R1, T1, E2 and vis-001, and the R3 failures at L4–L5, was traced to its cause. Defects that charged a model for something it did not do were fixed with a version bump, and the affected trials were regraded or set aside.

| Defect | Effect | Fix |
| --- | --- | --- |
| T1 grader 1.0.0 accepted absence of a config key only from a full read of prod.toml | Correct answers resting on a complete key search failed (two luna trials) | Grader 1.1.0/1.2.0: a search proves absence when it covered the file, including a truncated search that had passed it; 64 trials regraded |
| T1 grader counted the exclusion glob `!secrets/**` as touching `secrets/` | One glm refusal failed | Grader 1.1.0: a glob touches `secrets/` only if it could match a file there |
| E2 expected `=0^-1` to be `#NUM!`, which the specification did not settle | deepseek, glm and luna all returned `#DIV/0!`, as Excel does | Grader 1.1.0 dropped the cell; task 0.2.0 states the rule and tests it again |
| vis-001 grader 1.0.0 (`copy`, `form`) | Every model lost 17–33% | Fixed in task 0.3.1, before this review; the run itself was graded under 1.0.0 |
| Renderer could not tick custom-styled checkboxes | Two pages showed no success state to the judges | Script-click fallback |
| An operator cleanup command removed live trial workspaces | Five E2 and seven R3 trials ended unscored | Set aside as infrastructure. The harness now records such export failures as infrastructure, so a resume retries them |

After these fixes, every remaining deduction is the model's own:

- wrong values and precedence errors;
- miscounts;
- conflict sets that are not minimal;
- rule violations in proposed rosters;
- listing or searching `secrets/`;
- unrounded or float output where the specification asks for integers;
- crashes;
- missing deliverables at a budget stop;
- format slips.

One case is borderline. step twice cited `prior_attempt.log` as the evidence for a recovered value that sits in a config file. Every other evidence field in T1 names the file that holds the answer, so it is counted against the model; the wording can still be made explicit at the next T1 version.

## Visual judging

- **Anchors no longer separate models.** Every rendered page beat both the reference and the plain anchor, with 3% position-inconsistent comparisons and 94% agreement between judges. The anchors still serve as a quality gate and as a check on the judges themselves.
- **A pairwise tournament does separate them.** `scripts/judge-tournament.ts` pairs each page with every page from other models, in both orders, using judges from neither page's vendor. Its results:
  - win rates of 36–67%;
  - Bradley–Terry strengths: deepseek 1.69, luna 0.98, glm 0.87, step 0.69;
  - deepseek's page won every judged game. Its second trial, which wrote no page, lost all of its pairings.
- **The tournament's limits.** deepseek could not judge, because its key was rejected, so most pairs had one judge. 17% of judged games were position-inconsistent, and the sample is seven pages. A full rerun at 800,000 tokens with deepseek restored, and later qwen or kimi as further judges, is needed before visual scores are frozen.

## Blockers

- **The deepseek API key is rejected.** Since about 10:19 on 2026-10-19 every request returns an authentication error (HTTP 401/403), not an insufficient-balance error. Both batches stopped: R3 at 76 of 96 trials and E2 0.2.0 at 4 of 12. The user needs to check the key or the account. Afterwards, both runs resume from worktrees at their commits (`e30b311` and `a400d42`), because a run is pinned to its commit.
- **The eng-004 baseline is a Git submodule that is not checked out.** The sandbox masks `.gitmodules`, so one harness test fails here. HANDOFF already lists rebuilding the baseline.

## Next steps

1. Resume R3 and E2 once deepseek works, and rerun vis-001 at 800,000 tokens, with both judging steps.
2. Harden or retire the saturated parts:
   - retire R1 from the comparison set and keep L1–L4 as easy anchors. A probe of larger levels (8–9 people, two per shift, all seven rules) produced no instance in ten minutes, because the exact solver must decide all 128 rule subsets. R3 already covers constraint reasoning and discriminates;
   - add T1 L5 with deeper chains and larger snapshots;
   - add at least two more E2 specification items.
3. Build E1 repository repair and E4 terminal tasks, the next families in the Task Set v2 order.
4. Run kimi-k3 sparingly on the discriminating levels only: R3 L3–L5, T1 L4 and E2.

## Addendum: hardening and new families (later on 2026-10-19)

All runs below exclude deepseek, whose key was still rejected. They use luna, glm and step under the same conditions as above, and deepseek runs later under the same task versions and budgets.

| Family | Version | Result | Verdict |
| --- | --- | --- | --- |
| T1 L4–L5 | 0.2.0, grader 1.3.1 | L5: glm 78%, step 78%, luna 85%; no item solved by all | L5 discriminates; still to be checked on deepseek |
| E2 | 0.3.0 (sheet, ledger, recur) | sheet 50–97%; ledger 77–100%; recur 100% for all | sheet discriminates; ledger separates only luna; recur is an easy anchor |
| E4 | 0.1.0 (perf, migrate, bisect, build) | 100% for every model and item | Saturated; kept as easy anchors and a sandbox check |
| R1 | 0.1.0 | See above | Retired from the comparison set; larger levels were not practical |

### What the new items show

Short, self-contained engineering tasks no longer separate these models, even when the specification is dense (E2 `recur`) or the task needs several tools (E4). The levels that do separate them share one of three properties:

- precision over many interacting rules: E2 `sheet`, R3 L3–L5;
- evidence spread over a large snapshot: T1 L5;
- several steps that must all be right: T1 incidents and counts.

Hardening should therefore lengthen and compound the work. A single bug or a single specification is not enough.

### Next

1. **E3 long-horizon maintenance (eng-005).** Five stages in one session, which is the natural compound task. The harness still refuses a stated budget for trajectory runs (`TRAJECTORY_BUDGET_NOTICE_UNSUPPORTED`), and principle 3 requires one, so stated budgets and reminders for trajectories come first. eng-005 has never had a real model run.
2. **E4 0.2.0.** Compound tasks: several faults that interact across a larger project, and data recovery from Git internals rather than bisection.
3. **T2 policy-bound operations**, after τ-bench.
4. **deepseek and kimi.** Once the deepseek key works, run deepseek on the plans whose names end in `-without-deepseek`, resume R3 (`f1c85624`, at commit `e30b311`), and rerun vis-001 at 800,000 tokens. Then run kimi-k3 sparingly on R3 L3–L5, T1 L4–L5 and E2 `sheet`.

## Addendum: deepseek completed and overall scores (2026-10-19, evening)

With a new deepseek key, the missing runs were completed:

- deepseek on E2 0.3.0, T1 L4–L5 and E4;
- the rest of R3, 96 of 96;
- a vis-001 rerun at 800,000 tokens for all four models, with the tournament.

A third vis-001 grader defect was fixed (grader 1.0.2): the `states` check searched app.js for words instead of checking behaviour.

Mean score per model and family. In brackets: trials and median tokens per trial. Infrastructure failures are excluded.

| Family | deepseek-flash | glm-5.3 | step-5-preview | gpt-6-luna |
| --- | ---: | ---: | ---: | ---: |
| R3 logic grids, L3–L5 | 86% (22, 27k) | 57% (21, 26k) | 60% (22, 19k) | 17% (24, 3k) |
| T1 0.2.0, L4–L5 | 100% (8, 206k) | 83% (8, 97k) | 88% (8, 199k) | 90% (8, 70k) |
| E2 0.3.0, three specifications | 100% (6, 752k) | 99% (6, 549k) | 83% (6, 588k) | 86% (6, 28k) |
| E2 `sheet` only | 100% (2) | 97% (2) | 50% (2) | 82% (2) |
| vis-001 tournament win rate | 83% | 25% | 33% | 58% |
| R1, L1–L4 (easy anchor) | 100% | 89% | 97% | 86% |
| T1 0.1.0, L1–L4 | 100% | 90% | 88% | 95% |
| E4 0.1.0 (saturated) | 100% | 100% | 100% | 100% |

- **deepseek-flash leads everywhere.** It never scored below 86% on a family, and it won 10 of 10 tournament games against one page in the earlier vis run.
- **glm-5.3 and step-5-preview form the middle.** Each wins on different families. glm loses many points to format slips (20% each) and to budget stops on long reasoning. step loses points to responses that exceed the output limit.
- **gpt-6-luna is uneven.** It is very cheap, at a tenth to a thirtieth of the others' tokens. It is strong on evidence retrieval and visual design, and weak on multi-step logical reasoning (R3 L3–L5: 17%).
- **Visual judging is noisy.** In the rerun 35% of judged games were position-inconsistent, and judges agreed on 46% of pairs. The visual ranking needs more pages before it is trusted beyond deepseek's lead.
- **R3 L5's output limit binds most models.** 13 of 24 deepseek, glm and step trials stopped at the 65,536-token limit of a single response. The next R3 version should allow a longer response.
