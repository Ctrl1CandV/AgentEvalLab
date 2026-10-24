# v2 Run Protocol

The conditions under which a number is produced. A result is meaningful only together with its protocol, so every field below is recorded with the result (CODE §3, run metadata), and results under different protocols are never mixed in one row.

## 1. Model pool and labels

Unchanged user decisions:

- **Thinking level:** the middle level, the vendor's "medium" where named. The label carries the level: `deepseek:deepseek-flash-high`, `aliplan:qwen3.8-flash-default`.
- **Temperature:** 0 for every model.
- **Snapshots:** record the provider, the model id, and whatever snapshot or version information the provider returns. An alias alone does not prove the same snapshot.

The pool by phase:

- **Dev pool:** deepseek-flash plus about two references from qwen3.8-flash, mimo-v2.6-flash, glm-5.3 / glm-5.3-flash and step-5-preview. At most one model from the airy.work relay; no pro models; one repetition.
- **Validation and holdout pool:** the dev pool plus at least one clearly stronger reference and one clearly weaker one, so that the scale is shown to span a range. This needs the user's approval and a cost plan (PLAN-007 decision D1).

## 2. Budget tracks

| Track | Use | Rule |
| --- | --- | --- |
| **Fixed budget** (primary) | every headline number | One budget per task family, frozen before validation, identical for every model, stated to the model at the start, with reminders at 50%, 75% and 90%. The best deliverable within the budget is the result. Self-caused stops count by the frozen rules. |
| **Budget curve** (analysis) | to calibrate and to show where quality plateaus | Predeclared levels (B/2, B, 2B; 4B only where the curve is still rising), on a small fixed subset of dev tasks |
| **No unlimited track** | — | Budgets are not raised after seeing a model fail |

**Calibrating B.** On the dev split, run the curve for the strongest dev model and one reference. Choose the smallest B where going from B to 2B raises the family primary by less than 0.05, or by less than its interval half-width. Record the curve. Then freeze B for validation and holdout.

Open-ended families use their whole budget by design. Their B is the budget at which the improvement per doubling falls below the threshold.

## 3. Token accounting

- **Unchanged user decision:** budgets count fixed token units, with cached input counted in full, and no prices.
- **Reported alongside:** input, cache read, cache write, output and reasoning tokens where the provider reports them; model calls; tool calls; wall time; tool CPU time where the family measures it.
- A provider that hides reasoning tokens is reported as "not reported", never as 0.
- Agentic work spends 90–98% of counted tokens on cache reads (T2 and E3, 2026-10-23). Budgets therefore come from the curve, not from estimates of output length.

## 4. Context policy

Each family declares its policy:

| Policy | Used by |
| --- | --- |
| `single` | one session per task |
| `per-stage` | trajectories where the project carries the earlier work |
| `continuous` | one session across stages |

E3 per-stage results measure cross-stage code evolution and are not comparable with continuous results.

## 5. Tools and limits

- **Tool profile per family.** Answer-only families (AR answer-only, R3) get no tools. Agentic and engineering families get the workspace profile with command execution.
- **Two protocols where tools change the construct.** AR runs answer-only (reasoning) and, as a separate protocol, with code execution (program synthesis). They are never averaged.
- **Command limits** (`commandLimits`, since b46c859) are stated in the tool description. They are 10 minutes for AE and ER, and the default elsewhere.
- **Per-response caps:** 131,072 tokens and 524,288 characters, unchanged. A family that legitimately needs longer single responses declares it in its card.
- **Runtime mounts.** Read-only dependency directories for repository tasks (ER, later LR) are declared by the package and mounted into the sandbox (CODE §4).

## 6. Repetitions

| Split | Repetitions |
| --- | --- |
| dev | one |
| validation | one per task, plus three on a predeclared 20% subset per family to estimate within-task variance |
| holdout | three for the models compared in the release conclusions, one for the others |

More tasks are preferred over more repetitions.

## 7. Failures and coverage

| Outcome | Treatment |
| --- | --- |
| Infrastructure failure: provider unavailable, harness error, grader error, sandbox failure | Retried by the batch policy. If it persists, the trial is `unscored` with its reason and counted in coverage. Never a zero, never silently dropped. |
| Self-caused stop: budget, timeout, output limit, malformed final answer, loop | Scored by the frozen rules: the deliverable at the stop is graded. |
| Provider content refusal (`content_filter`, as with mimo's "high risk" in T2) | `unscored`, with the reason `provider_refusal`; reported per model |
| A harness or grader defect found later | Fixed with a version bump. Every affected trial of every model is re-graded or re-run; the earlier numbers keep their version. |

A family row is shown only when coverage is at least 90% of planned tasks per model; otherwise it is marked incomplete.

## 8. Run metadata (recorded per run)

- task package id, version and manifest hash;
- grader version;
- code commit;
- suite file and protocol track;
- split;
- models with labels and snapshot information;
- thinking levels and temperature;
- tool profile;
- command limits;
- budgets and context policy;
- retry policy;
- random seeds (trial order, environment seeds);
- machine (CPU model, core count);
- start and end times.

## 9. Machine and timing

- Timing-sensitive families measure **CPU time** of the candidate process, not wall time (AE since 0.1.0, through a read-only wrapper), and judge one submission at a time under a lock.
- A family that times anything declares its noise test in its card: the same submission judged twice, with the machine quiet and loaded. The family must show identical verdicts and a rank change below a declared tolerance.

## 10. Cost governance

- Before every paid run: the worst-case tokens from the preflight, and an expected figure from the budget curve.
- Each phase of PLAN-007 has a token envelope. Exceeding it needs the user's approval.
- Runs longer than about 1.5 hours are launched by the user from a WSL terminal:

  ```
  PATH=/home/claude-dev/.local/share/conda/envs/agenteval/bin:$PATH nohup npm run suite -- --resume <run> >> <run>/launch.log 2>&1 &
  ```

  The suite refuses a resume under another Node major version. The implementer watches it with a background watcher.
- No default 300–500M-token round. Breadth (more independent tasks) comes before length (bigger budgets).
