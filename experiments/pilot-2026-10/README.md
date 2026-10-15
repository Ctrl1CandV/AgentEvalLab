# Pilot 2026-10

The first live run (PLAN-004 phase 4). Its purpose is to calibrate per-task budgets and confirm that the harness, providers, graders, and reports behave as expected under real model traffic. It is not a model comparison: three trials per task cannot rank models.

**Status (2026-10-15):** reasoning and tool batches complete; the engineering batch stopped after one trial per model at the token budget. See [the pilot results](../../docs/reviews/2026-10-15-pilot-results.md).

## Conditions

| Model | Report label | Endpoint | Thinking | Temperature | Notes |
| --- | --- | --- | --- | --- | --- |
| `supergpt:gpt-6-luna` | `supergpt:gpt-6-luna-medium` | SuperGPT relay, OpenAI protocol | `medium` (sent explicitly; also the model's default) | 0 | The relay ignores output-token limits; the harness enforces the cap from reported usage. |
| `supercn:glm-5.3-flash` | `supercn:glm-5.3-flash-default` | SuperCN relay, Anthropic protocol | `provider-default` (thinking always on) | 0 | Thinking cannot be disabled and has no level to set. The relay does not report reasoning tokens separately. |

Thinking levels are not forced to match: each provider controls thinking differently, and GLM-5.3-Flash has no level to set. Each model runs at a stated level instead, and reports append that level to the model label, as public leaderboards do (user decision, 2026-10-14). Temperature is 0 for both. Both conditions are recorded in `experiment.json`. Both models passed the live provider checks of 2026-10-14, including luna reasoning at `medium` with tools attached; see `docs/reviews/2026-10-14-provider-check.md`.

## Plans

Every plan uses 3 repetitions, 2 provider retries per request, a stop after 3 consecutive infrastructure failures, and candidate sandboxing.

| Plan | Cases | Timeout | Turns / model calls | Tool calls | Output tokens per call | Batch token ceiling |
| --- | --- | --- | --- | --- | --- | --- |
| `reasoning.eval.json` | rsn001-schedule, rsn002-derivation (read-only) | 10 min | 8 / 8 | 8 | 32,768 | 500,000 |
| `tool.eval.json` | tool001-evidence (doc-evidence, read-only) | 15 min | 30 / 30 | 60 | 32,768 | 2,000,000 |
| `engineering.eval.json` | eng001-import-validator | 30 min | 40 / 40 | 60 | 32,768 | 3,500,000 |

The ceilings total 6,000,000 tokens, about 3,000,000 per model. A ceiling stops scheduling new trials; it does not cut off a running trial. The budgets are deliberately generous, because the pilot measures what tasks need.

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
