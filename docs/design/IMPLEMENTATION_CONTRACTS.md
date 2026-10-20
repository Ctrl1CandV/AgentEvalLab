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

## Generated items

A package of a generated family (Task Set v2) declares `items`. Each item has:

- an identifier and a difficulty `level`;
- files under `items/<id>/`: an optional `prompt.md` and `public/...` files;
- the requirements it activates.

Items and trajectory stages are mutually exclusive, and every item must activate at least one critical requirement. Preflight hashes every item file, and the `items/` tree must match the declaration exactly.

A plan case selects items with `items`: `"all"`, a list of item IDs, or `{ "levels": [...] }`. A package with items requires a selection, and an unknown item or level is an error. The case expands into one trial per item (per repetition and model). Each trial is projected as follows:

- the package's shared public files;
- the item's `public/` files, without the `items/<id>/` prefix (a collision with a shared file is an error);
- the prompt: package instruction, item prompt, case prompt and budget statement, in that order.

Preflight refuses a plan whose artifact limits cannot hold a trial's starting files: the package's public files plus the largest selected item's files (`PLAN_ARTIFACT_LIMIT_TOO_LOW`). Without this check, every trial would run and then fail artifact export. The grader request's context carries `itemId` and the item's `activeRequirementIds`; packages without items keep the earlier context unchanged. Records carry `itemId` and `itemLevel`.

Reports group rows by case and level. Paired model differences pair by item, and an Items section counts the items every model solved, none scored on, and those that separate the models. Regrading reuses the item's requirements, together with the trial's recorded answer and verified tool trace.

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

The trial score is partial credit (`trialScore` in `src/evaluation/grader.ts`). It is the weighted fraction of the grader's judged content checks that passed; weights default to 1. When the manifest's `scoring.formatCheckId` check fails, the score is further reduced by `scoring.formatPenalty`. Answer-graded tasks share one recovery rule (user decisions, 2026-10-16 and 2026-10-18). An answer that is not one JSON object is recovered when exactly one JSON object can be found in it: an object that only lacks up to three closing braces at its end (added 2026-10-20, T1 grader 1.4.1; other answer graders adopt it at their next version), the only fenced code block that holds one, or else the only top-level object in surrounding prose. With no candidate, or with several, nothing is recovered, so the grader never chooses between candidate answers. A recovered answer is graded on its content and fails only the non-critical `answer-format` check, so it scores 80% of its content score. An answer that cannot be parsed fails every content check. Human-review checks do not enter the score. Reports give the mean score, with the Wilson interval of the score sum (conservative for scores in [0, 1]), alongside the resolved rate (`passed` verdicts). Paired model differences use mean scores. Tokens per resolved trial and budget stops are reported as efficiency and never enter the score.

A score run references the original artifact manifest and task version. Regrading appends a new score run; it does not replace the original result. Snapshot restoration verifies the file manifest and writes into a new, nonexistent destination.

## Batch containment

A plan's `batch` block (`src/evaluation/batch.ts`) bounds a whole run.
- Provider requests are retried up to `maxRetries` times for 408/409/429/5xx and connection errors before any output streams; each HTTP attempt is recorded on the request.
- Provider errors are classified. A full context window becomes `CONTEXT_LIMIT`, a budget outcome of the evaluated condition. Authentication, balance, and availability errors are infrastructure failures.
- The batch stops immediately on `PROVIDER_AUTH` or `PROVIDER_BALANCE`, or after `maxConsecutiveInfrastructureFailures` infrastructure failures in a row. It also stops scheduling new work once known usage reaches `maxTotalTokens` or `maxCostUsd`. Usage that the provider did not report is counted separately, never as zero.
- Tokens are fixed units: every reported token counts once, cached input included, and no prices are used (user decision, 2026-10-15). `maxTotalTokensPerModel` bounds each model separately; a model that reaches it stops (`MODEL_TOKEN_CEILING` in `notRun`) while the other models continue.
- With `budgetNotice` (single runs only), the model is told its budget (PLAN-005 WP3). One fixed paragraph, `budgetStatement` in `src/harness/budget-notice.ts`, is appended to the task prompt. It lists every limit and says the task stops and is graded as it stands when a limit is reached. Each time usage first passes a reminder threshold of any limit (default 50%, 75% and 90%; user decision, 2026-10-16), one `[Budget status]` user message is queued through Pi's steering hook before the next request. It is recorded as a `budget_notice` event. Tool results stay unchanged, so trace-based graders are unaffected. A live probe on 2026-10-16 confirmed that both the OpenAI and the Anthropic protocol endpoints accept the message. A live run needs either `maxTrialTokens` or a batch ceiling. `--validate-only` prints the worst-case spend: planned trials times `maxTrialTokens`.
- `batch.concurrency` (1 to 16, default 1) runs that many single-run trials at once. Slots are taken in schedule order. Each running trial reserves its `maxTrialTokens` against the ceilings until it is recorded, so concurrency cannot overshoot them, and report writes are serialised. Concurrency changes no evaluated condition, so it is left out of the run fingerprint: a run can be resumed or merged with a different concurrency.
- The optional budget field `maxTrialTokens` caps one trial (one cycle in a trajectory). Before a further request, a trial over the cap ends with `TRIAL_TOKEN_LIMIT`, a budget stop that is still graded. When the cap is set, a trial starts only if every applicable ceiling still has room for a whole trial, so a ceiling is exceeded by at most the last request of a trial.
- Unscheduled trials are listed under `batch.notRun`, and the report is marked incomplete.
- `--resume <run>` continues a single-run batch only when the fingerprint is unchanged. It reruns missing and infrastructure-failed trials; each replacement names the trial it supersedes, which stays on disk.
- The CLI refuses provider requests unless `batch.maxTotalTokens` or `batch.maxTotalTokensPerModel` is set.

## Continuous trajectories

A trajectory is one trial with a shared workspace and agent session. Stage records retain cycle-level execution, public checks, snapshots, private grades, and active requirements. Stage budgets and the trajectory budget are enforced separately.

Public checkers run against disposable copies, so they cannot alter the archived submission. Candidate timeout is a task outcome; grader timeout or protocol failure is an evaluator error. A trial whose execution ended with a budget stop, a timeout, or another model-side failure (`failureKind` `budget` or `model`) is graded on its final state, and its verdict counts toward pass rates. Only infrastructure failures are skipped and excluded; `--resume` reruns them.
