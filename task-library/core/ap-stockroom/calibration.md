# Calibration Record: AP stockroom

## Version 0.1.0 (2026-10-24, PLAN-007 WP3.3)

**Environment** (decision D7, recommended option): a store's stockroom of four products over 40 days, with a local supplier (next morning, 1.3 × cost, fee 15) and an import supplier (4 mornings plus a random delay of 0–3 days, cost, fee 40, minimum 25), a capacity, cash, weekday demand with trend, promotions announced a week ahead, Poisson–Gamma noise and unannounced surges. Rules and distributions are public (`public/RULES.md`); the draws are hidden in the simulator's private state. Orders are idempotent by reference; 8% of order calls get an uncertain reply (half of them placed).

**Anchors and bound** (`python3 private/build_package.py`, `private/items.json`):

| Store | Myopic | Strong | Bound | Gap | Strong setting (z import, review days, z local) |
| --- | ---: | ---: | ---: | ---: | --- |
| store-01 | 30,467.68 | 45,165.55 | 54,379.35 | 0.61 | 2.0, 2, 0 |
| store-02 | 31,212.39 | 58,675.28 | 71,390.75 | 0.68 | 2.0, 1, 0 |
| store-03 | 23,791.25 | 53,028.75 | 66,797.71 | 0.68 | 1.5, 2, 0 |
| store-04 | 42,863.51 | 63,254.59 | 77,856.95 | 0.58 | 1.5, 2, 0 |
| store-05 | 23,373.40 | 39,942.32 | 48,481.87 | 0.66 | 2.0, 1, 0 |
| store-06 | 35,212.76 | 57,765.48 | 70,906.90 | 0.63 | 2.0, 1, 0 |
| store-07 | 59,662.49 | 91,751.57 | 99,998.17 | 0.80 | 2.0, 1, 0 |
| store-08 | 49,135.88 | 70,396.67 | 80,343.53 | 0.68 | 2.0, 1, 0 |
| store-09 | 38,024.02 | 62,639.74 | 76,586.11 | 0.64 | 2.0, 1, 0 |
| store-10 | 21,940.37 | 35,840.68 | 55,189.91 | 0.42 | 1.5, 1, 0 |

Gap = (strong − myopic) / (bound − myopic). Admission (TASK_LIBRARY §3.4): at least 0.3 on every item, and the strong policy clearly below the bound: both hold. The strong policy's parameters were tuned on 30 futures resampled from the public distributions per item (72 settings), never on the item's own draws; the grid's optimum is inside it.

**Self-calibration** (`python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.1.0.log`, 71/71): anchors replay exactly from the policies' logs; the strong run completes with no invalid action or duplicate (it overflows on six items, 2–134 units, when delays bunch imports); an empty log is not completed; duplicates, invalid orders and an overflowing delivery are counted; the command-line protocol reproduces the myopic profit.

## Version 0.2.0 (2026-10-25, grader 1.1.0)

**Self-calibration** (`python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.2.0.log`, 73/73): as 0.1.0, plus the `day` command — `day command: command line equals in-process, 40 days managed` and `malformed day: invalid, no day ended`, for every item.
