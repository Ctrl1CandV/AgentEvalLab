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

