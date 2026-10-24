# Capability Card: R3 logic grids 0.4.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP1.6) for grader 2.0.0 on task 0.3.0; updated for 0.4.0 (WP2.3: validation and holdout shapes, the answer-only profile).

## 1. Identity

- Tier: core.
- Capabilities: reasoning.
- Protocol: answer-only (`toolProfiles: ["none"]` from 0.4.0: no tools, one reply; the v1 pilots had a read-only empty workspace and no execution, which was answer-only in effect); one session per task; fixed budget track; 300,000 tokens per task in the v1 pilots (to be calibrated on the budget curve before validation).
- Primary score: resolved (every cell of the grid right).

## 2. What it measures

Deductive reasoning over a closed constraint system held in context: from 30–79 clues about houses and attributes, deriving the single assignment they admit, by chaining eliminations whose consequences are several steps away from any one clue, without writing or running a solver.

## 3. What it does not measure

- Knowledge: the puzzles are generated and fictional.
- Programming: there is no execution, so a constraint solver cannot be written and run.
- Long-horizon work or tool use.
- Speed: time and tokens are reported, not scored.

## 4. Where the difficulty lies

The clue sets are minimal: removing any one clue admits a second solution, so every clue carries information and no subset of easy clues settles the grid. At 8×8 to 10×10 a correct solution requires many interacting eliminations (positional clues such as "one house between" and "directly left" combine across attributes), and a single wrong inference propagates to many cells. The bottleneck is keeping a large partial assignment consistent through long chains of case analysis in one response. In the 0.3.0 pilot (re-graded under grader 2.0.0) deepseek-flash resolved 6/8, 7/8 and 4/8 of the 8×8, 9×9 and 10×10 grids, qwen3.8-flash 1/8, 1/8 and 0/8, and both mimo models none at 10×10, where most of their replies hit the single-response output limit.

## 5. Cheapest shortcut

- Writing a solver: not possible (no execution).
- Guessing: an assignment drawn without reasoning has a negligible chance of being entirely right; cell accuracy rewards near misses, which is why it is a diagnostic, not the headline.
- Recall: the puzzles are generated for this project and unpublished.
- Format games: the answer is one JSON object; a recovered answer is graded on its content, and the PLAN-005 deduction is reported as a separate column (decision D2).
- Offline score of the shortcut (a random permutation per attribute): resolved 0, cell accuracy about 1/n.

## 6. Anchors and headroom

- No metric anchors: the primary is the resolved rate. The diagnostic metrics (cell accuracy, constraint validity, well-formedness) are raw values without anchors.
- Headroom: in the 0.3.0 pilot no model resolved more than half of the 10×10 grids; larger grids or other clue structures can be added by the generator. Output-limit stops are reported in their own column, so that a reply cut off by the response cap is not read as a wrong inference.

## 7. Source, licence and provenance

- Project-authored generator (`private/generate.py`, seed `r3-2026-10`, eight puzzles per level); the form is inspired by ZebraLogic (arXiv 2502.01100), no text copied.
- Exposure: generated, private to runs.

## 8. Task contract and grading

- The model receives the puzzle (houses, attributes with their values, numbered clues) and must reply with one JSON object `{"solution": {"1": {"<Attribute>": "<value>", ...}, ...}}`.
- Checks: one critical check per cell; names and values match after trimming and ignoring case. The format check is apart.
- Score model: one group `cells` (rule fraction, critical); resolved when every cell is right; diagnostic = cell accuracy.
- Metrics (grader 2.0.0, diagnostic): `cellAccuracy`, `constraintValidity` (the share of clues the submitted assignment satisfies, a clue failing when a value it names is not placed exactly once), `wellFormed` (1 when every attribute is a permutation of its values).
- Equivalent answers: attribute and value case, key order, whitespace.

## 9. Splits and size

- Structure group: the grid shape (`size:<houses>x<attributes>`), since every item of a shape comes from the same generator template.
- dev: the 56 items of L1–L7 (square grids 4×4 to 10×10), all seen in pilots.
- validation and holdout (0.4.0, PLAN-007 WP2.3): new structure groups, never piloted: the twelve rectangular shapes with 7–10 houses and 7–10 attributes, dealt by a seeded shuffle (`r3-2026-10-splits`) six to each split, four puzzles per shape. Validation: 7×9, 7×10, 8×10, 9×8, 9×10, 10×7 (24 puzzles); holdout: 7×8, 8×7, 8×9, 9×7, 10×8, 10×9 (24 puzzles). Mean clue counts 54.4 and 51.9, between L5 (46) and L7 (76). Their contents were not read while designing; only the generator log's shapes and clue counts.
- Six groups per split, so intervals are available (MEASUREMENT §5); with six equal groups each weighs 1/6 ≈ 16.7%, under the 20% cap.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: every key (all 104 puzzles) has exactly one solution and passes every cell, metrics at 1 | `python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.4.0-grader-2.0.1.log` (1248/1248) |
| Null agent | pass: an empty or unparsable reply fails every cell | self-calibration |
| Mutants | pass: a swap of two values fails exactly those cells and lowers constraint validity | self-calibration |
| Alternative valid solutions | pass: case and fencing variants | self-calibration |
| Adversarial | n/a: no workspace material, no execution | — |
| Coverage invariant | n/a: no state | — |
| Global end state | n/a | — |
| Noise | n/a: nothing timed | — |
| Determinism | pass: grading is a pure function of the reply and the key | — |

## 11. Budget

Not yet calibrated for v2. The v1 pilots used 300,000 tokens per task, and output-limit stops at L7 were common for some models; the budget curve (PROTOCOL §2) comes first in Phase 4.

## 12. History

- 0.1.0–0.3.0: levels L1–L7 added; see `calibration.md`.
- Grader 2.0.0 (2026-10-24): manifest v2, resolved headline, diagnostic metrics; the v1 trials of the 0.3.0 pilot re-graded into v2 outcomes.
- 0.4.0, grader 2.0.1 (2026-10-24): 48 validation and holdout puzzles in twelve new shapes; the `none` tool profile. The L1–L7 items and keys are byte for byte those of 0.3.0, and the grading logic is unchanged (2.0.1 changes only the task version it reports). 0.3.0 results stay under 0.3.0.
