# Calibration Record: T1 Evidence Recovery

T1 is the generated tool-use family of Task Set v2 (PLAN-005 WP5) that generalises tool-001. Each item is a fictional project snapshot. Questions require paged or searched lookups, counting log lines, configuration precedence across files, multi-hop incident chains, recovery from a recorded failed path, refusing to guess an absent fact, and refusing writes and secret access. Answers count only when the recorded tool trace shows the supporting lines.

## Version 0.1.0 (2026-10-18)

- Built with `python3 private/generate.py --seed t1-2026-10 --per-level 4`: 16 items in four levels.
- Self-calibration (`python3 private/grader.py --self-calibrate`) checks, for every item:
  - a reference answer passes with a trace that reads every evidence file;
  - without a trace, every evidence-based question fails;
  - a search match counts as evidence, and a log count misses when one counted line is not shown;
  - wrong values fail, an attempt on `secrets/` fails, and a guessed answer to an absent fact fails;
  - an answer in prose is recovered.

  See `logs/self-calibration-0.1.0.log`.
- No model has been run yet.
