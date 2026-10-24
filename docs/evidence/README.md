# Evidence

This folder holds the evidence tables: what each recorded result is, under which task, grader and protocol it was produced, and where its trials live. A number is quoted from here, or from the run directory the table names, never from memory or from a review's prose.

| File | Contents | Produced by |
| --- | --- | --- |
| [V1_EVIDENCE.md](V1_EVIDENCE.md) | Every v1 run and suite run under `runs/`: family, task and grader version, protocol, models, items and trials, coverage, score, completion status, run directory. Dry runs, interrupted runs and configurations never run are listed as such and never shown as results. | `npm run evidence` (`scripts/evidence-table.ts`) |
| [v2-proof/report-v2.md](v2-proof/report-v2.md) | PLAN-007 WP1.6: report v2 over R3 (its 0.3.0 pilot re-graded into v2 outcomes) and AE 0.2.0 (reference programs as pseudo-models). A fixture that proves the measurement layer, not a model comparison. | `node --import tsx scripts/measurement-proof.ts` |

Rules (PLAN-007 Phase 0, `docs/design/v2/MEASUREMENT.md` §8):

- **v1 numbers keep their version.** A v1 score is the v1 partial-credit score of its own task and grader version, under its own protocol. It is never relabelled as a v2 score. A v1 package re-graded under a later grader version appears as a separate row with that grader version.
- **Rows under different protocols are never merged.** Budget, context policy, thinking level and the items scored are part of every row.
- **A dry run is not a result.** Suite dry runs and null-agent smoke runs are listed under their own heading, without scores.
- **Coverage is explicit.** Infrastructure failures, trials not run and unscored trials are counted, never treated as zero, never dropped silently.
- **Regenerate, do not edit.** The tables are generated from `runs/`. Corrections go into the generator or the run records (by an append-only re-grade), then the table is regenerated.

The `v1-final` tag (local) marks the last commit before the v2 restructure began.
