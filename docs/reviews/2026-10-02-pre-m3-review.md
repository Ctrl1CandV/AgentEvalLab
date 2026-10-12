# Reliability Review

This note records the scoped reliability findings addressed before continuing evaluation development.

## Findings and changes

| Area | Finding | Change |
| --- | --- | --- |
| Stage isolation | An early public checker exposed logic from later stages. | Keep each public checker limited to the current stage. |
| Snapshot integrity | A checker could mutate the saved candidate snapshot. | Run public checks against a disposable copy and grade the preserved archive. |
| Timeout attribution | A candidate timeout could be reported as a grader failure. | Treat candidate timeout as a task result; reserve evaluator errors for grader or infrastructure failures. |
| Tool evidence | Repeated or overlapping pages and records split across page boundaries could be rejected. | Merge consistent evidence and reject contradictory overlaps or missing records. |
| CSV records | Delimiter checks did not consistently cover physical record endings. | Validate record boundaries while permitting quoted newlines. |
| Clarification target | A response could claim clarification without naming the missing field. | Require a structured target for the missing parameter. |

## Verification boundary

The fixes were checked with offline reference traces and targeted negative cases. Existing tests and calibration logs remain historical evidence tied to their recorded revisions. No live model API calls or capability measurements were part of this review.

The broader partial-grade branch and general anti-gaming research were intentionally left outside the scoped remediation.
