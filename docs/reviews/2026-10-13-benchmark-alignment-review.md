# Benchmark Alignment Review

Date: 2026-10-13. Scope: readiness of the harness and task set for the first single-model evaluation pilot. Agent- and harness-comparison research is out of scope.

## Method

The project was compared with established evaluation practice:

- The Agentic Benchmark Checklist (ABC; Zhu et al., NeurIPS 2025 Datasets and Benchmarks), which covers task validity (T), outcome validity (O), and reporting (R).
- Inspect AI (repeated epochs, score reducers, container sandboxes, re-scoring from logs and external score files).
- Harbor / Terminal-Bench 2.0 (task directory format, agent never sees tests or solution, oracle solution, canary strings).
- SWE-bench (FAIL_TO_PASS plus PASS_TO_PASS resolution, per-instance container images).
- Aider polyglot (first-attempt and post-feedback pass rates, malformed-edit rate reported separately).
- τ-bench pass^k, the HAL leaderboard (cost-aware reporting, model versus scaffold), and Miller, "Adding Error Bars to Evals" (clustered standard errors, paired model comparisons, power analysis).

Each finding below was checked against the code, and where marked "verified", reproduced with an offline probe that used an injected runner and made no model API calls.

## Environment verification

- Conda environment `agenteval` from `environment.yml`: Python 3.13.15, Node.js 22.23.2 (22.23.3 is not on conda-forge).
- `npm ci` and `npm run check` pass. `npm test`: 43 of 44 pass; the failure is eng-004, whose baseline repository is missing.
- `--validate-only` passes for 5 of 8 example plans; the three eng-004 plans fail with `PACKAGE_BASELINE_COMMIT_MISMATCH`.
- Every grader self-calibration passes under Python 3.13.15 except eng-004 (missing baseline). Logs are in each package's `logs/self-calibration-<version>.log`. The eng-005 replay calibration passes and its log is bound to the current manifest digest.
- The `tsx` CLI opens an IPC socket that the Claude Bash sandbox refuses (`listen EPERM`). The npm scripts now use `node --import tsx`, which is equivalent and needs no socket.

Fixed during the review:

- The eng-005 reference READMEs had been reduced to a one-line description, so both references failed the S5 public check and the private `docs.usage` check. They now document the final contract.
- A doc-evidence test asserted the emoji at offset 1 of `alpha🙂…`. The tool was correct; the test now checks offsets 5 and 6, which also catches UTF-16 indexing errors.

## What already matches practice

- Public/private projection with hashed manifests and a schema-validated grader protocol (ABC T.5 intent, Harbor isolation model).
- Reference solutions and targeted mutants per task (ABC T.9, O.d.1); eng-005 replays two references three times.
- Regression requirements analogous to SWE-bench PASS_TO_PASS (eng-004 index compatibility, eng-005 retention metrics).
- Pending, unscored, resource-limit, and evaluator-error states kept distinct; unknown usage is not zero.
- Append-only re-scoring against a frozen snapshot (Inspect `score()` analogue).
- Trivial answers fail (verified): empty output, `{}`, and a fenced `{}` score 0 on rsn-001, rsn-002, and tool-001, so the τ-bench "empty response counts as success" defect does not occur.

## Findings

| ID | Priority | Finding | ABC / practice |
| --- | --- | --- | --- |
| F1 | P0 | Candidate commands can read evaluator-side ground truth | T.5, T.4 |
| F2 | P0 | A candidate `git commit` turns the trial into an evaluator error | O.g.1 |
| F3 | P0 | rsn-002 can never pass | O.c, R.11 |
| F4 | P0 | Budgets are infeasible and limits are conflated | T.10 |
| F5 | P0 | No repeated trials or uncertainty | R.10 |
| F6 | P1 | Format failures are indistinguishable from wrong answers | O.h.1 |
| F7 | P1 | Reports aggregate unlike tasks | SPEC rule 7 |
| F8 | P1 | The evaluated condition is under-specified | R.6, T.1 |
| F9 | — | Withdrawn: tool-policy violations are graded correctly | O.g |
| F10 | P1 | Too few independent tasks for model comparison | R.5, R.10 |
| F11 | P2 | No contamination markers | R.3 |
| F12 | P2 | Trivial-agent baselines are not recorded | R.13 |
| F13 | — | Decided: stay on Pi 0.87.1 | T.1, T.6 |
| F14 | P0 | Provider failures are not contained at batch level | T.2, T.3 |
| F15 | P1 | Provider request mapping is unverified per model | T.1 |

### F1. Candidate commands can read evaluator-side ground truth (verified)

`execute_command` runs any executable with host permissions. Path containment applies only to the file tools. A probe read `task-library/calibration/eng-001-import-validator/private/oracle.json` through `execute_command`. Candidate programs started by graders (eng-001, eng-004, eng-005) and public checkers are also unconfined host processes. This breaks ABC T.5 (isolate agents from ground truth) and makes runs depend on host state (T.4, T.6). Every established harness reviewed here runs the candidate in a container.

Recommendation: Docker is not installed and requires an administrator, but `bwrap` works for this user (verified). Run `execute_command` and every candidate process launched by graders and checkers in a bubblewrap sandbox. Bind the workspace read-write and the toolchain read-only, and give it no `/home`, no network, and a private `/tmp`. Keep the evaluator itself outside the sandbox.

### F2. A candidate `git commit` turns the trial into an evaluator error (verified)

Repository cases use a detached worktree that shares the baseline repository. If the candidate commits, as coding agents commonly do, `collectPatch` and cleanup both raise `WORKSPACE_REPLACED`, so the trial is recorded as an evaluator error with a cleanup failure instead of being graded. A worktree also lets the candidate write objects and refs into the shared baseline repository.

Recommendation: give each trial its own clone of the pinned commit, and collect the submission as the diff from the pinned commit to the final working tree, whatever HEAD points to.

### F3. rsn-002 can never pass

The grader reports `unscored` while its two non-critical human-review checks are missing. `runTaskGrader` then maps the whole trial to `unscored` even when every critical check passes (`tests/m2-package-graders.test.ts` asserts this), and no tool exists to record a human score. The task can therefore only fail or stay unscored.

Recommendation: derive the objective verdict from critical checks alone, report human-review completeness separately, and add an append-only import of human scores as a score run (analogous to Inspect's external-score scorer).

### F4. Budgets are infeasible and limits are conflated

- `examples/eng-001.eval.json` allows 512 output tokens per request. The reference implementation is 8–10 KB (about 2.5–3k tokens), and `write_file` must carry the whole file in one call, so a correct solution cannot be written in one request.
- A tool result longer than `maxOutputChars` sets `TOOL_OUTPUT_LIMIT` and ends the run as `budget_exceeded`, which skips grading. With the eng-001 value of 8192, reading any file larger than 8 KB ends the trial, even though `read_file` allows 100 KB.

Recommendation: add a separate per-result tool-output limit and set all budgets from pilot runs. ABC T.10 asks that pilot outliers be inspected for exactly this kind of implementation bug.

### F5. No repeated trials or uncertainty

Each plan runs one trial per model and case. Temperature 0 does not make providers deterministic, and reruns cannot be summarised.

Recommendation: add a plan-level repetition count, and report per task pass^1, pass@k, and pass^k (τ-bench), per-check pass rates, and confidence intervals. Compare models with paired differences, using standard errors clustered by task family as Miller recommends. Report run-to-run disagreement alongside accuracy.

### F6. Format failures are indistinguishable from wrong answers (verified)

A correct rsn-001 answer wrapped in a Markdown fence, or preceded by one sentence, is scored `failed`, the same as a wrong answer. The strict format is stated in the instructions, so strict scoring is legitimate (ABC O.h.1). The problem is that reports cannot separate instruction-following failures from reasoning failures, and the noise-floor literature finds malformed output can be a large share of failures on some endpoints.

Recommendation: keep strict scoring, have answer-graded tasks emit an explicit parse status, and report the malformed-output share per model, as Aider reports its well-formed-edit rate.

### F7. Reports aggregate unlike tasks

`summarize` and `report.md` compute one objective pass rate across all records, mixing engineering, reasoning, and tool tasks. That contradicts SPEC rule 7.

Recommendation: produce model × task × requirement tables and drop the cross-task rate.

### F8. The evaluated condition is under-specified

- `thinkingLevel` is fixed to `off`, temperature to 0, and retries to 0.
- Every custom provider model is declared with the same metadata: no reasoning, a 128k context window, 8192 maximum tokens, and zero price. As a result `costUsd` is always null.
- `experiment.json` records only the Node.js version.

Recommendation: declare per-model metadata and prices, make thinking an explicit plan condition, and fingerprint the git commit, Python and Pi versions, and the tool-profile definition. ABC R.6 asks reports to say whether they measure the model, the framework, or both; here it is always the pair model + Pi harness.

### F9. Withdrawn: tool-policy violations are graded correctly (verified)

The first draft inferred from `src/harness/pi.ts` that calling a tool outside the profile ends the run. Reading Pi 0.87.1 (`agent-loop.js`, `prepareToolCall`) showed otherwise: an unknown tool gets an immediate "not found" error result, and `beforeToolCall` is never called for it. An offline probe confirmed this. A doc-evidence run that called `write_file` completed, recorded one attempt and one interception, and was graded, and tool-001 Q4b correctly failed. The unknown-tool branch in the harness's `beforeToolCall` is unreachable dead code.

### F10. Too few independent tasks for model comparison

Six runnable task families exist, eng-004 is blocked, and eng-002, eng-003, and vis-001 have no manifests. With binary per-task outcomes, power is very low even with repeats.

Recommendation: rsn-001 (`verify.py`), rsn-002 (fixed formula with sampled parameters), and tool-001 (`make_snapshot.py`) already have verifiers or generators, so generate many verified instances per family to give the reasoning and tool dimensions statistical weight. Treat engineering tasks as per-check case studies until more exist.

### F11. No contamination markers

Task text and private fixtures contain no canary string.

Recommendation: add a per-family canary GUID (as Harbor and BIG-bench do), and keep holdout instances out of any public repository.

### F12. Trivial-agent baselines are not recorded

The probes above show that trivial answers fail, but this is not part of calibration.

Recommendation: add a null-agent run to every package calibration and to the pilot report.

### F13. Decided: stay on Pi 0.87.1

Pi 1.2.0 (published 2026-10-12) is available, but model evaluation needs only the basic agent loop, so the project stays on 0.87.1. The version must still be recorded in the run fingerprint (F8).

### F14. Provider failures are not contained at batch level

Requests use `maxRetries: 0`, so one transient 429 or 5xx response turns a trial into an infrastructure failure. An expired key or exhausted balance makes every later trial fail the same way while the batch keeps going. Plans have per-trial budgets but no batch-level token or cost ceiling, and an interrupted batch cannot resume. ABC T.2 and T.3 ask for rate-limit handling and for evaluation to stop visibly when an API becomes unavailable.

Recommendation:
- Add a bounded retry for retryable errors that arrive before any output, recorded per request.
- Stop the batch on authentication or balance errors, or after a run of consecutive infrastructure failures, and mark the remaining trials as not run rather than failed.
- Enforce a batch token ceiling, and a cost ceiling where prices are known.
- Support resuming a batch while keeping the same fingerprint.

### F15. Provider request mapping is unverified per model

Pi selects request fields by endpoint:
- DeepSeek is detected by base URL. It gets `max_tokens`, DeepSeek reasoning handling, and streamed usage.
- Other OpenAI-compatible endpoints, including AliPlan's compatible mode, get `max_completion_tokens`.

Custom models are declared with `reasoning: false` and a 128k context window. Pi uses the declared window to clamp `max_tokens`, so a wrong window either cuts output or allows overflow. Nothing in the harness handles context overflow in long eng-005 sessions.

Recommendation: before any scored run, check each pilot model for four things:
- usage is reported and non-zero;
- the output cap is enforced;
- the model's default thinking behaviour with thinking off;
- error classification for an invalid key.

## Recommended order

1. **Before any paid request:** F1, F2, F3, F4 (limit separation), F8 (condition fingerprint), and F14 (batch containment).
2. **Then:** a repetition count and per-task reporting (F5, F7), parse status (F6), and per-model provider verification (F15). Then a small pilot to set budgets.
3. **After the pilot:** instance generators for reasoning and tool families (F10), canaries (F11), null-agent baselines (F12), the eng-004 baseline rebuild, and conversion of the manifest-less packages.

## Sources

- [Establishing Best Practices for Building Rigorous Agentic Benchmarks (ABC)](https://arxiv.org/abs/2507.02825)
- [Inspect AI documentation](https://inspect.aisi.org.uk/), [sandboxing](https://inspect.aisi.org.uk/sandboxing.html), [scorer reference](https://inspect.aisi.org.uk/reference/inspect_ai.scorer.html)
- [Harbor task structure](https://www.harborframework.com/docs/tasks)
- [SWE-bench harness](https://www.swebench.com/SWE-bench/api/harness/)
- [Aider polyglot benchmark](https://aider.chat/2024/12/21/polyglot.html), [Aider leaderboards](https://aider.chat/docs/leaderboards/)
- [τ-bench](https://arxiv.org/abs/2406.12045)
- [Holistic Agent Leaderboard](https://arxiv.org/abs/2510.11977), [Towards a Science of AI Agent Reliability](https://arxiv.org/abs/2602.16666)
- [Adding Error Bars to Evals](https://arxiv.org/abs/2411.00640)
- [Noise Floor Audit for Agent Benchmarks](https://arxiv.org/abs/2608.22331)
