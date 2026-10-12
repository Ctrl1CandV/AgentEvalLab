# Calibration Record: eng-002 Resumable Batch v0.2.0

Family: eng-resumable-state. Development calibration only; not frozen. See instruction.md for the contract and rubric.md for scoring.

## Environment and artifacts

Python 3.13.15, standard library only, no network. Historical commands generated fixtures with private/make_fixtures.py and ran private/acceptance.py --self-calibrate. Recorded hashes: acceptance.py b2e18c35e9545208, ref_impl.py 0e03fd2e2efc15d3, and merged state fixtures 2741252162418356 (53 files).

## Recorded results

The reference implementation passed all seven static recovery cases: empty, complete, missing output, corrupt output, truncated journal, changed input, and stale temporary file. The complete case used unchanged modification times to prove that outputs were skipped.

Three white-box EE_CRASH checks passed: failure before journal append, failure with a stale temporary file, and failure after processing two items. Resume converged to the expected state. Three flawed implementations were rejected: trusting the journal (5/7), ignoring changed input hashes (6/7), and an empty implementation (0/7). Repeated runs were consistent. These are historical offline results, not model measurements.

## Review corrections captured in the package

The contract fixes the transformation, path mapping, encoding, traversal order, symlink policy, and journal format. Resume checks journal status, input hash, output existence, and output hash. Atomicity dimensions are reported separately. The complete case checks actual skipping with mtimes. Recovery after publication but before journal append is at-least-once, not exactly-once. The append path repairs a missing final newline. Power-loss durability and random-sleep interruption claims are excluded.

## Open limits

Black-box process termination and real candidate-model runs remain blocked. No production budget was selected, and multi-process execution is out of scope. Status: not frozen.
