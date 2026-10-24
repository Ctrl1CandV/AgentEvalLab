# Public Scoring Rubric: eng-002

Score requirements by weight. Calibrate and report three dimensions separately: static recovery, real interruption, and atomic publication.

## Dimension A: Static state recovery

Preload journals, outputs, and stale temporary files, run the tool, and inspect final state plus the reported processed/skipped sets.

| State | Required result |
| --- | --- |
| empty | Process all inputs; all outputs and journal entries are correct |
| complete | Skip all items; use unchanged output mtimes as objective evidence of skipping |
| missing_output | Reprocess the item whose journal says done but whose output is absent |
| corrupt_output | Reprocess the item whose output hash is wrong |
| bad_journal | Ignore a truncated final line, reprocess that item, and append without creating another damaged line |
| input_changed | Reprocess the item and reflect the new input |
| stale_tmp | Do not treat a .part file as output; finish with no .part files |

## Dimension B: Actual process interruption

Historical calibration used white-box EE_CRASH hooks in the reference implementation at before_journal, stale_temp, and after_n, then verified recovery. This is not black-box proof. A reproducible external process-kill protocol requires a separate process-control phase and is currently blocked. Do not use random sleeps to guess the interruption point.

## Dimension C: Atomic publication

The stale_temp injection verifies recovery from a .part left before rename. The before_journal injection verifies recovery after output publication but before journal commit. Resume safely recomputes the deterministic output, providing at-least-once behavior.

## Human review

Review clarity of state-machine and atomicity reasoning, races, hard-coded state assumptions, and README accuracy about resume guarantees. Rate modification effort as ready to use, minor edits, restructuring, or rewrite. Ties and inconclusive results are allowed.

## Acceptable implementations

Internal structure, journal field order, and temporary-file naming are unrestricted if the suffix is distinguishable and never treated as published output. Any implementation meeting the contract and final-state requirements passes.

## Not scored

Power-loss exactly-once behavior and concurrency are not promised. Fewer executions do not by themselves imply fewer errors. Historical rejection examples are documented in calibration.md.
