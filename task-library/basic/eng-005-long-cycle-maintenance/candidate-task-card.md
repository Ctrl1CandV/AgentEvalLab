# Candidate Task Card: eng-005 Long-Cycle Maintenance

## Identity

- ID: `eng-005-long-cycle-maintenance`
- Family: long-horizon engineering maintenance
- Status: development calibration; not frozen
- Contract: five sequential maintenance stages in one workspace and one continuous agent session

## Purpose

Observe implementation, feedback repair, regression control, data migration, error handling, and final delivery across related requests.

## Stage sequence

1. Add stable query filters, sorting, and pagination.
2. Add dependency relationships and state-transition constraints.
3. Preserve atomicity on rejected operations.
4. Migrate persisted state and append an event history.
5. Standardize errors and verify the complete system.

Only the current stage instruction should be projected. Each stage has a bounded public check and at most one repair cycle. Private grading uses preserved snapshots.

## Limits

Offline reference replays and mutations validate the recorded task contract and harness behavior. They do not establish real-agent capability, provider context limits, or cost.
