# T1 Calibration 2026-10

The difficulty calibration of the T1 evidence-recovery family (PLAN-005 WP5, [Task Set v2](../../docs/design/TASK_SET_V2.md)). It runs every item once on the four calibration models, at their middle thinking levels and temperature 0.

`task-library/calibration/t1-evidence-recovery` 0.1.0 has 16 generated snapshots, 4 per level:

| Level | Files | Characters | Questions |
| --- | --- | --- | --- |
| L1 | 16 | ~51K | lockfile, log lookup, config precedence, recovery, refuse a write |
| L2 | 21 | ~148K | adds a log count and an absent fact |
| L3 | 35 | ~258K | adds a two-hop incident chain, retired `.bak` distractors, and a secret request |
| L4 | 52 | ~393K | two log counts, two config questions, and a three-hop chain |

Tools are the doc-evidence profile: 400-character pages, line search with at most 50 matches, and list. Answers count only when the trace shows the supporting lines. Searching is far cheaper than paging, so the stated budget rewards an efficient strategy.

## Budget

Each trial gets 300,000 tokens, 60 responses, 80 tool calls and 30 minutes, stated to the model. These are first-run values: tool use grows the context with every call, and this run measures how much each level needs. The plan has a per-model ceiling of 2.5M tokens as a spending fuse.

```bash
npm run harness -- --plan experiments/t1-calibration-2026-10/calibration.eval.json
```

## Runs

| Run | Plan | Levels used |
| --- | --- | --- |
| `e239c8f3` | `calibration.eval.json`, `maxFiles` 50 | L1 to L3. Every L4 trial ran, then failed artifact export (`ARTIFACT_FILE_LIMIT`), so the run was stopped. |
| L4 rerun | `l4-rerun.eval.json`, `maxFiles` 500 | L4 |

The first plan copied artifact limits of 50 files from the R3 plan, below the 53 files an L4 snapshot projects. This was a plan error, not a model or grader error. Preflight now refuses limits that cannot hold a trial's own starting files (`PLAN_ARTIFACT_LIMIT_TOO_LOW`).

## Hard levels (task 0.2.0)

`hard-levels.eval.json` runs L4 and L5 of task 0.2.0, the levels that separate the models, on the four calibration models. L5 snapshots hold about 740,000 characters and 12 questions, so each trial gets 500,000 tokens, 100 responses and 120 tool calls, stated to the model. It waits for the deepseek key, because deepseek is the model that L5 must separate.

```bash
npm run harness -- --plan experiments/t1-calibration-2026-10/hard-levels.eval.json
```

The deepseek API key was rejected on 2026-10-19. `*-without-deepseek.eval.json` runs the same plan on the other three models in the meantime. deepseek follows later under the same task version and budget, and the item analysis combines the runs.

## Result (run `430a8c25`, task 0.2.0, grader 1.3.1, without deepseek)

| Level | glm-5.3 | step-5-preview | gpt-6-luna |
| --- | ---: | ---: | ---: |
| L4 | 88% | 98% | 95% |
| L5 | 78% | 78% | 85% |

At L5 no item was solved by every model, and one by none. The failures were audited:

- miscounted lock-file filters;
- included shared files ignored;
- a shared value misread;
- `secrets/` listed or read;
- format slips.

One grader defect was fixed in grader 1.3.1: it rejected an incident answer that went through the only change file. Median tokens per trial at L5: luna 114,000, glm 159,000, step 257,000; none reached the 500,000 limit.

A new deepseek key works from 2026-10-19. The `*-deepseek.eval.json` plans add deepseek under the same conditions.

## L5 and L6 (task 0.3.0, 2026-10-20)

`l5-l6.eval.json` runs L5 and L6 on five models, qwen3.8-flash at its default thinking included. L6 snapshots are about twice the size of L5's, with 15 questions, so each trial gets 800,000 tokens, 120 responses, 150 tool calls and 60 minutes, stated to the model.

```bash
npm run harness -- --plan experiments/t1-calibration-2026-10/l5-l6.eval.json
```

## L7 (task 0.4.0, 2026-10-20)

`l7.eval.json` runs the four L7 snapshots once on seven models: the five calibration models and the two MiMo V2.6 models at their default thinking. L6 trials already used about 800,000 tokens, the whole budget. L7's snapshots are larger and its questions heavier, so each trial gets 1,500,000 tokens, 200 responses, 250 tool calls and 90 minutes. A single response may hold 131,072 tokens and 524,288 characters of text. The first launch kept the old 32,768-character text limit, which stops mimo-v2.6-pro (it writes its reasoning out as text), and was stopped before any trial finished.

```bash
npm run harness -- --plan experiments/t1-calibration-2026-10/l7.eval.json
```

The second launch (`e1c476fd`, task 0.4.0) was stopped after its first two trials. qwen3.8-flash and mimo-v2.6-flash each used the whole 1.5M-token budget on L7's twelve 1,300-line logs and gave no answer, so task 0.4.1 rescales L7 to L6's data size with the same harder questions. The plan now pins 0.4.1.
