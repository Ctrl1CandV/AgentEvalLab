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

### Calibration 2026-10-18 (task 0.1.0)

Runs `e239c8f3` (L1–L3) and `d886d0fb` (L4), four models; details in `docs/reviews/2026-10-19-task-set-v2-calibration.md`. L1–L3 are close to saturation, and L4 separates the models: no L4 item was solved by all. deepseek-flash answered every question at every level. The audit found two grader defects, fixed in graders 1.1.0 and 1.2.0: a complete or passed-over search now proves a key absent, and an exclusion glob no longer counts as touching `secrets/`.

## Version 0.2.0 (2026-10-19)

- **L5** (four items, 12 questions, 67 files, about 740,000 characters):
  - shared files that a prod.toml includes, with the precedence stated in docs/CONFIG.md;
  - a count over the lock file by license and major version;
  - a count of one client's 5xx responses on one path across all six audit logs;
  - an absent key that staging.toml and prod.toml.bak both set.
- The recovery question now asks for the file where the value is set as evidence, as the config question already did.
- L1–L4 snapshots and answer keys are unchanged; only that recovery wording differs in their prompts.
- Grader 1.3.0 grades `lock_count` like `log_count` and `log_total` by count and shown lines. The absence self-check now runs on whole-snapshot searches, so it also covers include lines and shared files.
- Every L5 answer was also recomputed independently from the snapshot files.
- Self-calibration: 424/424; see `logs/self-calibration-0.2.0.log`.
