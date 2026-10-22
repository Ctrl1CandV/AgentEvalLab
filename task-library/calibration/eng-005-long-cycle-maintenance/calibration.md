# Eng-005 Calibration Protocol

## Development calibration sequence

1. Run node build-manifest.mjs from task-library/calibration/eng-005-long-cycle-maintenance and compare the generated manifest hash with the example plan. The generator excludes host caches such as __pycache__ and .pyc.
2. Run npm run check. Compile TypeScript to a temporary directory and run the compiled Node suite; use the compiled CLI for validate-only and confirm that it does not load credentials or call an API.
3. Run node task-library/calibration/eng-005-long-cycle-maintenance/run-calibration.mjs. It executes the fixed public checker and private grader stage by stage against reference source snapshots. Each of ref-a and ref-b is repeated three times. No model is called and Pi reasoning is not simulated.
4. Run the script's fixed-clone mutations for an S4 query regression and lost migration fields. The private grader must reject them. The script also verifies that changing a candidate checker copy cannot replace the pinned checker and fabricated self-tests do not affect private grading.
5. tests/trajectory.test.ts covers Pi session history, one workspace and current-stage projection, one public repair, stopping at the call budget, post-session grading, stage snapshot restoration, a full five-stage pass path, and a fault matrix. Two fixed references are replayed with injected sessions three times to check stable scheduling and grading signatures. Injected sessions send no external requests and are not real model trajectories.

## Pass conditions

Both references pass every active requirement at every stage and produce the same behavior despite different code organization. Three repetitions must be stable. S4 failure cannot be erased by an S5 pass; lost migration data must fail migration.preserve. Candidate checker tampering and self-reported tests cannot change trusted grading. Compiled checks cover continuous Pi transcripts, a shared workspace, future-stage isolation, one repair, post-hoc grading, stage recovery, and global call-budget stopping.

The latest historical log is logs/acceptance-self-calibration.json. It records the manifest hash, Node version, reference repetitions, and mutants. It contains no real model request and proves neither model capability, API behavior, nor methodological validity.

## Limits

Historical development calibration was recorded as complete. Event-sink testing uses injected serialization failures and does not model physical disk failure or power-loss recovery. Real provider context limits, abort latency, and cost require an authorized M5 pilot. The package is development calibration, not a frozen evaluation set.


## Version 0.2.0 (2026-10-13)

The English task material in this repository is the canonical baseline; there is no earlier source text to reconcile against. Version 0.1.1 recorded digests for earlier bytes of the instruction and documentation files, so the package no longer passed preflight. This version re-pins every file digest and resolves the grader and public checkers as `python3` from PATH (Python 3.13 required) instead of a host-specific interpreter path. Grader logic is unchanged; the grader reads the task version from the request.

Calibration results above were recorded against version 0.1.1 and remain historical. Recalibration under 0.2.0 is pending a provisioned Node.js 22 and Python 3.13 environment.


## Version 0.2.1 (2026-10-14)

Candidate code started by the private grader and the five public checkers now runs through the harness sandbox launcher (`scripts/sandbox_exec.py`, bubblewrap): only the candidate's working directory is writable, and the host home directory, the task package (including `private/`), and the network are unreachable. The launcher path comes from the grader request's `sandbox` field (graders) or the `--sandbox-launcher` argument (public checkers); when a plan opts into `"isolation": "host"`, the field is null and candidates run as before. The task contract and check logic are unchanged; the grader version is now 1.1.0.

Recalibration under 0.2.1 is recorded in `logs/self-calibration-0.2.1.log`.


## Version 0.3.0 (2026-10-20)

**Why.** In the first real-model runs of E3 (2026-10-20), every model that reached a stage passed every private check of S1–S4: the private grader exercised little beyond the public checkers, so only S5 separated the models.

**Grader 2.0.0** adds twenty hidden checks, 41 in all. Each one tests behaviour that its stage brief states, which the public checker does not exercise:

- **QUERY (S1), 6 new:**
  - `query.defaults`: no options means page 1, page size 2, sort by createdAt ascending;
  - `query.desc-ties`: ties broken by id ascending under `--order desc` too;
  - `query.sort-keys`: title and id sorting;
  - `query.empty-result`: a filter with no match keeps the response shape;
  - `query.page-size-bounds`: 100 accepted, 0 and 101 rejected;
  - `query.rejects-malformed`: non-integers, negative values, unknown options and out-of-range status, sort and order values are rejected without writing.
- **DEPENDENCY (S2), 5 new:**
  - `dependency.duplicate`;
  - `dependency.unknown` (either side);
  - `dependency.transitive-cycle` (a three-order cycle);
  - `dependency.backward` (no move back from DONE or from IN_PROGRESS);
  - `dependency.all-prerequisites` (DONE only once every prerequisite is DONE).
- **NO_MUTATION (S3), 2 new:** a blocked completion, and duplicate, unknown and cyclic dependencies, each leave the file byte for byte unchanged.
- **MIGRATION (S4), 4 new:**
  - `migration.read-only`: list, show and export keep a version 1 file;
  - `migration.event-details`: events name their order (null for the migration), timestamps are ISO, and two updates share a type;
  - `migration.failed-no-write`;
  - `migration.cli-shape` after migration.
- **ERRORS_DOCS (S5), 3 new:**
  - `errors.codes-all`: DUPLICATE_ID, INVALID_ARGUMENT, NOT_FOUND, DEPENDENCY_CYCLE and DEPENDENCY_NOT_COMPLETE, each for its error class;
  - `errors.store-invalid`: an unreadable store gives STORE_INVALID;
  - `errors.clean-output`: one JSON line, nothing on stderr, exit code 2, for all of them.

**Calibration.** `run-calibration.mjs` passes:

- Both references pass all 41 checks at every stage, three times each. Neither needed a change, which supports that the checks follow the briefs.
- Two new mutants model common shortcuts, and the hidden checks catch exactly them. Reversing the whole order for `desc` fails only `query.desc-ties`. Detecting only direct cycles fails `dependency.transitive-cycle` and `failure.no_mutation-dependency`.
- The grader takes about 10–20 seconds per stage, so plans now give it 300 seconds.

See `logs/acceptance-self-calibration.json`.

## Version 0.4.0 (2026-10-21)

**Why.** Under 0.3.0, qwen3.8-flash passed 41/41 checks, deepseek-flash and gpt-6-luna 40/41: the five stages are well specified, and these models carry out any well-specified brief. PLAN-006 B4 adds a stage that the strong models' first implementations do not survive, and that ranks working ones by speed.

**S6, scale.** The store grows to 100,000 work orders, with:

- a dependency chain 50,000 orders deep;
- a ladder of 32 paired levels, each order depending on both orders below, so paths number in the billions;
- an order with 2,001 prerequisites;
- random prerequisites elsewhere.

`stages/S6/public/make_store.py` writes such a store for the model to test with. The hidden store comes from the same generator under another seed.

The hidden workload (`private/scale.py`) has 15 commands:

- list pages with filters, sorted by createdAt and id (fixed-format strings, so every reasonable comparison agrees);
- show;
- dependency additions that close a cycle through the chain and the ladder, and additions past them that must search all of either;
- a completion blocked by one unfinished prerequisite among 2,001, and one allowed;
- a create and a rename.

Requirement `SCALE` (critical) has three checks: `scale.list`, `scale.dependencies` and `scale.status`. Each compares outputs (error codes for failures) and the final store with the reference in `private/scale-reference`. Requirement `SCALE_SPEED` (not critical: a ladder, not acceptance) has `scale.speed-3`, `-1.5`, `-1.1` and `-0.75`: the workload's total time against the reference's, best of three interleaved runs on one core, after the three correctness checks pass. The reference takes about 5.3 seconds; its floor is Node start-up and parsing a 23 MB store, about 0.3 seconds per command.

**References.** ref-a and ref-b now look up orders through a map and search dependencies iteratively with a visited set. ref-a searches depth first, ref-b breadth first. Both write a version 2 store in place instead of copying it first. `private/scale-reference` is ref-a's source.

The S1–S5 ref-a, the kind of code these stages invite, fails at scale:

- its recursive search overflows the stack on the 50,000-deep chain, so three dependency commands end in errors;
- its prerequisite check scans the whole array for each of 2,001 prerequisites;
- its workload takes 1.65 times as long.

**The untouched project now earns nothing.** On the 2026-10-21 dry run, a null agent scored 8 of 41 checks (19.5%):

- the base and seed checks pass on an untouched project;
- `dependency.self` and `dependency.unknown` passed because an unimplemented `depends` command is rejected too;
- `migration.schema` passed because a read keeps a version 1 file.

Grader 2.1.0 makes base and seed checks guards that count only when a check of a stage's own requirement passes. The rejection checks now also need the command to work where it should, and `migration.schema` needs the first write to migrate.

**Score.** A trajectory scores the share of the final stage's 48 checks that pass in its last graded snapshot. Plans give the whole task 8,000,000 tokens and each stage 2,000,000; the grader gets 15 minutes per snapshot.

**First run (2026-10-22, `runs/suites/20261022-050033-dev-0cdf`).** deepseek-flash and qwen3.8-flash each passed every check of S1–S5 without a repair. Each was stopped in S6 by the stage's 2,000,000 tokens, with a delivery that passes the three correctness checks and every speed rung but `speed-0.75`: 47/48 (97.9%). The null agent scored 0 in the suite's smoke step. S6 did not harden E3 for these models.

