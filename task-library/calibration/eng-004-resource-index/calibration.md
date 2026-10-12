# Offline Calibration Record: eng-004 Resource Index

Task version 0.1.1; development use only. Historical environment: Node v22.23.3, no network, no dependency installation.

Two reference implementations used different valid approaches. Across three repetitions, each passed all seven checks. Coverage included search filtering, defaults, Unicode code-point ordering, pagination, input rejection, CSV behavior, and index compatibility. Three targeted flawed implementations were rejected: an off-by-one page start, missing CSV escaping, and an incorrect nextOffset.

CSV checks inspect CRLF record boundaries, quoting, embedded LF, and the required final CRLF. Search, legacy index behavior, and CSV export are checked separately. Failure output is stored only as a bounded digest or summary.

## Limits

Offline calibration only demonstrates compatibility between the contract, checker, and reference implementations. No model API was run and no candidate traces were collected for the two proposed tool profiles. A single basic/augmented comparison cannot establish that extra tools reduce rework.
