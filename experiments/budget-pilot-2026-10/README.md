# Budget Pilot 2026-10

A re-pilot on the current four tasks under the scoring and budget rules of [PLAN-005](../../docs/plans/PLAN-005-discriminating-attributable-evaluation.md). It checks the mechanics:

- partial-credit scores with the 20% format deduction;
- budgets stated to the model, with reminders at 50%, 75% and 90%;
- per-task token budgets, set from the first pilot.

It does not measure difficulty; the tasks are known to be too easy (PLAN-005 WP5).

## Conditions

| Model | Report label | Thinking | Temperature |
| --- | --- | --- | --- |
| `supergpt:gpt-6-luna` | `supergpt:gpt-6-luna-medium` | `medium`, the vendor's named middle level | 0 |
| `supercn:glm-5.3` | `supercn:glm-5.3-high` | `high`, the middle of `low`, `high` and `max` | 0 |

Thinking runs at a middle level, not the maximum (user decision, 2026-10-16).

## Budgets

Each task has one budget, the same for every model, stated in the prompt (`budgetNotice: true`). At any limit the trial stops and is graded as it stands. Values are about five times or more the largest use of a non-outlier pilot trial, and are not raised for glm's overthinking (user decisions, 2026-10-15 and 2026-10-16).

| Plan | Tokens per trial | Responses | Tool calls | Time | Largest normal use in the first pilot |
| --- | --- | --- | --- | --- | --- |
| `reasoning.eval.json` (rsn-001, rsn-002) | 50,000 | 8 | 8 | 10 min | 9.1K tokens, 3 responses, 2 tool calls, 86 s |
| `tool.eval.json` (tool-001) | 100,000 | 20 | 30 | 10 min | 12.7K tokens, 6 responses, 9 tool calls, 41 s |
| `engineering.eval.json` (eng-001) | 300,000 | 40 | 60 | 30 min | luna 60K tokens, 9 responses, 11 tool calls, 90 s |

Every response may produce up to 32,768 output tokens. A token budget counts every input and output token, including cached input and reasoning. The offline replay in PLAN-005 found that glm reached a correct eng-001 solution within 300K tokens in all three replayed trials.

Worst-case spend, printed by `--validate-only`, is 1.5M tokens per model over the three plans. There are no batch ceilings, because the per-trial budgets bound spending.

## Running

```bash
npm run harness -- --plan experiments/budget-pilot-2026-10/reasoning.eval.json
npm run harness -- --plan experiments/budget-pilot-2026-10/tool.eval.json
npm run harness -- --plan experiments/budget-pilot-2026-10/engineering.eval.json
```

## What to check

1. Every failure traced to its cause: model, grader, task ambiguity or infrastructure.
2. Whether stating the budget changes token use, compared with the first pilot.
3. How often trials hit a budget; tokens per resolved trial.
4. Whether the reminders appear where expected (`budget_notice` events) and do not derail the models.
