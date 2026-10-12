# Pi Harness Notes

## Execution flow

`src/harness/pi.ts` resolves a model, creates a fresh tool collection, constructs a Pi Agent, and sends the supplied prompt. The runner subscribes to agent events and accumulates execution counters.

The harness treats these as separate limits:

- wall-clock timeout
- completed assistant turns
- model requests
- tool attempts
- output tokens per request
- total persisted output characters
- tool-evidence bytes

A limit failure is recorded with its failure kind. It is not silently converted into a successful stop.

## Tools

Tools are selected by a named profile. Each run receives a fresh collection, and duplicate tool names are rejected. Tool implementations execute as trusted host code; profiles and output limits do not provide an operating-system sandbox.

The evidence-recovery profile exposes bounded file and search operations. It records returned evidence and enforces path containment, page limits, and evidence-size limits.

## Providers

Built-in provider catalogs are created in memory. Custom endpoints are registered in `src/providers.ts`. Credentials are loaded only for an actual run and are redacted from persisted output.

A provider request is not made during `--validate-only` preflight. Offline tests may inject a stream function to exercise runner behavior without network access.

## Events and persistence

Events are sequenced and appended. A failed event sink is sticky: later emissions fail, and the caller can rethrow the original error. This prevents a partial event log from being reported as a complete run.

## Evaluation lifecycle

A plan is validated and preflighted before execution. The evaluator creates the workspace, invokes the runner, freezes artifacts, runs the trusted grader, records a score run, and cleans up. A trajectory keeps the workspace and session across stages and stores verified checkpoints.

## Reading path

Read `src/types.ts`, `src/config.ts`, `src/harness/pi.ts`, then `src/evaluation/run.ts`. For continuous work, continue with `src/evaluation/trajectory.ts` and `src/evaluation/trajectory-snapshot.ts`.
