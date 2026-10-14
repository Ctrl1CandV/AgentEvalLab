# Offline Calibration Record: eng-004 Resource Index

Task version 0.1.1; development use only. Historical environment: Node v22.23.3, no network, no dependency installation.

Two reference implementations used different valid approaches. Across three repetitions, each passed all seven checks. Coverage included search filtering, defaults, Unicode code-point ordering, pagination, input rejection, CSV behavior, and index compatibility. Three targeted flawed implementations were rejected: an off-by-one page start, missing CSV escaping, and an incorrect nextOffset.

CSV checks inspect CRLF record boundaries, quoting, embedded LF, and the required final CRLF. Search, legacy index behavior, and CSV export are checked separately. Failure output is stored only as a bounded digest or summary.

## Limits

Offline calibration only demonstrates compatibility between the contract, checker, and reference implementations. No model API was run and no candidate traces were collected for the two proposed tool profiles. A single basic/augmented comparison cannot establish that extra tools reduce rework.


## Version 0.2.0 (2026-10-13)

The English task material in this repository is the canonical baseline; there is no earlier source text to reconcile against. Version 0.1.1 recorded digests for earlier bytes of the instruction and documentation files, so the package no longer passed preflight. This version re-pins every file digest and resolves the grader and public checkers as `python3` from PATH (Python 3.13 required) instead of a host-specific interpreter path. Grader logic is unchanged; only the TASK_VERSION constant in private/acceptance.py changed.

Calibration results above were recorded against version 0.1.1 and remain historical. Recalibration under 0.2.0 is pending a provisioned Node.js 22 and Python 3.13 environment.

The pinned baseline repository (commit 3b43f3c6c2db454f90765de2ca614b783c624c8e) is not available in this repository: baseline/ is an unresolvable Git link. The task cannot run until a project-owned baseline is rebuilt and pinned, which will be a further version change.
