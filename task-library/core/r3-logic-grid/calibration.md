# Calibration Record: R3 Logic Grid

R3 is the first generated family of Task Set v2 (PLAN-005 WP5). Its form follows ZebraLogic: logic grid puzzles whose difficulty grows with grid size. The package is built from a seed by `private/generate.py`. The generator draws a random solution, adds true clues of eight kinds until exactly one solution remains, then removes every clue whose removal keeps the solution unique. Every item therefore has a unique solution and a minimal clue set.

Attribute values are fictional or deliberately unusual combinations, and each puzzle is new, so memorised puzzles do not help.

## Version 0.1.0 (2026-10-18)

- Built with `python3 private/generate.py --seed r3-2026-10 --per-level 8`: 40 items, 8 per level, L1 4×4 to L5 8×8.
- Self-calibration (`python3 private/grader.py --self-calibrate`) checks, for every item:
  - the counting solver finds exactly one solution, and it equals the key;
  - every clue is true under the key;
  - every clue is necessary;
  - the key passes every cell;
  - a fenced key is recovered and loses only the format check;
  - swapping two values fails exactly those two cells;
  - names and values match case-insensitively;
  - an unparsable answer fails every cell.

  See `logs/self-calibration-0.1.0.log`.

### Calibration 2026-10-18 and 2026-10-19 (task 0.1.0)

See `docs/reviews/2026-10-19-task-set-v2-calibration.md`.

- L3–L5 discriminate: deepseek-flash 86%, step-5-preview 60%, glm-5.3 57%, gpt-6-luna 17%.
- At L5, 13 of 24 trials of the three thinking-heavy models stopped at the 65,536-token limit of a single response. That limit bound most of them, so the next calibration raises it.

## Version 0.2.0 (2026-10-20)

- **L6**: eight 9-by-9 puzzles of 58–64 clues, so that the strongest model is not near saturation once longer responses are allowed. Generating a 9-by-9 puzzle takes about 2.5 seconds.
- L1–L5 items and keys are unchanged; each item's seed is its id.
- Self-calibration: 432/432; see `logs/self-calibration-0.2.0.log`.

### Calibration 2026-10-20 (task 0.2.0)

L4–L6 on five models (`experiments/r3-calibration-2026-10/README.md`): deepseek-flash solved every puzzle, L6 included (100%), while the others scored 14–60%. The strongest model is saturated, so the family needs a harder level.

## Version 0.3.0 (2026-10-20)

- **L7**: eight 10-by-10 puzzles of 73–79 clues, every attribute category the generator has. Generating one takes 5–7 seconds.
- L1–L6 items and keys are unchanged.
- Self-calibration: 504/504; see `logs/self-calibration-0.3.0.log`.

## Grader 2.0.0 (2026-10-24, task 0.3.0 unchanged)

PLAN-007 WP1.6: R3 is the first contract family on manifest v2.

- **Manifest v2:** tier core, capability reasoning, the capability card `card.md`, a score model with a resolved primary and one critical group of cells (rule fraction), the format check apart, and three diagnostic metrics. Every item is in the dev split (all have been seen in pilots); a structure group is a grid size.
- **Grader result v2:** `cellAccuracy`, `constraintValidity` and `wellFormed` beside the cell checks.
- **Self-calibration** (`logs/self-calibration-0.3.0-grader-2.0.0.log`, 672/672): besides the earlier rows, every key scores 1 on all three metrics; a swap of two values stays well formed but breaks some clue (the clue set is minimal and the solution unique); a duplicated value is not well formed; an unparsable reply scores 0 on all three.
- Items and keys were regenerated from the same seed and are byte for byte the same.
- The trials of the 0.3.0 pilot (`runs/e3b89e80-676e-4b9b-a3dc-f5e2ddff6bfb`) were re-graded under 2.0.0 into new score runs with v2 outcomes.

## Version 0.4.0, grader 2.0.1 (2026-10-24, PLAN-007 WP2.3)

**Splits.** Validation and holdout come from new structure groups, never piloted (VALIDATION §3): the twelve rectangular shapes of 7–10 houses by 7–10 attributes, dealt by a seeded shuffle (`r3-2026-10-splits`) six to each split, four puzzles per shape, from the same seed (`r3-2026-10`, item ids `P<houses>x<attributes>-NN`). Validation: 7×9, 7×10, 8×10, 9×8, 9×10, 10×7; holdout: 7×8, 8×7, 8×9, 9×7, 10×8, 10×9. Mean clue counts 54.4 (validation) and 51.9 (holdout), against 46 (L5), 61 (L6) and 76 (L7). Only these structure figures were read; the puzzles were not opened. The 56 items of L1–L7 and their keys are byte for byte unchanged and stay dev.

**Answer-only.** `toolProfiles: ["none"]`: the model gets no tools and answers in its reply. The v1 pilots ran with a read-only, empty workspace and no execution (at most two tool calls, which could only list an empty directory), so the protocol is the same in effect; formally it is a new condition, which the Phase 4 R3 re-check runs on dev.

**Grader 2.0.1** reports task version 0.4.0; the grading logic is that of 2.0.0. Self-calibration 1248/1248 (`logs/self-calibration-0.4.0-grader-2.0.1.log`): every one of the 104 keys has exactly one solution and passes every cell.
