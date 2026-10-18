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
- No model has been run yet. The difficulty of each level is unknown until the calibration pilot.
