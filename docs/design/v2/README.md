# AgentEvalLab v2: Restructure Design

Status: design, 2026-10-24. The user decided on 2026-10-24 to restructure the whole project; this design is mine to make, and the user approves it before implementation begins.

Inputs:

- the third-party review `docs/reviews/2026-10-24-third-party-evaluation-review.md` (astra);
- the hardening history: reviews of 2026-10-19 to 2026-10-23, and PLAN-004 to PLAN-006;
- the run evidence under `runs/`.

This directory is the design. The implementation plan is [PLAN-007](../../plans/PLAN-007-v2-restructure.md).

## 1. Why v1 overflowed

Over three hardening rounds, almost every family moved to 90–100% for the strong flash models, or was held below that only by budgets. The causes are structural, not local to a few tasks.

1. **We authored the difficulty, as rules.**
   - Most v1 tasks are complete specifications of a procedure: a manual, a policy, a brief, a staged feature list.
   - Agents that read rules, query state, write scripts and check their work carry out such procedures reliably.
   - More rules, branches, couplings and scale made the tasks longer, not harder.
   - Where we added optimisation, our own "best known" anchors fell to generic search: enumeration in T2 0.2.0, annealing in T2 0.3.0, a path heuristic in E3 S7.
2. **The scales could not show headroom.**
   - Scores were weighted fractions of checks. Routine checks formed a high floor: T2 scored 72.5% at the naive plan.
   - Open-ended objectives were cut into a few rungs that capped at our references (E2, E3, E4, AE).
   - A score near 100 could mean "mastered", or "our anchor is weak".
3. **The process could not tell improvement from overfitting.**
   - We tuned two to ten items at a time, on the same two or three models, and read the same feedback.
   - There was no validation or held-out split.
   - We audited failures but not successes; the T2 coverage hole in the review is one result.
   - Budgets, context policy and harness limits changed alongside difficulty, so no round isolated one cause.
4. **Coverage narrowed.**
   - The full suite holds a handful of independent items per family: E2 1, E4 1+1, E3 1 trajectory, T2 4.
   - Several "families" now measure the same thing, writing a search program.

So v2 changes four things at once, but in a fixed order (PLAN-007):

- what we measure, and where the difficulty comes from;
- how a score is formed;
- how we confirm that a difference is real;
- how the library stays ahead of new models.

## 2. Goals

- **G1 Replicable discrimination.** Differences between models that hold on held-out tasks, with intervals computed over independent tasks, not over checks or repetitions.
- **G2 Headroom by construction and over time.**
  - Difficulty anchored outside this project: real software and its own tests; human-calibrated puzzles; human contest standings; decisions scored against an unreachable hindsight optimum; comparative judgements.
  - Raw values reported uncapped.
  - Families that refresh with new material.
- **G3 Scores with a meaning.** Each task reports:
  - whether it was **resolved**;
  - a **diagnostic** partial score;
  - its **raw objective values**.

  A model gets a **capability profile**, not one blended number.
- **G4 Attribution, both ways.** Every deduction is the model's own (unchanged since PLAN-005). Every pass is genuine: success audits and coverage invariants, not only failure audits.
- **G5 Coverage of the project's dimensions.**
  - engineering;
  - reasoning and logic;
  - agentic tool use;
  - visual design;
  - efficiency ("speed"), reported, never scored.

Non-goals:

- forcing scores into 30–80;
- claims about general intelligence;
- agent or harness comparisons (still a much later version);
- rewriting the execution core.

## 3. Binding principles

1. **Every task has a capability card before any paid run** (`docs/templates/CAPABILITY_CARD.md`). The card states:
   - what the task measures;
   - where its difficulty lies;
   - the cheapest shortcut and how the task resists it;
   - its anchors and its licence.

   A task whose card cannot say where the difficulty lies is not built.
2. **Difficulty never comes from hidden requirements, ambiguity, traps in format, or harness limits.** A specification may be long and demanding, but every check traces to the public contract.
3. **The unit of evidence is the independent task.** Tests, checks, cells and stages are evidence inside a task, not samples.
4. **Raw values are primary for open-ended work.** Normalised scores are piecewise-linear through declared anchors and are not capped above the top anchor. Rungs are labels only.
5. **Splits are fixed before tuning.**
   - **dev**: inspect freely.
   - **validation**: used once per freeze.
   - **holdout**: used only after the release freeze.

   Splits are drawn by structure (repository, problem, generator template), not by seed.
6. **Protocols are part of the result.** The budget track, context policy, tools, thinking level, temperature, command limits and model snapshot are recorded with every number. Results under different protocols are never mixed.
7. **Versions are immutable.** A grader or anchor change makes a new version. Old numbers keep their version and are re-graded into new columns, never relabelled.
8. **Saturation demotes.** When most tasks of a family are resolved by every model in the pool, the family moves to the basic tier, and new material goes into the core.

## 4. Architecture

```
                 Capability profile (per model, per protocol, per release)
   engineering | reasoning | agentic tool use | visual design | efficiency (reported)
        ^             ^              ^                ^                ^
   ---------------------------------------------------------------------------
   Tier        Purpose                                  Scored as
   basic       reliability: exact procedure-following,  resolved rate; high scores expected
               format, long-horizon consistency
   core        main discrimination, externally          resolved rate / normalised objective
               anchored, refreshed                      with intervals over tasks
   frontier    headroom for future models, raw values   raw objective + anchors (uncapped)
   ---------------------------------------------------------------------------
   Families -> tasks (structure groups, splits, provenance) -> trials (protocol)
   Validation pipeline: card -> offline baselines -> grader verification -> dev pilot
                        -> freeze -> validation -> holdout -> release -> refresh
```

Families planned for v2.0 (details in [TASK_LIBRARY](TASK_LIBRARY.md)):

| Capability | Basic | Core | Frontier |
| --- | --- | --- | --- |
| Engineering | E3 eng-005, E4 speedup, eng-001 | **ER** live repository repair (dev from SWE-bench-Live and SWE-rebench; validation and holdout from our own mining of recent fixes); E2 routes and E4 compress as bridges | **AE** heuristic contests (ALE-Bench); LR library rebuild (later) |
| Reasoning and logic | rsn-001/002 (retired to history) | **AR** abstraction and reasoning (ARC-AGI-1/2, Apache-2.0), answer-only; **R3** logic grids | RC reasoning certificates (later) |
| Agentic tool use | T1 evidence, T2 operations | **AP** sequential decisions under uncertainty (new environments) | — |
| Visual design | — | **VIS v2**: several briefs, executed interactions, comparative judging | — |
| Efficiency | reported for every trial: tokens by kind, calls, wall time | | |

## 5. What stays, what changes, what goes

| Area | Decision |
| --- | --- |
| Execution core (Pi 0.87.1 harness, sandbox, workspaces, artifacts, grader protocol, append-only regrade, trajectory runner, provider slots, budget notices, suite runner) | **Stays.** It is tested, and the v1 problems were not there. It is extended with read-only runtime mounts, answer-only profiles, metrics and the v2 schemas ([CODE](CODE.md)). |
| Manifest, grader result, plan, suite and report schemas | **New versions** (v2), with v1 still readable for history |
| Scoring | **Rebuilt.** Task units, behaviour groups, resolved, raw metrics, anchors, intervals over clusters ([MEASUREMENT](MEASUREMENT.md)). |
| Run protocol | **Formalised.** Budget tracks, budget calibration, usage breakdown, coverage ([PROTOCOL](PROTOCOL.md)). |
| Validation | **New.** Success audits, coverage invariants, splits, release gates, versioning ([VALIDATION](VALIDATION.md)). |
| Task library | **Re-tiered.** T1, T2, E3, E4 speedup and eng-001 to basic; R3 to core; E2 routes and E4 compress as bridge tasks; new core families ER, AR, AP and VIS v2; AE to frontier. rsn-001/002, tool-001, R1, the T2 shift desk and the eng-002/003 candidates are retired (kept for history). |
| Docs | **Consolidated.** v2 design here; plans continue with PLAN-007; the old design docs are archived with a pointer. |
| Results | v1 runs stay as they are. An evidence table states their versions and protocols; they are never re-read as v2 scores. |

## 6. Documents

| Document | Contents |
| --- | --- |
| [MEASUREMENT](MEASUREMENT.md) | task outcome record, score model, anchors, aggregation, intervals, saturation indicators, report contents |
| [PROTOCOL](PROTOCOL.md) | model pool and labels, budget tracks and calibration, token accounting, context policies, repetitions, failures and coverage, run metadata, cost governance |
| [TASK_LIBRARY](TASK_LIBRARY.md) | tiers, capability matrix, disposition of every package, new family designs, authoring workflow, splits, provenance, refresh |
| [VALIDATION](VALIDATION.md) | grader verification gates, success and failure audits, split discipline, release gates, versioning, demotion |
| [CODE](CODE.md) | what code stays, schema v2 definitions, new modules, target layout, migration, tests |
| [CAPABILITY_CARD template](../../templates/CAPABILITY_CARD.md) | the card every task family fills in |
| [PLAN-007](../../plans/PLAN-007-v2-restructure.md) | phases, work packages, acceptance criteria, costs, user decision points |

## 7. Position on the third-party review

I agree with its evidence and its central recommendations:

- capability matrix and tiers;
- capability cards;
- splits;
- task-level scoring with resolved, diagnostic and raw outputs;
- success audits;
- protocol records;
- budget tracks;
- versioning;
- not using rules or scale as difficulty.

Its P0 items are Phase 0 of PLAN-007:

- the evidence table;
- the T2 coverage fix;
- the success audits;
- the document sync.

Where this design goes further:

1. **Scope.** The user widened the restructure to the whole project. That covers measurement, library, protocol, validation, schemas, repository layout and docs. Following the review's evidence, the execution core is still extended, not rewritten.
2. **Sources.** The review proposes three prototypes we would author (engineering recovery, tool planning, reasoning). On the user's direction (2026-10-23), v2 takes most core difficulty from external, licensed, dated sources with human or real-software anchors:
   - live repository issues;
   - ARC-AGI;
   - AtCoder Heuristic Contest problems.

   Authored environments are kept only where no external source exists: AP, and later a constructed recovery family. Externally anchored tasks resist our own tuning bias, and dated sources can refresh.
3. **Durability.** Refresh and demotion are part of the design, not a later idea. ER and AE can add dated material; saturation moves a family to the basic tier.

The review's warnings bind this design:

- change one thing at a time;
- no 300–500M-token round by default;
- historical paper scores do not prove present difficulty;
- private contest seeds are not unpublished data;
- no reweighting to push a model below 80.
