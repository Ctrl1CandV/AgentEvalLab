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
