# Eng-005 Work Order CLI Long-Cycle Maintenance Task Card

Status: development calibration, not a formal holdout.
Family: eng-workflow-evolution.
Unit: one model, condition, and repetition form a continuous trajectory. Five stages and up to two deliveries are not independent samples.

## Fixed setting

Maintain an offline TypeScript work-order CLI from a pinned baseline commit. Use Node 22 and the standard library only. No network or third-party packages. Seed data includes empty descriptions, repeated timestamps, and multiple statuses. Directory layout, dependencies, commands, pagination, status rules, migration, and errors are defined by the currently released stage materials under task-library/candidates/eng-005-long-cycle-maintenance/stages/.

## Five stages

| Stage | Request | Public checker | Private requirements |
| --- | --- | --- | --- |
| S1 | Status filtering, stable sorting, pagination | public-s1 | BASE_CLI, BASE_DATA, QUERY |
| S2 | Dependency graph, cycle rejection, state progression, completion prerequisites | public-s2 | Add DEPENDENCY |
| S3 | Reproduce rejected operations and prove byte-level no-write behavior | public-s3 | Add NO_MUTATION |
| S4 | v1 to v2 migration, events, idempotence, data preservation | public-s4 | Add MIGRATION |
| S5 | Unified error protocol, stable codes, final documentation | public-s5 | Add ERRORS_DOCS |

The private grader runs only requirement IDs active at that stage. Public checker results may produce one repair hint; hidden grading never provides feedback to the candidate. The runner invokes the pinned checker file from the package, not a candidate-workspace copy.

## Private requirement mapping

The manifest and private grader contain the complete requirement/check ID mapping. Requirement groups cover baseline CLI, source-data preservation, queries, dependencies, failure atomicity, migration/events, and errors/documentation. The S4 migration fixture is independent of the candidate's current data. Grade each stage and cycle snapshot separately; passing S5 cannot retroactively repair S1-S4.

## Calibration set

- ref-a and ref-b are behaviorally equivalent reference implementations with different organization; each complete trajectory is repeated three times.
- mutants/late-repair passes only the final snapshot; earlier checkpoints must retain failures.
- mutants/lost-migration-data drops null or non-English field values during migration.
- mutants/s4-query-regression breaks an earlier query during migration.
- Additional cases cover incorrect event sequence numbers, empty checker output, fabricated self-tests, tampered candidate checker copies, output/time limits, and stages not reached because of budget exhaustion.

This is trusted local task code, not an OS security sandbox. Run it only in an approved offline candidate directory. Any formal model-capability claim requires a separately authorized API batch and repeated runs.
