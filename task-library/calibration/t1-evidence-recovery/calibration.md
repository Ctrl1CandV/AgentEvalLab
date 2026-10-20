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
- Grader 1.3.1 (2026-10-19): with a single change file in the snapshot, an incident answer needs only the change and the config line. A calibration trial answered correctly through the only change file without reading the review, a sound shortcut that 1.3.0 failed. A later version should add decoy changes, so that the chain has to be followed.

## Version 0.3.0 (2026-10-20)

deepseek-flash answered every L4 and L5 question, so L5 could not place the strongest model in the 30–80% band. L6 has four items, 15 questions each, about 100 files and 1,080,000 characters:

- **Nested includes.** Two shared files include a third, and precedence runs through the chain.
- **Change history.** Every production change has a dated record with its value before and after. Two questions ask for a key's value at the end of a past day, and one key's latest change is the incident's change, so decoy changes for the same service surround it.
- **Upstreams.** A second failed read in `prior_attempt.log` needs the `timeout_ms` of the service another service sends requests to, which prod.toml names.
- **A join.** One day's 5xx responses for the clients on one plan, from `clients.csv`, are counted.
- **A count above the search limit.** One client's 4xx and 5xx responses across all eight logs (62–86) cannot be found with a single search.

L1–L5 snapshots and keys are unchanged.

Grader 1.4.0:

- grades `config_at_date`;
- treats only configuration files' whole-file proofs as proofs of absence, so `prior_attempt.log` and `clients.csv` must be read.

Every L6 answer was also recomputed independently from the snapshot files. Self-calibration: 584/584; see `logs/self-calibration-0.3.0.log`.

### Calibration 2026-10-20 (task 0.3.0) and grader 1.4.1

Run `3a683df7`, L5 and L6 on five models; see `experiments/t1-calibration-2026-10/README.md`. The audit found two grader defects, both fixed in grader 1.4.1:

- **A date question accepted only one of two valid evidence files.** The value at the end of a day appears as the `To` of the last change on or before it and as the `From` of the next change. gpt-6-luna cited the latter with the right value. Both now count, each shown in full.
- **An answer complete except for its final closing brace scored 0.** qwen3.8-flash did this, and it is the kind of format slip that principle 2 deducts by 20%. Such an object is now recovered.

Every other failed question was the model's own:

- wrong counts and values;
- an include chain not followed;
- a value given without the evidence that it is not overridden;
- `secrets/` listed.

Self-calibration: 622/622.
