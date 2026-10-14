# Offline Calibration Record: rsn-001 Shift Scheduling

Task version 0.2.1; development use. The package uses the fixed Python 3.13 standard-library environment and private/acceptance.py.

The oracle checks that A has a valid minimal conflict set, B either gives correct conditional branches or asks a non-empty clarification targeted at daily_need, and C's schedule satisfies the constraints when recomputed. Different valid conflict-set orderings, schedules, and conditional answers are accepted; the oracle's exact prose and schedule are not required.

Targeted incorrect answers and an unrelated clarification target are rejected. Empty or malformed objects are rejected, and repeated evaluation is deterministic. The detailed historical log is logs/acceptance-self-calibration.log.

No real model answer has been run. These few synthetic instances do not represent general CSP ability. B checks one structured clarification/conditional answer and does not implement a multi-turn clarification dialogue.


## Version 0.3.0 (2026-10-13)

The English task material in this repository is the canonical baseline; there is no earlier source text to reconcile against. Version 0.2.1 recorded digests for earlier bytes of the instruction and documentation files, so the package no longer passed preflight. This version re-pins every file digest and resolves the grader and public checkers as `python3` from PATH (Python 3.13 required) instead of a host-specific interpreter path. Grader logic is unchanged; only the TASK_VERSION constant in private/acceptance.py changed.

Calibration results above were recorded against version 0.2.1 and remain historical. Recalibration under 0.3.0 is pending a provisioned Node.js 22 and Python 3.13 environment.
