# Hardening Round 2, 2026-10-21/22

**Goal (user, 2026-10-21).** Build a one-command suite runner (PLAN-006 Part A). Then harden E4, T1, T2 and E3 (Part B) until deepseek-flash scores about 80% or below on most families; a few slightly above is acceptable. Dev rounds used deepseek-flash with qwen3.8-flash and mimo-v2.6-flash as references, one repetition, and only the families being changed. No relay model was used.

## Part A: the suite runner

`npm run suite -- --suite suites/dev.json --models <list> --families <ids>` runs from one background command:

1. It freezes HEAD into a worktree.
2. It generates one plan per family from its template.
3. Preflight:
   - it checks the packages and the plans' pins;
   - it validates every plan;
   - it prints a worst-case token estimate.
4. It runs each family once with the null agent.
5. It launches every family at once, with concurrent trials capped per provider endpoint across processes.
6. It resumes each run once for its infrastructure failures.
7. It writes `report.md` and `report.json`.

`--dry-run` stops before the launch, and `--resume` continues a suite or rebuilds its report after regrades. A model without `?thinking=` runs at its declared middle level. `suites/dev.json` refuses pro models, a second relay model and more than one repetition.

**Acceptance.**

- **Dry run.** A dry run of all seven families validated every template, and the null agent earned nothing on six of them. On E3 an untouched project scored 19.5%, a defect fixed in B4.
- **End-to-end run.** The first end-to-end run (E4 speedup 0.4.1 and T2 0.2.0 with deepseek and qwen, `runs/suites/20261021-120039-dev-fe3b`) took 19 minutes. Its family scores and median tokens match `scripts/item-analysis.ts` on the same runs.
- **Tests.** Offline tests (`tests/suite.test.ts`, 9) cover plan generation, model and repetition substitution, scores against the trials, flags, the retry pass, dry runs, and resuming an interrupted suite in its run directories. They also cover provider slots and stopped providers.

**Defects the runner found in itself.**

- `task_packages.py check` failed on historical plans' stale pins, so the preflight checks only the suite's plans (`check --plans`).
- The per-model token ceiling equalled trials × budget. A trial may pass its budget by its last request, so deepseek's speedup trial (2.04M of 2M) left its compress trial unrun. The ceiling now allows 1.25 budgets per trial.

## Results

All figures are dev runs of one trial per item. Scores are partial credit after the regrades below.

| Family | Version | deepseek | qwen | mimo-flash | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| R3 logic grids | 0.3.0 | 72% | 24% | 28% | 2026-10-20, unchanged |
| E2 routes | 0.5.0 | 71% | 17% | 58% | 2026-10-20, unchanged |
| T1 depth ladder | 0.5.0, D2–D8 | 95.0% | 82.5% | 70.0% | content 38/40, 40/40, 35/40 |
| T2 optimisation | 0.3.0, S/M/L | 95.2% | 100% | 78.6% | |
| E4 speedup | 0.5.0 | 7/8 | 8/8 | 7/8 | |
| E4 compress | 0.5.0 | 5/6 | 4/6 | 0/6 at 2M | at 4,000,000 tokens; mimo not yet at 4M |
| **E4** (mean of the two) | 0.5.0 | **85.4%** | **83.3%** | — | |
| E3 long horizon | eng-005 0.4.0 | 97.9% | 97.9% | not run | 47/48 each |

## B1. E4: compress, and a speedup gate

**compress** asks for a lossless compressor for simulated CDN edge logs. The size on two hidden days is placed between LZMA preset 9e (0%) and a compressor written for the format (100%), with rungs at 50/80/90/97% behind round-trip gates. Splitting fields into columns is worth only about 12% on this scale; the rungs are structure in the data (per-address profiles, per-edge request ids, size memos). Self-calibration: 9 scenarios, including a program that stashes the original for its own decompression, which earns nothing.

At 2,000,000 tokens per trial **no model left a working compressor**, which was a budget problem, not the models':

- deepseek's range coder was mid-edit at the budget;
- qwen's turn ended with `packlog.py` half-written;
- mimo's program was no smaller than gzip.

The check was rerun by hand on each program and agreed. Each trial made 30–38 requests of about 60,000 tokens. The budget is meant to let most models finish, so it was too small for this item, and compress now has 4,000,000 tokens.

**At 4,000,000 tokens the item works.** deepseek's compressor reaches 92.7% of the way to the reference (5/6) and qwen's 81.8% (4/6). Both round-trip every hidden input within the time limit. This is the second continuous engineering item, after E2 `routes`, that places deepseek in the 80s and below.

**speedup.** The formal 0.4.1 run put deepseek at 0%. Its program was correct but 3.1 times as slow as the reference, and the outputs only counted once `speed-3` passed. A small speed difference decided the whole score, so 0.5.0 adds a `speed-8` rung as the gate; the original, 70 times as slow, still earns nothing. In the 0.5.0 run deepseek and mimo passed 7 of 8 rungs and qwen all 8.

## B2. T1: the depth ladder

Levels D2–D8 ask questions that follow 2–8 references:

- incident → review → change → service, then its production upstream once to three times, then a key's effective value;
- `upstream` itself follows the precedence rules;
- every step has a plausible distractor.

Self-calibration passed 1734/1734:

- an independent solver reproduces every key;
- each distractor changes the answer in 70% of applicable cases;
- a trace that leaves out any file of a chain fails.

**Result: depth did not separate the models on content.** deepseek answered 38/40 chain questions, qwen 40/40 and mimo 35/40; mimo's five misses are a trial that ended without an answer. Per-step accuracy is close to 1 for these models, so errors do not compound at depth 8. The spread in scores comes from format deductions: prose or fences around the answer, which the prompt rules out.

## B3. T2 0.3.0: optimisation within the policy

Policy section 11 lets each damaged or missing unit be made good four ways and requires the resolution of least cost to the shop:

- products sent at cost;
- one carrier rate per delivery address;
- refunds in full;
- credit at 70%.

Shared stock, shared addresses and customer constraints couple the decisions. A min-cost flow over every set of shipping addresses gives the optimum, and enumeration agrees on the eight smaller tickets.

**Result: deepseek 95.2%, qwen 100%, mimo 78.6%.** qwen and deepseek reached the optimum on 12 and 11 of 12 tickets. They worked most tickets out by reasoning, with tickets of at most 15 units; deepseek ran its own Python on 3 tickets and qwen on 5. deepseek's one miss (`om2`, 7.3% above the optimum) gave credit where sending a unit from stock was cheaper. Every other deduction was a budget stop or mimo's own failure:

- planning without acting;
- a repetition loop;
- stopping at the budget.

## B4. E3: eng-005 0.4.0 with a scale stage

S6 grows the store to 100,000 work orders with a chain 50,000 deep, a ladder of diamonds with billions of paths, and an order with 2,001 prerequisites. A hidden workload of 15 commands is compared with a reference:

- correctness (`SCALE`, critical);
- speed rungs at 3/1.5/1.1/0.75 times the reference's time (`SCALE_SPEED`, a ladder, not critical).

The S1–S5 reference code, the kind these stages invite, fails at this size: its recursive search overflows the stack on the chain, and it takes 1.65 times as long. Both references were rewritten to scale and pass, three times each. Three mutants land where expected:

- a recursive linear search and a search without a visited set fail `scale.dependencies`;
- linear lookups with a full copy before each write are correct and reach `speed-1.5`.

Grader 2.1.0 also fixes an attribution defect found by the suite's dry run. A null agent scored 8 of 41 checks under 0.3.0: the base and seed checks pass on an untouched project, and two rejection checks passed because an unimplemented command is rejected too. In the round's smoke the null agent now scores 0.

**Result: 47/48 for both deepseek and qwen.** Both passed every check of S1–S5 without a repair. In S6 each was stopped by the stage's token budget, after making the tool scale: all three correctness checks and every speed rung but `speed-0.75` pass. They took 12 and 28 minutes and 6.6M and 6.8M tokens. Speed rungs are 4 of 48 checks, so a correct but slow S6 would still score 92%. **E3 remains saturated.**

## What this round shows

The 2026-10-20 review found that more detail does not harden a family. This round shows that more depth or scale does not either, while the brief stays well specified:

- **T1:** reference chains eight deep with a distractor at every step.
- **T2:** an exactly specified optimisation with a computable optimum, small enough to work out by hand. The models do, with a script for some tickets.
- **E3:** a scale requirement with a stated reference. The models write the scalable code.

deepseek and qwen carry these out at 95–100%. What spreads them is still:

- reasoning depth without tools to offload it (R3);
- open-ended optimisation and engineering scored on a continuous scale against a strong reference (E2 `routes` 71%, E4 `compress` 83% for deepseek, qwen 17% and 67%).

The weaker reference, mimo-v2.6-flash, does separate on T1 (70%) and T2 (79%), mostly through incomplete or unanswered trials.

## Defects found and fixed

| Defect | Effect | Fix |
| --- | --- | --- |
| E3 grader credited an untouched project | null agent 19.5% | grader 2.1.0: guards and working-command conditions |
| speedup 0.4.1 gated outputs on `speed-3` | a correct 3.1× program scored 0 | 0.5.0 adds a `speed-8` gate |
| T2 closing-fence pattern began at the first fence | replies showing commands in a block lost 20% | grader 1.1.1 |
| T2 deducted format from a missing reply | budget-stopped trials lost 20% of their actions' credit | grader 1.1.1 |
| T1 refused a reply with several objects | a clear final answer scored 0 | grader 1.6.1 recovers the object the reply ends with |
| Suite ceiling had no room for overshoot | a planned trial did not run | ceiling 1.25 budgets per trial |
| compress budget 2,000,000 | no model could finish | 4,000,000 |

Every remaining deduction in the T1, T2 and E4 runs was audited and is the model's own.

## Tokens

| Round | deepseek | qwen | mimo-flash |
| --- | ---: | ---: | ---: |
| Part A (E4 speedup 0.4.1, T2 0.2.0) | 2.84M | 3.02M | — |
| B1+B2 (E4 0.5.0, T1 depth) | 2.97M | 3.94M | 5.14M |
| B3 (T2 0.3.0) | 2.73M | 3.04M | 4.46M |
| deepseek compress (2M) | 2.07M | — | — |
| E3 and compress (4M) | 10.74M | 10.99M | — |
| **Total** | **21.4M** | **21.0M** | **9.6M** |

## Decisions for the user

1. **T1, T2 and E3 stay at 95–98% for deepseek** after the approved designs. Three ways forward:
   - **Keep them as reliability families.** They check that a model carries out well-specified work without slips, and they separate weaker models (mimo 70% and 79%; luna 33% on T2 0.2.0). They would then not count toward the 80% target. The target holds on R3 (72%) and E2 (71%), with E4 slightly above (85%).
   - **Rebuild them around a continuous open-ended objective**, as E2 `routes` and E4 `compress` are:
     - for E3, score S6 continuously against a much faster reference and weight it as a stage, not as 7 of 48 checks;
     - for T2, use instances too large to enumerate, with tiered carrier rates, so that the optimum needs a real search.

     Each costs a design round and about 10–20M tokens to calibrate.
   - **Retire the saturated families** from the scored suite, keeping them as anchors.
2. **E4 at 85% for deepseek** is slightly above the target. Accept it as one of the "few slightly above", or move compress's upper anchor further out: the reference reaches 2.6 times LZMA's ratio, and deepseek got 92.7% of the way.
3. **mimo-v2.6-flash** has not run compress at 4,000,000 tokens (about 4M of MiMo quota), nor E3 0.4.0 (about 8M).
4. **The relay models** (glm-5.3, step-5-preview, gpt-6-luna) have run none of the new items. They need relay balance first.

