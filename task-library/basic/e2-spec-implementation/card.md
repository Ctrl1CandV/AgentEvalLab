# Capability Card: E2 specification implementation 0.5.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP2.2), for grader 1.6.0 on the unchanged task 0.5.0.

## 1. Identity

- Tier: basic for the contract items (sheet, ledger, recur, query); **routes** is an open-ended bridge reported in core engineering (TASK_LIBRARY §2), run by the suites as the family `E2-routes`.
- Capabilities: engineering.
- Protocol: `workspace-basic` with command execution; one session per item; fixed budget track, stated to the model. Routes: 3,000,000 tokens and two hours (the last v1 configuration, `experiments/e2-calibration-2026-10/routes.eval.json`). The contract items have no configuration at this version and are in no suite yet (their last runs used 0.8M at 0.3.0 and 1.2M at 0.4.0).
- Primary score: resolved for the contract items; for routes, `routeShare` through its anchors, uncapped.

## 2. What it measures

Implementing a program from a written specification, from an empty workspace: a spreadsheet evaluator (sheet), a ledger with holds, captures and FX (ledger), a recurrence-rule expander (recur), a small SQL engine (query), and, open-ended, a vehicle-routing heuristic under capacity, duration and refrigeration constraints with an 8-second limit (routes).

## 3. What it does not measure

- Working in an existing code base (ER, E3).
- Library knowledge: the Python standard library only.
- Speed of the model: reported, not scored.

## 4. Where the difficulty lies

- **Contract items (basic): reliability.** Every behaviour is specified, with worked examples; hidden fixtures cover the edge cases each section names (error propagation, rounding, ordering, clamping). Strong models resolve most checks; the misses are slips on a rule.
- **Routes (bridge): real headroom.** A simple constructive heuristic reaches the baseline; savings construction gets past half the way; reaching the best known costs (long runs of a local-search heuristic, offline) within 8 seconds on 50–800 customers needs a good construction plus an efficient improvement search under the constraints. In v1 (3M tokens) deepseek-flash reached 71.2% of the rung scale, the mimo models 56–58%, qwen3.8-flash 16.7%.

## 5. Cheapest shortcut

- Missing or crashing programs: nothing passes (each item's missing-program check in the self-calibration).
- Routes: the nearest-neighbour baseline itself is at 0; an infeasible plan counts 0 for its instance; a program that runs past the limit counts 0.
- Hard-coding the samples: the hidden fixtures and instances differ.

## 6. Anchors and headroom

| Metric | Anchor | Maps to | Raw value | Source |
| --- | --- | ---: | ---: | --- |
| `routeShare` | baseline | 0 | 0 | per instance, the nearest-neighbour baseline the contract names |
| `routeShare` | best-known | 1 | 1 | per instance, the best cost of three long offline runs (`private/routes/anchors.json`) |

- `routeShare` is the mean over the eight hidden instances of `(baseline − cost) / (baseline − best)`, each at least 0 and never capped: the contract's own scale, now reported as a value rather than four rungs. A plan better than the best known goes above 1 (flagged as extrapolated). The rungs 50/80/90/97% stay as labels in a non-critical group.
- Diagnostics: `routeCost` (the total length, an instance without a feasible plan at its baseline's cost) and `feasibleInstances`.
- Validity: the README the contract asks for (the critical group `readme`). Per-instance validity is inside the value: an infeasible, late or missing plan counts 0 for its instance.

## 7. Source, licence and provenance

Project-authored specifications, references, fixtures and instance generator; no third-party text or code. Exposure: private to runs.

## 8. Task contract and grading

- Each item's `prompt.md` is its specification; the program runs in the sandbox on hidden fixtures (10 s each) or instances (stopped at 10 s, 8 s stated).
- Score model: one critical group per contract item (rule fraction); `readme` (critical); for routes, its 32 rung checks in a non-critical group and the metric group `routes-share`. `primaryByItem` makes routes metric-primary.
- Timing: routes' limit is wall time, as the contract states; from grader 1.6.0 routes gradings run one at a time under a lock, each on one core. Under heavy machine load a time-bounded search loses value (noise test below), so routes should be graded on a lightly loaded machine.
- Equivalent solutions: any implementation; only outputs (and, for routes, plan costs) count. Sheet compares numbers with a tolerance; the others exactly.

## 9. Splits and size

Each item is its own task and structure group (`item:<id>`), all dev. Routes, a single task, is a bridge for linking releases, not a discriminating family on its own (one structure group, no interval).

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: each contract item's reference passes every check; routes: LNS and savings each pass every 50% rung, LNS above savings | `python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.5.0-grader-1.6.0.log` |
| Null agent | pass: a missing program fails every check; routes' baseline earns nothing | self-calibration; the suite smokes |
| Mutants | pass: every mutant fails the check it targets | self-calibration |
| Alternative valid solutions | pass for routes (LNS, savings); the contract items accept any output that matches | self-calibration |
| Adversarial | n/a beyond the sandbox: outputs are recomputed | — |
| Noise | routes, **open**: with 5 busy processes on 20 cores the LNS reference's `routeShare` moves 0.009 and no label changes (pass at the declared 0.03); with every core busy it loses 0.052 and three rung labels (fail). The wall-time limit is the contract's; a time-bounded search does less work on a loaded machine. Routes gradings run one at a time under a lock; a CPU-time limit would need a new task version (PLAN-007 Phase 2 review) | `python3 private/grader.py --noise [--load N]`, `logs/noise-0.5.0-grader-1.6.0-routes.log` |
| Determinism | contract items pass; routes depends on the machine through its wall-time limit | — |

## 11. Budget

Routes 3,000,000 tokens (v1); every routes trial in v1 stopped on its budget, which an open-ended item is expected to do.

## 12. History

- 0.1.0–0.5.0: see `calibration.md`.
- Grader 1.6.0 (2026-10-24): manifest v2; routes reports `routeShare`, `routeCost` and `feasibleInstances`, is headlined by `routeShare`, and is judged one grading at a time; every 0.5.0 trial re-graded.
