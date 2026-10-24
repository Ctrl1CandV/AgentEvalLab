# Calibration Record: R1 Shift Roster

R1 is a generated reasoning family of Task Set v2 (PLAN-005 WP5) that generalises rsn-001. Each item is a roster instance:

- Coverage is a fixed rule: every shift is staffed by exactly the required number of people.
- Each instance adds a subset of seven optional rules: availability, max_shifts, min_shifts, one_per_day, rest, senior and apart.
- Half the items of each level are feasible and half are not. Every infeasible item's smallest conflict involves at least two rules.

`private/roster.py` decides feasibility for any subset of rules. It is a depth-first search with memoised failures. Rules that concern one shift or one day are checked before the search, and capacity bounds for max_shifts, min_shifts and senior prune it. The grader uses the same solver to accept any minimal conflict set, not only the ones recorded in the key.

## Version 0.1.0 (2026-10-18)

- Built with `python3 private/generate.py --seed r1-2026-10 --per-level 8`: 32 items, 8 per level, 4 feasible and 4 infeasible.
- Self-calibration (`python3 private/grader.py --self-calibrate`) checks:
  - the solver agrees with exhaustive search on 60 random small instances and rule subsets;
  - every feasible item is feasible, its example roster passes every check, and a fenced example is recovered;
  - an empty roster and a wrong verdict score 0;
  - every infeasible item is infeasible, and every recorded conflict is minimal and passes;
  - a non-minimal superset fails, a verdict without a conflict gets half the checks, and a claim of feasibility fails.

  See `logs/self-calibration-0.1.0.log`.
- No model has been run yet.
