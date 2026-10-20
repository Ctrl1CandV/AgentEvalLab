# Hardening Round, 2026-10-20

**Goal (user, 2026-10-20).** Bring every family's scores into the range 30–80%. Before this round, E2, E3, E4 and T1 were well above it for the strong models. The user added a MiMo token plan, and mimo-v2.6-pro and mimo-v2.6-flash joined the pool at their default thinking (`docs/reviews/2026-10-14-provider-check.md`). Visual judging only had to become good enough, and it did (see Visual judging below).

## What did not work: more detail

Every family was first hardened by making its well-specified work longer or more detailed. For the strong models, none of it moved the scores.

| Family | Version | What was added | Strong models |
| --- | --- | --- | --- |
| T2 | 0.2.0 | Policy rules that interact: verified addresses, coupon prices, credit-first refunds, tier windows and fees, price drops, sequential and unidentifiable requests | qwen 100%, deepseek 97.5%, mimo-pro 97.5% |
| E3 | eng-005 0.3.0 | Twenty hidden checks, each drawn from a stage brief | qwen 100%, deepseek 97.6%, luna 97.6% |
| E4 | 0.2.0 | Compound items: six faults reported as symptoms, a four-fault pipeline, lost Git work | every model, every check |
| E4 | 0.3.0 | codec: reverse-engineer a log format from its encoder's bytecode | deepseek, qwen, mimo-flash 11/11 |
| T1 | 0.4.x | L7: distinct counts, a median over about 90 requests, joins across every log, three-deep includes | deepseek 100%, qwen every answer right (format deduction only) |

These models carry out a well-specified brief, policy or specification almost perfectly, edge cases included. More detail raises cost, not difficulty. The errors that remain are slips, such as a silver customer given gold's extended return window, and they appear in one repetition and not the other.

## What does separate them: ladders

**R3** is the one family that spread the models from the start. A logic grid gets harder with its size, and each model stops at a different rung:

| Level | deepseek | mimo-pro | mimo-flash | qwen |
| --- | ---: | ---: | ---: | ---: |
| L5 (8×8) | 75% | 63% | 60% | 25% |
| L6 (9×9) | 89% | 63% | 25% | 32% |
| L7 (10×10, new in 0.3.0) | 53% | 0% | 0% | 14% |
| **L5–L7** | **72%** | **42%** | **28%** | **24%** |

At L7 the MiMo models stop at their own output limit in every trial: one response of 131,072 tokens is not enough thinking for a 10×10 grid.

The two new engineering items follow the same idea and score continuously:

- **E2 `routes`** (0.5.0), an optimisation item in the form of ALE-Bench. Delivery routing with capacities, duration limits and refrigerated vans. Each plan scores the share of the way from a nearest-neighbour baseline to the best cost found offline, with checks at 50/80/90/97% on eight instances. In self-calibration, Clarke-Wright savings earns 12/32 and an 8-second LNS 23/32.
- **E4 `speedup`** (0.4.0). Make a quirky, slow report program fast with byte-identical output. Speed checks at 16×, 6×, 3× and 1.5× of an optimised reference sit behind exact-output gates. The original is 71× slower than the reference; a version that keeps `strptime` for every row is 2.6×.

Results (models with balance: deepseek, qwen, mimo-pro, mimo-flash; the relay models could not run):

| Item | deepseek | mimo-pro | mimo-flash | qwen |
| --- | ---: | ---: | ---: | ---: |
| E2 routes (0.5.0), checks passed | 70%, 73% | 49%, 64% | 58%, 58% | 6%, 27% |
| E4 speedup (0.4.0 ladder) | 100%, 100% | 100%, 100% | 100%, 0% | 100%, 0% |
| E4 speedup (0.4.1 ladder, measured offline) | 100%, 100% | 86%, 86% | 86%, 0% | 71%, 0% |

- **routes.** It spreads the strong models inside the target range. deepseek wrote ruin-and-recreate searches with regret insertion. One qwen trial's solver overloaded a van on seven of eight instances (infeasible, so nothing). Every trial used its whole 3M-token budget, as optimisation work does: the budget plays the part of ALE-Bench's contest time.
- **speedup.** deepseek's programs beat the reference (0.64× its time), with a hand-written timestamp scanner and the csv module only for quoted fields. That is near the practical floor in Python, so the 0.4.1 ladder (3/1.5/1.1/0.75×) places the field below deepseek rather than above it. The zeros are wrong outputs. A 0.4.0 trial cannot be regraded under 0.4.1, so the 0.4.1 row is an offline measurement of the delivered programs, and a 0.4.1 run is still needed.

## Harness changes

- **Provider failures stop only their provider.** An expired key at one relay used to stop the whole batch, for every model.
- **A trajectory stage stopped by its budget is graded** on what it delivered, as single runs are.
- **A response lost to a transient provider error mid-stream** is dropped and the session continues, at most twice. Errored requests keep the provider's redacted error text.
- **The relays' quota errors** (403 with `insufficient_user_quota`) are classified as balance failures.
- **Only the task budget stops a model.** New plans allow 131,072 output tokens and 524,288 characters of text per response. The old 32,768 limits stopped mimo-v2.6-pro in every codec trial, because it writes its reasoning out as text as well.

## Defects found and fixed

| Defect | Effect | Fix |
| --- | --- | --- |
| T2 grader 1.0.0 counted only a bare JSON object as a well-formed reply, while POLICY.md asks the reply to *end with* one | Every model that explains first lost 20% on every ticket | Grader 1.0.1 accepts a closing object, bare or fenced; 59 trials regraded |
| Sandbox placeholder files were committed with E2's query item | 24 empty files in the repository | Untracked |
| R3 and T2 manifests pinned calibration.md, edited after building | Preflight refused the R3 run | Rebuilt and re-pinned |
| `.gitignore` excluded the codec item's bytecode | Preflight refused the codec run | A narrow exception |
| T1 L7 0.4.0 had twelve 1,300-line logs | Models used the whole 1.5M budget without answering | 0.4.1 keeps L6's data size |
| codec mutants for the day reset and the 64-entry table | They turned out to be equivalent decoders | Replaced with real mutants |

## Accounts

The airy.work relay, which serves glm-5.3, step-5-preview and gpt-6-luna, has been out of balance since the afternoon (¥0.01–0.02 left). Its models fail at the first request, and the runs record them as not run or as infrastructure failures, to be resumed after a top-up. deepseek ran out too and was topped up during the round.

## Visual judging

The judge exam (pairs whose better page is known, in both orders) passed four judges at 100% with no position flips: luna, deepseek, glm-5.3-flash and qwen. step answered nothing and was excluded. The tournament separates deepseek and qwen (83% and 74% win rates) from step and glm (26% and 18%), with luna between them, and the 95% intervals are disjoint between those groups. This is good enough for the user's purpose, and no further work was done on it.

## Where the families stand

These figures cover the models with balance: deepseek, qwen, mimo-pro and mimo-flash. glm, step and luna are still to run.

| Family | Version | deepseek | qwen | mimo-pro | mimo-flash | In 30–80%? |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| R3 logic grids | 0.3.0, L5–L7 | 72% | 24% | 42% | 28% | yes, two models just below |
| T1 evidence recovery | 0.4.1, L7 | 96% | 85% | 36% | 34% | the top two above |
| E2 specifications | 0.5.0, routes | 71% | 17% | 56% | 58% | yes, qwen below (its own bugs) |
| E4 command line | speedup, 0.4.1 ladder (offline) | 100% | 36% | 86% | 43% | deepseek above |
| E3 long horizon | eng-005 0.3.0 | 98% | 100% | 41% | 85% | no |
| T2 service desk | 0.2.0 | 97.5% | 100% | 97.5% | 91% | no |

## Decisions for the user

1. **E3 and T2 are saturated** for the strong models. Detail cannot harden them, and a ladder would change what they measure:
   - **E3 (long horizon).** A sixth stage on scale could carry speed tiers against a reference, as speedup does: 100,000 work orders, with list and dependency checks timed. A full run costs about 6–8M tokens per model, because every request resends the whole session.
   - **T2 (policy-bound tool use).** Policy application is where these models are most reliable. A ladder needs either an optimisation inside the policy (the cheapest compliant rebooking, for example) or a simulated user who must be questioned, as in τ²-bench, which needs a model to play the user. The alternative is to keep T2 as a reliability family, which separates the weaker models (luna 33%, mimo-flash 91%) but not the strong ones.
2. **T1** separates the MiMo models but not deepseek and qwen. Its only lever left is volume, and at twelve 1,300-line logs that turned into budget exhaustion.
3. **Accounts.** The airy.work relay needs balance before glm, step and luna can run any of the new items; their trials are recorded as not run and can be resumed.
