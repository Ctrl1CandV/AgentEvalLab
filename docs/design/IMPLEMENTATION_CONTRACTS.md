# Implementation Contracts

## Evaluation plan

A plan pins its schema version, case IDs, models, budgets, task-package paths and hashes, tool profiles, and execution policy. Validate the complete plan before creating a run directory or loading credentials.

A case selects one supported evaluator. Human evaluation remains pending until a reviewer supplies a score. Pending is neither pass nor fail.

## Task-package boundary

A package manifest identifies its task ID and version, family, capability, usage, entry point, public files, trusted files, requirement IDs, grader protocol, and runtime.

- Public files are copied into the candidate workspace.
- Trusted files and private fixtures stay in the evaluator package.
- Every listed file is checked against its SHA-256 digest.
- The grader runs with bounded time and output and returns a schema-validated result.
- Candidate-written checks or self-reported status are not trusted evidence.

## Run lifecycle

1. Validate the plan and preflight package hashes.
2. Create an isolated worktree or workspace for each trial.
3. Project only public task files.
4. Run the candidate within the declared model, tool, and resource budgets.
5. Persist the event trace and collect an immutable artifact manifest.
6. Grade the frozen artifact snapshot.
7. Clean up the workspace and record cleanup failures separately.
8. Write per-trial and aggregate reports.

## Events, privacy, and usage

Events are append-only and sequenced. If persistence fails, the run reports an infrastructure failure rather than a complete result. Stored output is redacted and truncated to the configured limit. Never serialize credentials.

Usage is attributed to candidate, probe, or another declared interaction. Missing, partial, and reported usage remain distinguishable. Unknown usage must not be interpreted as zero.

## Grading and recovery

A task grader receives a bounded request containing the trial ID, submission directory, and task-specific context. It returns checks with stable requirement IDs and pass, fail, or unknown values.

A score run references the original artifact manifest and task version. Regrading appends a new score run; it does not replace the original result. Snapshot restoration verifies the file manifest and writes into a new, nonexistent destination.

## Continuous trajectories

A trajectory is one trial with a shared workspace and agent session. Stage records retain cycle-level execution, public checks, snapshots, private grades, and active requirements. Stage budgets and the trajectory budget are enforced separately.

Public checkers run against disposable copies, so they cannot alter the archived submission. Candidate timeout is a task outcome; grader timeout or protocol failure is an evaluator error.
