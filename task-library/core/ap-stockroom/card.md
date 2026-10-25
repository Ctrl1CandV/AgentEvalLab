# Capability Card: AP stockroom 0.2.0 (prototype)

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP3.3), before any model run. Environment chosen by the plan's recommendation for decision D7 (inventory and orders with lead times and uncertain demand); the user has not yet decided D7.

## 1. Identity

- Tier: core candidate (prototype: one environment, ten dev seeds).
- Capabilities: agentic (decisions under uncertainty through a stateful tool).
- Protocol: `workspace-simulator`: the workspace tools with execution (to plan with programs) and the `simulator` tool (`observe`, `order`, `advance`, `day`, `result`), whose state and hidden draws live outside the workspace; one session per store; fixed budget track, provisional 5,000,000 tokens and three hours per store until the budget curve (Phase 4).
- Primary score: the store's profit over 40 days, normalised per item through two reference policies (myopic 0, strong 1), uncapped; 0 unless the model ends day 40 itself.

## 2. What it measures

Running an operation over time when the future is uncertain: reading a complete, public set of rules and a demand model, forecasting (weekdays, trend, announced promotions), weighing a cheap slow supplier with random delays against a fast expensive one, keeping safety stock without overflowing the stockroom, reacting to surprises (surges, late imports), and executing many tool calls reliably (idempotent orders, uncertain replies).

## 3. What it does not measure

- Rule-following for its own sake: every rule is simple; the difficulty is the decisions.
- Knowledge of operations research by name: the model may use any method, including writing a simulation in the workspace.
- Speed: tokens and time are reported, not scored.

## 4. Where the difficulty lies

The optimum is unreachable: the demand and the import delays are random and unseen until they happen, so no search over the scenario is possible, and the score rewards a good policy, not a lucky one (anchors are on the same draws). The offline baselines show room on both sides: a policy that only reorders yesterday's sales locally (myopic) loses to stockouts in promotions and surges and pays the local markup and fees every day; a forecast-driven policy with imports, safety stock and local top-ups, its three parameters tuned on 30 sampled futures for each of 72 settings (far more compute than a trial), gains 0.42–0.80 of the way from the myopic profit to the hindsight bound (median about 0.65), and still stays clearly below it. Doing as well as the strong policy needs the model to build and run a real policy over 40 days of tool calls; doing better needs a better one (sharper forecasts of promotions, smarter use of the two suppliers against the capacity).

## 5. Cheapest shortcut

- Doing nothing: the run does not count (`completed` fails), primary 0.
- Ordering little, from the local supplier only: about the myopic anchor, which maps to 0.
- Flooding the stockroom: units beyond the capacity are refused and paid for; holding costs and salvage at 40% punish overstock.
- Peeking at the future: the scenario's draws are in the simulator's private state, outside the workspace and the sandbox; the rules say exactly what is random.
- Duplicate orders on uncertain replies: the reference makes orders idempotent; a re-order under a new reference is a real, paid duplicate (recorded).

## 6. Anchors and headroom

| Anchor | Maps to | Source |
| --- | ---: | --- |
| myopic | 0 | reorder yesterday's demand from the local supplier every morning, on the item's own draws (`private/policies.py`) |
| strong | 1 | the forecast-driven policy with parameters tuned on sampled futures (never the item's draws), on the item's draws |
| bound (reported) | — | the hindsight optimum of the item's realised demand and delays with capacity and cash relaxed: a lot-sizing dynamic programme per product (an upper bound on any policy) |

Per item (profit): myopic 21,940–59,662; strong 35,841–91,752; bound 48,482–99,998 (`private/items.json`, `calibration.md`). The gap (strong − myopic)/(bound − myopic) is at least 0.42 on every item (admission needs 0.3), and the strong policy stays clearly below the bound on every item. Uncapped: a model that beats the strong policy scores above 1, up to roughly 1.3–2.4 at the bound.

## 7. Source, licence and provenance

Project-authored simulator, rules and policies. Exposure: generated (seeds `ap-2026-10:1` to `:10`), never published.

## 8. Task contract and grading

- The model gets `instruction.md`, `public/RULES.md` (complete rules, distributions and score), and the tool.
- The grader replays the simulator's command log (handed over by the harness, outside the model's reach) on a fresh state; days not reached are run with no orders.
- Checks: `completed` (critical: the model ended day 40); recorded hard constraints, not critical: `no-invalid-actions`, `no-duplicate-orders`, `no-overflow`. Their penalty is their effect on profit (rejected orders do nothing; duplicates and refused units are paid).
- Raw values: `profit`, `bound`, `regret`, `invalidActions`, `duplicateOrders`, `overflowUnits`, `lostUnits`, `daysManaged`.
- Equivalent solutions: any policy; only the realised profit counts.

## 9. Splits and size

Prototype: ten dev seeds of one environment, one structure group (`env:stockroom`), so no interval. TASK_LIBRARY §3.4 asks for three environments and 30 tasks for validation; those follow if the prototype shows spread in Phase 4.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: the myopic and strong logs replay to their anchors on every item; gap ≥ 0.42; strong below the bound | `python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.1.0.log` (71/71) |
| Null agent | pass: an empty log is not completed | self-calibration; suite smoke |
| Hard-constraint negative tests | pass: duplicate orders, invalid orders (unknown product, below the import minimum) and an overflowing delivery are counted | self-calibration |
| Protocol | pass: the myopic policy through the simulator's command line, one process per command, gives the same profit; issued as one `day` call per day, the command line gives its in-process profit and 40 managed days; a malformed `day` is invalid and ends no day | self-calibration |
| Adversarial | the draws are not in the workspace; the simulator runs outside the sandbox with a private state | harness (`workspace-simulator`, CODE §4a) |
| Noise, determinism | pass: deterministic given the seed and the command log; nothing timed | — |

The strong policy, a heuristic, overflows the stockroom on six of ten items (2–134 units) when random delays bunch its imports; that is recorded, not hidden.

## 11. Budget

Provisional 5,000,000 tokens and three hours per store. Task 0.1.0 needed about four calls a day, each re-reading a growing transcript (about 15M tokens for 40 days, cached input counted in full); 0.2.0's `day` command (the day's orders and its end in one call) and compact morning view bring a careful run to roughly 2–3M. The budget curve comes first in Phase 4.

## 12. History

- 0.1.0 (2026-10-24): the prototype; no model run.
- 0.2.0, grader 1.1.0 (2026-10-25): the `day` command and the compact morning view of `advance` and `day`, so that 40 days fit the token budget (the usage forecast before Phase 4 found 0.1.0's transcript alone over budget). Rules, draws, policies and anchors unchanged.
