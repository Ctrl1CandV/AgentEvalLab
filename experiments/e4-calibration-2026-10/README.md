# E4 Calibration 2026-10

The first run of the E4 command-line family (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). Task 0.1.0 has four items:

- `perf`: make a slow report fast without changing its output;
- `migrate`: write and run a SQLite schema migration;
- `bisect`: find and undo a regression in a Git history;
- `build`: repair a C project's build and bugs.

The calibration models solve each item twice, at their middle thinking levels and temperature 0.

Each trial gets 500,000 tokens, 60 responses, 100 tool calls and 30 minutes, stated to the model, and four trials run at once. The grader runs the hidden checks in the sandbox; the score is the fraction of checks passed.

```bash
npm run harness -- --plan experiments/e4-calibration-2026-10/calibration.eval.json
```

The deepseek API key was rejected on 2026-10-19. `calibration-without-deepseek.eval.json` runs the same plan on the other three models in the meantime. deepseek follows later under the same task version and budget.

## Result (run `fbdcfb07`, without deepseek, 24 trials)

E4 0.1.0 is saturated. gpt-6-luna, glm-5.3 and step-5-preview passed every check of every item in both repetitions. They differed only in cost: luna needed 16,000–50,000 tokens per trial, and glm and step 100,000–500,000, twice reaching the 500,000-token limit just as they finished. The items stay as easy anchors and an end-to-end check of the sandbox. Harder command-line work needs longer, compound tasks; see `docs/reviews/2026-10-19-task-set-v2-calibration.md`.

A new deepseek key works from 2026-10-19. The `*-deepseek.eval.json` plans add deepseek under the same conditions.

## Compound items (task 0.2.0, 2026-10-20)

`compound.eval.json` runs the three compound items, `stockroom`, `pipeline` and `recover`, twice on five models, qwen3.8-flash at its default thinking included. Each trial gets 800,000 tokens, 100 responses, 150 tool calls and 60 minutes, stated to the model. The null-agent baseline scores 0 on every item.

```bash
npm run harness -- --plan experiments/e4-calibration-2026-10/compound.eval.json
```

Run `c95f78c8`: 20 of 30 trials, before the airy.work relays ran out of balance (at the time this stopped every model). Every graded trial of every model passed every check of `stockroom`, `pipeline` and `recover`. Several stopped at the 800,000-token budget after they had already repaired everything. gpt-6-luna needed 18 responses for the six stockroom faults. The compound items are saturated as well.

## codec (task 0.3.0, 2026-10-20)

`codec.eval.json` runs the reverse-engineering item twice on seven models: the five calibration models and the two MiMo V2.6 models at their default thinking. Budgets are those of the compound run, except that a single response may hold 131,072 output tokens, as in R3 and E2 (clamped to each model's own limit). From now on only the task budget, not one response, should stop a model.

```bash
npm run harness -- --plan experiments/e4-calibration-2026-10/codec.eval.json
```

Run `627cdf83` (task 0.3.0, codec):

| Model | Trials | Checks passed |
| --- | --- | --- |
| deepseek-flash | 1 (the other: no balance) | 11/11 |
| qwen3.8-flash | 2 | 11/11, 11/11 |
| mimo-v2.6-flash | 2 | 11/11, 8/11 (missed `timestamps`, `multi-day`, `restore` at the token budget) |
| mimo-v2.6-pro | 2 | 0/11, 0/11: stopped by the 32,768-character text limit of a single response |
| glm-5.3, step-5-preview, gpt-6-luna | — | not run: the airy.work relay had no balance |

Recovering a format from bytecode does not separate the strong models either: deepseek, qwen and mimo-flash decoded every hidden group in 19–34 responses. mimo-v2.6-pro writes its reasoning out as text as well as in its thinking, so the per-response text limit stopped it in both trials. That limit is a safety guard, not the task budget, so plans from now on allow 524,288 characters of text per response.

## speedup (task 0.4.0, 2026-10-20)

`speedup.eval.json` runs the speedup item twice on seven models, with 2,000,000 tokens per trial and artifact limits of 128 MiB per file and 512 MiB per trial. The first launch kept the codec run's 2 MiB file limit and was stopped: both of its trials left large test days in the workspace, which could then not be exported for grading. A single response may hold 524,288 characters of text, and the grader has 15 minutes, since the timing runs take up to three minutes.

```bash
npm run harness -- --plan experiments/e4-calibration-2026-10/speedup.eval.json
```

Run `9b2dbac7` (task 0.4.0, speedup): 10 of 14 trials; the relay models had no balance. Every trial used its whole 2,000,000-token budget, optimising until stopped.

Under 0.4.0's ladder (16/6/3/1.5×), deepseek, qwen and mimo-pro passed every check in one or both trials, so 0.4.1 moved the ladder. A 0.4.0 trial cannot be regraded under 0.4.1, whose prompt states other thresholds. So each delivered `analyze.py` was measured offline on 0.4.1's hidden days (reference 0.65 s, one core, best of three), which shows where the trials would land. This is a calibration measurement, not a result:

| Model | Trial 1 | Trial 2 |
| --- | --- | --- |
| deepseek-flash | 0.64×, all outputs right: 7/7 | 0.69×: 7/7 |
| mimo-v2.6-pro | 0.99×: 6/7 | 1.00×: 6/7 |
| mimo-v2.6-flash | 0.94×: 6/7 | wrong output on every day: 0/7 |
| qwen3.8-flash | 1.26×: 5/7 | wrong output on every day: 0/7 |

A 0.4.1 run is still needed for results.

## speedup 0.4.1, formal run (2026-10-21)

The first suite run (PLAN-006 Part A), `runs/suites/20261021-120039-dev-fe3b`, at commit `53c833c`, with deepseek-flash and qwen3.8-flash, one trial each, 2,000,000 tokens per trial:

| Model | Checks | Time against the reference | Tokens |
| --- | --- | --- | ---: |
| deepseek-flash | 0/7 | 3.1×, all outputs right | 2.05M (budget stop) |
| qwen3.8-flash | 4/7: outputs and `speed-3` | between 1.5× and 3× | 2.04M (budget stop) |

deepseek's program is correct but took 2.5 seconds against the reference's 0.8, measured again on an idle machine. The trial ended at its budget while it was still tuning and difference-testing. In 0.4.0 its two programs ran at 0.64× and 0.69×. Under 0.4.1 a correct program just above 3× earned nothing, a cliff that 0.5.0 removes with a `speed-8` rung (see the package's `calibration.md`).

## E4 0.5.0: speedup and compress (2026-10-21)

`speedup-0.5.eval.json` (2,000,000 tokens per trial) and `compress.eval.json` (4,000,000 tokens per trial since 2026-10-22, below) run the two scored items. The E4 score is their mean. The grader has 20 minutes per trial, because the compress check makes up to twelve candidate runs of up to 60 seconds after about a minute of anchors. (The first B1 round used `terminal.eval.json`, both items at 2,000,000 tokens, since removed.)

Run `runs/suites/20261021-123806-dev-d275` (dev suite, commit `4c8c616`), speedup and compress once per model:

| Model | speedup (8 checks) | compress (6 checks) | Tokens |
| --- | --- | --- | ---: |
| deepseek-flash | 7/8 (all but `speed-0.75`) | not run: the suite's per-model ceiling had no room for the speedup trial's overshoot (fixed in `6ee49fe`); run separately | 2.04M |
| qwen3.8-flash | 8/8 | 0/6: `packlog.py` left half-written; the trial ended with "Now let me write the complete implementation properly." | 2.75M |
| mimo-v2.6-flash | 7/8 | 0/6: correct round trips, but larger than LZMA preset 9e (about gzip's size) | 4.10M |

The compress checks were rerun by hand on both delivered programs and gave the same verdicts. Neither model's result comes from the check.

deepseek's compress trial ran on 2026-10-22 (`runs/suites/20261022-040520-dev-7f6a`). It scored 0/6: at the budget its `packlog.py` was mid-edit, a range coder that raises a TypeError. All three models ended without a working compressor after 30–38 requests of about 60,000 tokens each, so compress now has 4,000,000 tokens per trial (see the package's `calibration.md`).
