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

## Version 0.4.0 (2026-10-20)

**Why.** At L6 (task 0.3.0) qwen answered 98% of the checks and glm 95%, while deepseek, step and luna were at 69–81%. The questions that still failed were the counts above the search tool's 50-match limit, the joins with clients.csv, nested includes and the upstream hop.

**L7** keeps only those kinds and makes each heavier: twelve logs of 1,300 lines and 500 packages, about 1.9 million characters per snapshot. It has 14 questions:

- a lock-file count;
- a 5xx join with clients.csv;
- a **distinct count**: clients on one plan with a 4xx or 5xx response on one path on one day;
- a count across all logs above the match limit;
- a **join across every log**: one plan's 4xx responses on one path, 111–182 requests;
- a **median**: the response time of one path's successful requests on one day, the lower middle value of 101–112 requests (new kind `log_stat`, graded like a count: the value, the cited log, and every counted line seen);
- a nested include;
- a **three-deep include**: limits-standard now includes a fourth shared file, limits-floor;
- two values at a past date;
- the upstream hop;
- a **failed read two upstream steps away**;
- the retired-copy trap;
- the secret.

At deep levels the generator guarantees that a two-deep and a three-deep key exist: it reserves keys for the first service.

**Self-calibration:** 828/828 (superseded by 0.4.1). L1–L6 items and keys are unchanged.

## Version 0.4.1 (2026-10-20)

**L7 rescaled.** With twelve logs of 1,300 lines (0.4.0), each request resent 50,000–100,000 tokens of log lines. The first two trials, qwen3.8-flash and mimo-v2.6-flash, used their whole 1,500,000-token budget without giving an answer, despite the 50/75/90% reminders. The level then measured budget management rather than evidence recovery, and the run was stopped.

L7 now keeps L6's data size: eight logs of 1,100 lines and 400 packages, about 1.08 million characters. It also keeps the harder questions of 0.4.0:

- counts of 66–110 requests across all logs;
- a median over about 90 requests;
- distinct counts, three-deep includes, and two upstream steps.

Self-calibration: see `logs/self-calibration-0.4.1.log`. L1–L6 are unchanged.

## Version 0.5.0 (2026-10-21)

**Why.** L7 (0.4.1) still put deepseek-flash at 96% and qwen3.8-flash at 85%, and the only lever left in the L levels was volume, which at twelve 1,300-line logs turned into budget exhaustion (0.4.0). PLAN-006 B2 replaces volume with depth: errors compound with the number of references a question follows, as grid size does for R3.

**The depth ladder** (`private/chains.py`): levels D2, D4, D6 and D8, four items each, five chain questions per item. Snapshots are small (126 files, about 15,000 characters: 18 services with base, prod, staging and retired configs, seven shared files in include chains, changes, reviews and incidents), so depth, not volume, decides.

- A chain runs incident → review → change → the service the change set → its production `upstream`, followed once, twice or three times → a key's effective production value. `upstream` follows the precedence rules too.
- Depth counts the files needed after the incident. D2 asks for the value the incident's change set; D4 to D8 combine one to three upstream steps with values from prod.toml, an included file, a file that one includes, or base.toml.
- Distractors at every step:
  - the incident's timeline names a second review, whose change was rolled back without effect;
  - the review names a superseded proposal;
  - the changed key has a later change;
  - staging.toml, prod.toml.bak and base.toml name other upstreams;
  - shared files, base.toml, staging.toml and retired copies set the same keys.

  Both decoy changes belong to services whose chains end at another answer.
- New question kind `chain`, graded like `config`. The trace must show:
  - every file of the chain, the incident, review and change in full;
  - each step's deciding line;
  - the proofs that nearer files do not set a key.

  A whole-file proof of a configuration file may be a complete search for the key it is about, `upstream` included (grader 1.6.0).

L1–L7 snapshots and keys are unchanged.

**Self-calibration** (`python3 private/grader.py --self-calibrate`, 1690/1690; `logs/self-calibration-0.5.0.log`):

- An independent solver reads only the snapshot text, follows each chain and reproduces every key.
- Taking one step's distractor instead changes the answer:
  - the decoy review and the superseded change always do;
  - over all applicable distractors, 60 of 60 at D2, 100 of 140 at D4, 104 of 140 at D6 and 96 of 140 at D8 do. The rest lead, by chance, to the same end.
- A trace that reads every file of a chain passes; one that leaves out any single file fails; a wrong value fails.

