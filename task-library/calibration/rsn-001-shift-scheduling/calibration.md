# Offline Calibration Record: rsn-001 Shift Scheduling

Task version 0.2.1; development use. The package uses the fixed Python 3.13 standard-library environment and private/acceptance.py.

The oracle checks that A has a valid minimal conflict set, B either gives correct conditional branches or asks a non-empty clarification targeted at daily_need, and C's schedule satisfies the constraints when recomputed. Different valid conflict-set orderings, schedules, and conditional answers are accepted; the oracle's exact prose and schedule are not required.

Targeted incorrect answers and an unrelated clarification target are rejected. Empty or malformed objects are rejected, and repeated evaluation is deterministic. The detailed historical log is logs/acceptance-self-calibration.log.

No real model answer has been run. These few synthetic instances do not represent general CSP ability. B checks one structured clarification/conditional answer and does not implement a multi-turn clarification dialogue.
