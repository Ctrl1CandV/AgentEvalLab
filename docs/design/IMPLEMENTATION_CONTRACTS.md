# Implementation Contracts

## Evaluation plan

A plan pins its schema version, case IDs, models, budgets, task-package paths and hashes, tool profiles, and execution policy. Validate the complete plan before creating a run directory or loading credentials.

Plans use schema version 3. Each model entry may set `thinkingLevel` (default `"off"`) and `temperature` (default 0; `null` omits the parameter).
- `"provider-default"` sends no thinking parameter.
- A model whose provider metadata marks thinking as `always-on` cannot be planned with `"off"`, so a recorded condition always matches what the provider received.
- Any other level must be one the resolved model supports (Pi's `getSupportedThinkingLevels`); otherwise validation fails with `THINKING_LEVEL_UNSUPPORTED`. Pi would otherwise clamp the level to the nearest supported one without notice, and a model declared without reasoning would receive no thinking parameter at all.
- Reports label each model with its thinking level appended, for example `supergpt:gpt-6-luna-medium`; `-default` marks `"provider-default"`. A model table at the top of `report.md` lists each label with its thinking level and temperature.
- The runner ends a run with `OUTPUT_TOKEN_LIMIT` when a response reports more output tokens than `maxOutputTokensPerCall`, even if the endpoint ignored the cap. Budgets include `maxToolResultChars`; a larger tool result is returned to the model as a `TOOL_RESULT_TOO_LARGE` tool error, and the run continues. At run start, `experiment.json` records the evaluated condition (`src/evaluation/condition.ts`) and includes it in the run fingerprint:
- git commit and dirty flag;
- Node and Python versions, and Pi package versions;
- resolved model metadata and request options, including whether prices and metadata are verified;
- a digest of each case's tool definitions;
- candidate isolation.

A case selects one supported evaluator. Human evaluation remains pending until a reviewer supplies a score. Pending is neither pass nor fail.

## Task-package boundary

A package manifest identifies its task ID and version, family, capability, usage, entry point, public files, trusted files, requirement IDs, grader protocol, and runtime.

- Public files are copied into the candidate workspace.
- Trusted files and private fixtures stay in the evaluator package.
- Every listed file is checked against its SHA-256 digest.
- The grader runs with bounded time and output and returns a schema-validated result.
- Graders and public checkers that start candidate code prefix every such command with the sandbox launcher given in the grader request's `sandbox` field or the `{sandbox}` checker argument. The value is null or empty only when the plan sets `"isolation": "host"`.
- Candidate-written checks or self-reported status are not trusted evidence.

## Run lifecycle

1. Validate the plan and preflight package hashes.
2. Create an isolated worktree or workspace for each trial.
3. Project only public task files.
4. Run the candidate within the declared model, tool, and resource budgets.
5. Persist the event trace and collect an immutable artifact manifest.
6. Grade the frozen artifact snapshot.
7. Clean up the workspace and record cleanup failures separately.
8. Write per-trial records and a report. The report has operational counts and, for each model and task:
   - decided trials, pass rate, and 95% Wilson interval;
   - pass@k and pass^k for k = repetitions;
   - per-check rates and malformed-answer counts.

   Model differences are paired per task and compared only within one capability. No rate is pooled across unlike tasks. `--merge` combines run directories with identical fingerprints into one report.

## Events, privacy, and usage

Events are append-only and sequenced. If persistence fails, the run reports an infrastructure failure rather than a complete result. Stored output is redacted and truncated to the configured limit. Never serialize credentials.

Usage is attributed to candidate, probe, or another declared interaction. Missing, partial, and reported usage remain distinguishable. Unknown usage must not be interpreted as zero.

## Grading and recovery

A task grader receives a bounded request containing the trial ID, submission directory, and task-specific context. It returns checks with stable requirement IDs and pass, fail, or unknown values.

The objective verdict depends on critical requirements only: a failed critical check means `failed`, a missing critical check means `unscored`, and otherwise the trial `passed`. Missing non-critical checks, such as human-review items, do not change the verdict. They are reported as `review: pending`. A reviewer records them with `--import-review` (`src/evaluation/regrade.ts`), which appends a `human-review` score run that cites the previous run. The trial record and earlier score runs are never rewritten.

A score run references the original artifact manifest and task version. Regrading appends a new score run; it does not replace the original result. Snapshot restoration verifies the file manifest and writes into a new, nonexistent destination.

## Batch containment

A plan's `batch` block (`src/evaluation/batch.ts`) bounds a whole run.
- Provider requests are retried up to `maxRetries` times for 408/409/429/5xx and connection errors before any output streams; each HTTP attempt is recorded on the request.
- Provider errors are classified. A full context window becomes `CONTEXT_LIMIT`, a budget outcome of the evaluated condition. Authentication, balance, and availability errors are infrastructure failures.
- The batch stops immediately on `PROVIDER_AUTH` or `PROVIDER_BALANCE`, or after `maxConsecutiveInfrastructureFailures` infrastructure failures in a row. It also stops scheduling new work once known usage reaches `maxTotalTokens` or `maxCostUsd`. Usage that the provider did not report is counted separately, never as zero.
- Unscheduled trials are listed under `batch.notRun`, and the report is marked incomplete.
- `--resume <run>` continues a single-run batch only when the fingerprint is unchanged. It reruns missing and infrastructure-failed trials; each replacement names the trial it supersedes, which stays on disk.
- The CLI refuses provider requests unless `batch.maxTotalTokens` is set.

## Continuous trajectories

A trajectory is one trial with a shared workspace and agent session. Stage records retain cycle-level execution, public checks, snapshots, private grades, and active requirements. Stage budgets and the trajectory budget are enforced separately.

Public checkers run against disposable copies, so they cannot alter the archived submission. Candidate timeout is a task outcome; grader timeout or protocol failure is an evaluator error.
