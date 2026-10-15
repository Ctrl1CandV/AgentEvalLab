# Pilot 2026-10

The first live run (PLAN-004 phase 4). Its purpose is to calibrate per-task budgets and confirm that the harness, providers, graders, and reports behave as expected under real model traffic. It is not a model comparison: three trials per task cannot rank models.

**Status (2026-10-15):** the first round with glm-5.3-flash is recorded in [the pilot results](../../docs/reviews/2026-10-15-pilot-results.md). Its engineering batch stopped after one trial per model at the token budget. The pilot now continues with glm-5.3 in place of glm-5.3-flash (user decision), under per-trial and per-model token caps.

## Conditions

| Model | Report label | Endpoint | Thinking | Temperature | Notes |
| --- | --- | --- | --- | --- | --- |
| `supergpt:gpt-6-luna` | `supergpt:gpt-6-luna-medium` | SuperGPT relay, OpenAI protocol | `medium` (sent explicitly; also the model's default) | 0 | The relay ignores output-token limits; the harness enforces the cap from reported usage. |
| `supercn:glm-5.3` | `supercn:glm-5.3-max` | SuperCN relay, Anthropic protocol | `max` (sent explicitly as adaptive thinking with effort `max`; also the model's default) | 0 | Thinking is always on; effort is `low`, `high` or `max`. The relay does not report reasoning tokens; reports count thinking characters instead. |

Thinking levels are not forced to match: each provider controls thinking differently. Each model runs at its vendor's default level, sent explicitly so the label states what the provider received, and reports append that level to the model label, as public leaderboards do (user decisions, 2026-10-14 and 2026-10-15). Temperature is 0 for both. Both conditions are recorded in `experiment.json`. Both models passed live provider checks, including reasoning with tools attached; see `docs/reviews/2026-10-14-provider-check.md`.

## Plans

Every plan uses 3 repetitions, 2 provider retries per request, a stop after 3 consecutive infrastructure failures, and candidate sandboxing.

| Plan | Cases | Timeout | Turns / model calls | Tool calls | Output tokens per call | Tokens per trial | Tokens per model |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `reasoning.eval.json` | rsn001-schedule, rsn002-derivation (read-only) | 10 min | 8 / 8 | 8 | 32,768 | 100,000 | 400,000 |
| `tool.eval.json` | tool001-evidence (doc-evidence, read-only) | 15 min | 30 / 30 | 60 | 32,768 | 100,000 | 300,000 |
| `engineering.eval.json` | eng001-import-validator | 30 min | 40 / 40 | 60 | 32,768 | 1,000,000 | 2,300,000 |

Tokens are fixed units: every reported token counts once, cached input included, and no prices are used. The per-model ceilings total 3,000,000 tokens per model, the budget the user approved. A trial starts only when its model's ceiling has room for a whole trial, so a ceiling is exceeded by at most one request, and one model reaching its ceiling does not stop the other. A trial over its per-trial cap ends with `TRIAL_TOKEN_LIMIT`, a budget stop that is graded. The other budgets stay generous, because the pilot measures what tasks need; the per-trial caps are far above what luna and glm-5.3-flash needed on reasoning and tool tasks, but glm-5.3-flash's one complete engineering trial (2.7M tokens) would have hit the engineering cap.

The pilot excludes eng-005, whose five-stage trajectory needs its own cost estimate from these results, and eng-004, whose baseline must be rebuilt first.

## Running

From a clean, committed worktree (live runs refuse a dirty tree):

```bash
npm run harness -- --plan experiments/pilot-2026-10/reasoning.eval.json
npm run harness -- --plan experiments/pilot-2026-10/tool.eval.json
npm run harness -- --plan experiments/pilot-2026-10/engineering.eval.json
```

If a batch stops early, check `report.json` → `batch.stopReason` and continue with `--resume runs/<run-id>`. Resume reruns only missing and infrastructure-failed trials, and only for an unchanged fingerprint.

Trivial-agent baselines need no API: `node --import tsx scripts/null-agent-baseline.ts experiments/pilot-2026-10/<plan>.eval.json`. On 2026-10-14 all three plans gave 0 passes for both models, so doing nothing scores nothing.

## Reading the results

Each run directory contains `experiment.json` (plan, fingerprint, condition, schedule), per-trial records, and `report.json` / `report.md`. Before trusting any number:

1. **Check `batch`.** Confirm there was no stop reason and no `notRun` entries, and note any unknown usage.
2. **Check "Usage by task".** Look at median and maximum calls, tokens, and duration, and at the execution outcomes. Budget stops (`MODEL_CALL_LIMIT`, `TOOL_LIMIT`, `OUTPUT_TOKEN_LIMIT`, `TIMEOUT`) mean a budget bound; `PROVIDER_*` or `CONTEXT_LIMIT` mean a provider problem.
3. **Inspect outliers (ABC T.10).** For any failed trial, read `tool-trace.jsonl` and the grader evidence under `score-runs/` to see whether the harness or grader caused it.
4. **Check malformed answers** before reading pass rates on rsn-001, rsn-002, and tool-001.

## Decisions the pilot feeds

- **Per-task budgets for the first frozen set:** roughly the maximum observed usage plus headroom, keeping budget stops rare but possible.
- **Which thinking level each model uses in the frozen comparison.** The pilot shows what luna `medium` and GLM's always-on thinking cost per task.
- **The eng-005 trajectory cost estimate.**
