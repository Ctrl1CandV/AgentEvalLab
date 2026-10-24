# Capability Card: AE algorithm engineering 0.2.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP1.6); updated for grader 2.1.0 (WP3.5: a greedy reference for every problem, fresh seeds).

## 1. Identity

- Tier: frontier.
- Capabilities: engineering.
- Protocol: the workspace with command execution (`workspace-augmented`); one session per task; fixed budget track (30,000,000 tokens per task in the prepared dev plan, to be calibrated on the budget curve); commands limited to 10 minutes each (`commandLimits`, stated in the tool description).
- Primary score: metric `performance` (AtCoder performance), normalised through the item's anchors, uncapped.

## 2. What it measures

Engineering a program for a hard optimisation problem with no known optimum, under a time limit, by iterating: reading an unfamiliar problem, choosing and implementing a search, measuring it on the official tools, and improving it within a budget. The result is ranked among the human contestants of the original four-hour contest.

## 3. What it does not measure

- General software engineering on existing code bases (ER does), or knowledge of libraries.
- The contest itself: the machine, the language versions and the grace on the time limit differ from AtCoder's, and the model is not under the contest's clock, so a performance here is comparable between models, not a contest result.
- Speed of the model: tokens and time are reported, not scored.

## 4. Where the difficulty lies

The scale is set by people, not by us: a naive valid program for each problem reaches performance 440–990, the median contestant 1,240–1,350 and the winner 3,390–3,530. Going beyond a generic search needs problem-specific insight (the right representation and neighbourhood, a fast incremental evaluation) and careful engineering against the time limit; a short annealing run of a generic move set lands in the middle of the field. No shortcut collapses the problem: the optimum is unknown and the private cases are many (100–200) and varied.

## 5. Cheapest shortcut

- **Recall** of a published solution: these contests are public (2022–2025) and top solutions are often published, so a model may have seen them. Every task is marked `exposure: public`; every delivery is also judged on 50 fresh seeds of our own (`freshTotal`, grader 2.1.0), which separates generalisation from recall of the public seeds; per-model release dates go in the evidence table.
- **A trivial program**: scores at the naive anchor, which maps to 0.
- **Tampering or peeking**: the solution runs in the sandbox, out of reach of the tester, the inputs and the outputs; the self-calibration's tampering and peeking programs change nothing.
- **Spinning or failing cases**: any case not accepted makes the total 0, as in the contest, which puts the delivery at the bottom of the scale.

## 6. Anchors and headroom

| Anchor | Maps to | Source |
| --- | ---: | --- |
| naive | 0 | the item's naive reference (`private/references/`), judged like a delivery (`private/anchors.py`, `private/anchors.json`) |
| median-contestant | 0.5 | the performance at the contest's median rank (ALE-Bench standings and performance table) |
| winner | 1 | the performance of the contest's winner |

- A naive and a greedy reference for every problem (`private/references/`, `private/anchors.json`): greedy performances 909–1,774, far below every winner (`calibration.md`, grader 2.1.0).
- **Fresh seeds** (grader 2.1.0): `freshTotal`, the total on 50 seeds of our own, normalised through the naive (0) and greedy (1) references' totals on them; reported apart, never ranked against the humans.
- **Uncapped.** Above the winner's total the performance extends the winner's by the slope between the two best scores of the standings, and the value is marked `performanceExtrapolated`. The normalised value then passes 1.

## 7. Source, licence and provenance

- ALE-Bench (Sakana AI with AtCoder), NeurIPS 2025 Datasets and Benchmarks: statements, images, tool sources, seeds, standings and performance tables, CC BY-ND 4.0, officially provided by AtCoder Inc.; used unmodified (the tools compiled, a format shift), not redistributed. Judging logic adapted from the ALE-Bench code, Apache-2.0.
- Exposure: public (the contests and their system-test seeds are public). Contest dates are in each item's provenance.

## 8. Task contract and grading

- The model receives the official statement, the compiled official tools, 50 public seeds and `run.py`, and delivers `public/main.cpp` (or `main.py`).
- One check per task, `<item>-accepted` (critical): every private case accepted. The group `performance` (rule metric) weighs the normalised performance in the diagnostic, within [0, 1].
- Raw metrics (grader 2.1.0): `performance`, `total`, `performanceRank`, the diagnostic flag `performanceExtrapolated`, and `freshTotal`.
- Resolved = a valid delivery (every case accepted); the primary is the normalised performance of a valid delivery, 0 otherwise.
- Equivalent solutions: any program in the allowed languages; only its outputs count.

## 9. Splits and size

- Structure group: the contest (one problem).
- dev: AHC015, 035, 039, 046 (calibrated by hand for 0.1.0, named in the dev plan). validation: AHC026, 028, 032, 041, 042, 044. holdout: none yet; it comes from contests added later (ALE-Bench additions, long contests), never from these ten.
- Writing the six validation problems' naive references meant reading their statements. That is anchor construction, like validating an ER task's gold patch: nothing about the task or its grading was tuned on them.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: every naive and greedy reference reproduces its performance and fresh total, the greedy above the naive on both seed sets | `python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.2.0-grader-2.1.0.log` |
| Null agent | pass: no solution gives a total of 0, not accepted | self-calibration |
| Mutants | pass: an illegal output, a compile error and a spinning program score 0 | self-calibration |
| Alternative valid solutions | pass: C++ and Python solutions are both judged; C++ is preferred when both exist | self-calibration |
| Adversarial | pass: tampering with the tester and reading the private inputs change nothing | self-calibration |
| Coverage invariant | n/a: the delivery is a program, judged afresh | — |
| Global end state | n/a | — |
| Noise | pass: a search that uses the whole time limit gets the same verdicts and rank with every other core busy (CPU time is measured) | self-calibration |
| Determinism | pass for programs that do not depend on time; a time-bounded search may vary with the machine, which the noise gate bounds | self-calibration |

## 11. Budget

Not yet calibrated. The prepared dev plan (0.1.0) gives 30,000,000 tokens and four hours per task; the budget curve (PROTOCOL §2) on three dev tasks comes first in Phase 4.

## 12. History

- 0.1.0 (2026-10-23): ten short contests; the score was the share of 27 performance rungs (600–3,200).
- 0.2.0 (2026-10-24): manifest v2; the raw performance is the headline, normalised through per-item anchors and uncapped; rungs dropped; naive references for every problem; splits; the instruction states the new scale.
- Grader 2.1.0 (2026-10-24): greedy references for every problem; fresh-seed judging (`freshTotal`). No model has run AE, so nothing to re-grade.
