# Task Set v2: Design Proposal

Status: approved by the user on 2026-10-18 (PLAN-005 WP5 and WP6); building starts with R3 and R1.

## Problem

The four runnable tasks do not separate models:

- In the two pilot rounds and the budget pilot, gpt-6-luna resolved at least two of three trials on every task.
- Both models resolved rsn-001 and tool-001 in every trial of round 2.
- Each task is one fixed instance, so a trial is a single binary observation. Three repetitions of an easy item measure little more than noise.

## Targets

- **Spread.** Each task family should land between 20% and 80% mean score on the pilot models, and the pilot models should differ by more than the interval width on at least half the families.
- **Items, not repetitions.** Statistical power comes from many independent items per family, not from re-running one item. With per-item scores in [0, 1], separating two models by 10 points needs on the order of 30 to 50 paired items per capability; generated families make that cheap.
- **Partial credit and stated budgets**, as implemented in PLAN-005 WP2 and WP3.
- **Fresh content.** Generated, fictional instances, with seeds kept private for a holdout split, so memorised answers do not help.

## What mainstream benchmarks do

| Benchmark | Form | Lesson for this project |
| --- | --- | --- |
| [SWE-bench Verified](https://codeant.ai/blogs/swe-bench-scores), [SWE-bench Pro](https://arxiv.org/pdf/2509.16941), [DeepSWE](https://arxiv.org/pdf/2607.07946) | Repair a real repository from an issue; hidden fail-to-pass and pass-to-pass tests decide the result. Pro and DeepSWE use long-horizon, multi-file work. | Verified is saturated: independent scores reached 95–97% by July 2026 ([arXiv 2608.13675](https://arxiv.org/pdf/2608.13675)). Difficulty now comes from longer, multi-file tasks. A reported leak, "`.git` history exposes the gold commit" ([SWE-Bench Pro Verified](https://arxiv.org/pdf/2609.08149)), shows that a task repository must not contain its fix. |
| [Terminal-Bench 2](https://arxiv.org/pdf/2601.11868) ([leaderboard](https://llm-stats.com/benchmarks/terminal-bench-2)) | A containerised command-line task with an instruction, tests, an oracle solution and a time limit. | Realistic, hard tasks each with an oracle. Criticism of its small size and narrow error bars argues for many items. |
| τ-bench / τ²-bench | A tool-using agent works under a written policy; success is the final database state, reported as pass^k. | Grading the end state, not the path, plus policy compliance and reliability across repeats. This project already reports pass^k. |
| Aider Polyglot | Hard Exercism problems in several languages; a second attempt sees the test failures. | Test feedback as an explicit, scored second chance. |
| [ZebraLogic](https://arxiv.org/pdf/2502.01100), [Reasoning Gym](https://arxiv.org/pdf/2505.24760), [Enigmata](https://arxiv.org/html/2505.19914v2) | Procedural generators with verifiers and difficulty knobs. | Accuracy falls sharply past a complexity threshold (ZebraLogic's "curse of complexity"). A difficulty sweep therefore yields discrimination curves rather than one saturated number. |
| LiveBench, LiveCodeBench | Questions refreshed over time. | Regenerating or refreshing items limits contamination. |
| [How inference compute shapes evaluation](https://arxiv.org/pdf/2606.17930) | — | Vendor reports mostly do not disclose token, turn or time limits. This project states and records them. |

## Assessment of the current tasks

| Task | Verdict | Plan |
| --- | --- | --- |
| rsn-001 shift scheduling | Saturated; one fixed instance | Becomes generator family R1 |
| rsn-002 derivation check | Saturated except for format; one instance | Becomes generator family R2 |
| tool-001 evidence recovery | Saturated; one small snapshot | Becomes generator family T1 |
| eng-001 import validator | Mostly resolved; partial credit separates a little | Harden as E2; keep the current version as a calibration anchor |
| eng-002, eng-003 (no manifest) | Not runnable | Convert into repository-repair family E1 |
| eng-004 | Baseline missing | Rebuild into E1 |
| eng-005 five-stage trajectory | Not piloted | E3, under a stated budget |
| vis-001 landing page | Static checks and human review only | WP6 |

## Proposed families

Each family has a generator or a curated item list, a verifier that needs no model, difficulty levels, and an oracle solution for self-calibration.

### Reasoning

- **R1 constraint satisfaction**, generalising rsn-001. Generated rostering and assignment instances; difficulty grows with people, days and constraint types, with infeasible instances and minimal conflict sets. A solver verifies answers, and any valid schedule is accepted. Each trial holds 8 to 10 instances and is scored by the fraction solved.
- **R2 derivation audit**, generalising rsn-002. Generated multi-step derivations in kinematics, rates and probability, with one injected error among N steps. Answers are numeric certificates checked by recomputation. Difficulty grows with chain length, subtler errors and distractor steps.
- **R3 logic grids**, after ZebraLogic. Grid puzzles from 3×3 to 6×6 with red-herring clues and a unique-solution check. This form is well established and shows the steepest difficulty curve.

### Tool use

- **T1 evidence recovery at scale**, generalising tool-001. A generated project snapshot of hundreds of files, with distractor files, staging and production conflicts, multi-hop references (a config that names another file), deep pagination and protected paths. Each instance asks 6 to 10 questions. Content is graded from tool evidence in the trace, as now.
- **T2 policy-bound service operations**, after τ-bench. A simulated service with a small database, a written policy and tools (lookup, modify, refund). Tasks need several actions. Grading compares the final database state and checks for forbidden actions. The instructions come in one message; no simulated user, so no second model is needed.

### Engineering

- **E1 repository repair**, after SWE-bench. Project-owned repositories built from eng-002, eng-003 and eng-004, each seeded with several independent defects; each defect becomes one item with hidden fail-to-pass and pass-to-pass tests. The repository history must not contain the fix. Partial credit counts the hidden tests passed.
- **E2 specification implementation**, hardening eng-001. A larger specification with hidden adversarial cases, such as encodings, quoting, numeric edge cases and transactional failure. Partial credit counts cases passed. The current eng-001 stays as an easy anchor.
- **E3 long-horizon maintenance (eng-005).** Five stages in one session under a stated budget.
- **E4 terminal tasks**, after Terminal-Bench. Command-line work in the sandbox, for example repairing a broken build script, reconciling log files, migrating a data file or finding a performance regression. Each task has tests and an oracle. Only the bash and Python tools already in the sandbox are used.

## Difficulty calibration

1. Build each family at three to four difficulty levels, and self-calibrate each level with its oracle and known-wrong solutions.
2. Pilot every level on at least three models: gpt-6-luna-medium, glm-5.3-high and a third model, deepseek-flash or qwen3.8-flash.
3. Keep levels whose mean scores fall between 20% and 80% and that separate models. Retire saturated or impossible levels. Record per-item difficulty and a discrimination index, and use item response theory once there are enough items and models.
4. Audit every failure, as in the 2026-10 pilot, and fix defects with a version bump.
5. Freeze a comparison set and a private holdout set of seeds.

## Visual quality (WP6)

Findings from the literature:

- **Judge reliability is limited.** On paired web pages, the best model judges agree with human experts 66% of the time, against 85% between experts ([WebDevJudge](https://arxiv.org/pdf/2510.18560)). Another study found about 60% for pairwise UI judgements ([MLLM as a UI Judge](https://www.alphaxiv.org/overview/2510.08783)).
- **Pairwise comparison beats single scores.** Single-answer grading was about 8 points less accurate in WebDevJudge.
- **The judge should see screenshots and code together.** Images alone cost 5–9 points in WebDevJudge.
- **A checklist and several screenshots help.** Both improved agreement in [ArtifactsBench](https://arxiv.org/html/2507.04952v2).
- **Decomposed rubrics** are used to combine aesthetic judges ([arXiv 2609.27110](https://arxiv.org/pdf/2609.27110)).

Design:

- **Render.** Headless Chromium in the sandbox renders each submission: desktop 1440×900, phone 390×844 at DPR 2, every form state, and the long-content variant. Rendered measurements become objective checks: overflow, computed contrast, axe-core findings and target sizes.
- **Judge skill.** A versioned `private/judge/SKILL.md` holds the brief, a decomposed checklist, the procedure and a JSON output schema. The checklist covers fit to the brief, hierarchy, clarity, consistency, responsive quality and polish, with evidence for every item.
- **Inputs and comparison.** The judge receives screenshots and source, never the model's name. It compares the submission pairwise with fixed anchors of known quality, in both orders. The score is the share of comparisons won, with a disagreement between orders counted as a tie.
- **Reporting.** Aesthetic scores are a separate, clearly labelled dimension with the judge's measured agreement next to them. They never offset objective defects, given the judge's reliability.
- **Gates before use.** The judge must order the anchors correctly and stay stable under order swaps. Where several judges are used, they must also agree with each other. The user's comments on a sample serve as a reference, not as a gate (decision 4 below).
- **Independence.** No model judges its own vendor's pages. When every available vendor is also evaluated, a panel of judges is used and a page's own vendor is excluded from its panel. The judges' models, versions and the skill's digest are recorded in the run condition.

## Proposed order

1. **R3 and R1:** cheap to build, steep difficulty curves, and they make the statistics meaningful quickly.
2. **T1**, then **E2**.
3. **E1**, from eng-002, eng-003 and eng-004, and **E4**.
4. **T2** and **E3**.
5. **WP6**, in parallel once a judge model and the Playwright dependency are approved.

## Decisions (user, 2026-10-18)

1. **Scope and order:** the families and the order above are approved.
2. **Calibration models:** available now are `deepseek:deepseek-flash`, `supercn:glm-5.3`, `supergpt:gpt-6-luna`, `supercn:step-5-preview` and `supercn:kimi-k3`. Use kimi-k3 sparingly, because it costs more; revisit qwen after its quota resets on 2026-10-19.
3. **WP6:** Playwright may be added, and the judge model is Claude's choice.
4. **Human review:** the project has one reviewer, the user, who is not a design expert. Expert-agreement gates are therefore not feasible, and judging is delegated to models. The user's comments on a sample of pages are recorded as a reference for the judge, not as ground truth. The judge is checked instead for anchor ordering, order-swap stability and agreement between judges.
