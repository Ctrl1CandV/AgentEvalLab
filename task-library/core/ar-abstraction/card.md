# Capability Card: AR abstraction and reasoning 0.1.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP3.1), before any model run.

## 1. Identity

- Tier: core.
- Capabilities: reasoning.
- Protocols, reported as separate family rows and never averaged together:
  - **answer-only** (`toolProfile: "none"`): the task in the prompt, one reply;
  - **with code** (`workspace-basic` with Python): the same prompt, and the task as `public/task.json` to compute on.
- One session per task; fixed budget track. Budgets are provisional (answer-only 300,000 tokens, with code 1,000,000 tokens per task) until the budget curve on three dev tasks (PROTOCOL §2, Phase 4).
- Primary score: resolved (every test output matched within two attempts).

## 2. What it measures

Inducing a transformation rule from two to seven input–output examples of small coloured grids and applying it to new inputs: abstraction from few examples over objects, counting, symmetry, geometry and composition, with nothing to recall. With code, the same induction, with the option of checking a hypothesised rule as a program on the examples.

## 3. What it does not measure

- Knowledge or language: the tasks are grids of digits.
- Long-horizon work or tool use beyond running one's own code (with code).
- Speed: tokens and time are reported, not scored.

## 4. Where the difficulty lies

Each task's rule is new: it must be inferred from a handful of examples and hold for all of them, and the answer is checked exactly, size included, so a nearly right rule earns nothing. ARC-AGI-2 tasks were built to need several interacting rules (compositional and contextual application of symbols), and each was solved by at least two people in at most two attempts in a controlled test (average human 66% at release); current frontier systems remain far from that on ARC-AGI-2, which gives headroom. ARC-AGI-1, easier and older, gives the lower part of the scale. The bottleneck is forming and verifying the right hypothesis, not executing it.

## 5. Cheapest shortcut

- **Recall.** Both public evaluation sets are on the web (ARC-AGI-1 since 2019, ARC-AGI-2 since 2025), with outputs, and 376 of the 400 ARC-AGI-1 evaluation tasks are also in ARC-AGI-2's public training set. Every task is marked `exposure: public`. ARC-2 is the family's headline; ARC-1, with its overlap, runs answer-only as a low-weight reference row outside the capability profile (user decision of 2026-10-25; no per-model contamination flags).
- **Guessing**: an output grid is exact or nothing; the copy-the-input or most-common-colour answers match only where the rule is that trivial.
- **Format games**: the answer is one JSON object; a recovered answer loses 10% of its primary (user decision of 2026-10-25).
- **More attempts**: only the first two per test input count.

## 6. Anchors and headroom

No metric anchors (contract task, resolved headline). Raw diagnostics: `testShare` (share of test outputs matched) and `wellFormed`. Headroom: ARC-AGI-2, where humans who attempt a task solve it and current models mostly do not.

## 7. Source, licence and provenance

- ARC-AGI-1 public evaluation (`fchollet/ARC-AGI` @3990304, François Chollet, Apache-2.0) and ARC-AGI-2 public evaluation (`arcprize/ARC-AGI-2` @f3283f7, ARC Prize Foundation, Apache-2.0); tasks unmodified, licences in `private/licenses/`. The rendering and the instruction are ours.
- Exposure: public. Published 2019-11 (ARC-1) and 2025-03 (ARC-2).

## 8. Task contract and grading

- The model receives the instruction, the task's examples and test inputs (one row per line, digits separated by spaces, with each grid's size), and replies `{"test": [{"attempt_1": grid, "attempt_2": grid}, ...]}`.
- Checks: one critical check per test input (`test-<n>`): attempt 1 or 2 equals the expected grid exactly. Format check apart.
- Score model: one group `outputs` (rule fraction, critical); resolved when every test output is matched; diagnostic = the share matched (the task score TASK_LIBRARY §3.2 names). Format `answer-format`, deduction 0.2 reported separately.
- Equivalent answers: only the grid's values count; key order and whitespace do not.

## 9. Splits and size

- Structure group: the task (each task is its own source).
- Drawn by a fixed seed (`ar-2026-10`), by task, from task ids only: dev 40 (20 ARC-1, 20 ARC-2), validation 80 (30, 50), holdout 80 (30, 50); all 120 ARC-2 evaluation tasks and 80 of ARC-1's. The six ARC-1 evaluation tasks that are also ARC-2 evaluation tasks count once, as ARC-2. Validation and holdout tasks were not opened while building.
- Item level `arc1` or `arc2`, for the per-version rows.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: the official outputs resolve all 200 tasks, in attempt 1 and in attempt 2 | `python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.1.0.log` |
| Null agent | pass: an empty reply or one without an object fails every check | self-calibration; the suite smoke |
| Mutants | pass: one changed cell, a transposed grid, the right grid as a third attempt | self-calibration |
| Alternative valid solutions | n/a: one correct output per test input (ARC's definition) | — |
| Adversarial | n/a: no workspace material beyond the task; with code, the outputs are not in the workspace | — |
| Coverage invariant, global end state | n/a | — |
| Noise | n/a: nothing timed | — |
| Determinism | pass: grading is a pure function of the reply and the key | — |

## 11. Budget

Provisional (answer-only 300,000; with code 1,000,000 tokens per task); the budget curve on three dev tasks comes first in Phase 4.

## 12. History

- 0.1.0 (2026-10-24): built from the public evaluation sets; no model run.
