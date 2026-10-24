# Suite report v2: v2-measurement-proof

**Exploratory.** Dev split or fewer than five structure groups in some family: differences here are not conclusions.

Suite run `proof-9e1c2b69` at commit `0e3490f891cd`; split dev; track fixed; 1 repetition(s); 2026-10-24 to 2026-10-24; status **completed**.

| Model | Thinking | Temperature |
| --- | --- | --- |
| aliplan:qwen3.8-flash-default | default | 0 |
| deepseek:deepseek-flash-high | high | 0 |
| mimoplan:mimo-v2.6-flash-default | default | 0 |
| mimoplan:mimo-v2.6-pro-default | default | 0 |
| reference:naive | n/a (a program) | provider default |
| reference:greedy | n/a (a program) | provider default |

| Family | Tier | Capability | Package | Budget | Context | Tools | Command limits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R3 | core | reasoning | r3-logic-grid@0.3.0 | 0.3M/task | single | workspace-basic, read-only, no execution | default |
| AE | frontier | engineering | ae-heuristic-contests@0.2.0 | none (reference programs) | single | workspace-augmented | 600 s |

Every number below comes from the trials' outcome records (MEASUREMENT §2). A task is the sample: intervals resample structure groups (2,000 seeded resamples, 95% percentile) and are not given below five groups. Resolved-primary families read as the share of tasks resolved; open-ended families as a normalised value through the family's anchors, which is not capped at 1. Efficiency is reported, never scored.

## Capability profile

| Model | reasoning (core) |
| --- | --- |
| aliplan:qwen3.8-flash-default | 0.083 [n too small], 24 tasks |
| deepseek:deepseek-flash-high | 0.708 [n too small], 24 tasks |
| mimoplan:mimo-v2.6-flash-default | 0.304 [n too small], 22 tasks |
| mimoplan:mimo-v2.6-pro-default | 0.417 [n too small], 24 tasks |

Basic and frontier families, reported as their own rows and never averaged into the core:

| Model | AE (frontier) |
| --- | --- |
| aliplan:qwen3.8-flash-default | — |
| deepseek:deepseek-flash-high | — |
| mimoplan:mimo-v2.6-flash-default | — |
| mimoplan:mimo-v2.6-pro-default | — |
| reference:naive | 0 [0–0] |
| reference:greedy | 0.377 [n too small] |

## Families

### R3 (core, reasoning)

Primary: resolved rate. Runs: `runs/e3b89e80-676e-4b9b-a3dc-f5e2ddff6bfb`.

| Model | Tasks | Trials | Coverage | Resolved | Primary | 95% interval | Diagnostic | cellAccuracy (median) | constraintValidity (median) | wellFormed (median) | Format strict / recovered / missing | Penalised | Stops | Infra / refusals |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- |
| aliplan:qwen3.8-flash-default | 24 | 24 | 24 scored, 0 unscored, 0 not run of 24 planned | 8.3% | 8.3% | n too small | 24.5% | 0.123 | 0.626 | 1 | 11 / 2 / 11 | 8.3% | output_limit 3, done 21 | 0 / 0 |
| deepseek:deepseek-flash-high | 24 | 24 | 24 scored, 0 unscored, 0 not run of 24 planned | 70.8% | 70.8% | n too small | 72.3% | 1 | 1 | 1 | 19 / 0 / 5 | 70.8% | done 19, output_limit 5 | 0 / 0 |
| mimoplan:mimo-v2.6-flash-default | 24 | 24 | 22 scored, 2 unscored, 0 not run of 24 planned | 30.4% | 30.4% | n too small | 31.8% | 0 | 0 | 0 | 6 / 1 / 15 | 30.9% | output_limit 15, done 8, timeout 1 | 0 / 2 |
| mimoplan:mimo-v2.6-pro-default | 24 | 24 | 24 scored, 0 unscored, 0 not run of 24 planned | 41.7% | 41.7% | n too small | 41.7% | 0 | 0 | 0 | 10 / 0 / 14 | 41.7% | done 10, output_limit 14 | 0 / 0 |

### AE (frontier, engineering)

Primary: normalised metric, uncapped. Runs: none.

| Model | Tasks | Trials | Coverage | Resolved | Primary | 95% interval | Diagnostic | performance (median) | performanceExtrapolated (median) | performanceRank (median) | total (median) | Format strict / recovered / missing | Penalised | Stops | Infra / refusals |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | --- |
| reference:naive | 10 | 10 | 10 scored, 0 unscored, 0 not run of 10 planned | 100.0% | 0 | 0–0 | 50.0% | 624.5 | 0 | 811.75 | 4402925 | 0 / 0 / 0 | 0 | done 10 | 0 / 0 |
| reference:greedy | 3 | 3 | 3 scored, 0 unscored, 0 not run of 3 planned | 100.0% | 0.377 | n too small | 68.8% | 937 | 0 | 568.5 | 46461176 | 0 / 0 / 0 | 0.377 | done 3 | 0 / 0 |

## Pairwise comparisons

Per core capability, paired by task: A − B in the capability's primary, with a stratified cluster-bootstrap interval and the share of tasks each model is ahead.

| Capability | A | B | Tasks | A − B | 95% interval | A ahead | B ahead | Tied |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| reasoning | aliplan:qwen3.8-flash-default | deepseek:deepseek-flash-high | 24 | -0.625 | n too small | 0.0% | 62.5% | 37.5% |
| reasoning | aliplan:qwen3.8-flash-default | mimoplan:mimo-v2.6-flash-default | 22 | -0.214 | n too small | 4.5% | 27.3% | 68.2% |
| reasoning | aliplan:qwen3.8-flash-default | mimoplan:mimo-v2.6-pro-default | 24 | -0.333 | n too small | 4.2% | 37.5% | 58.3% |
| reasoning | deepseek:deepseek-flash-high | mimoplan:mimo-v2.6-flash-default | 22 | 0.47 | n too small | 45.5% | 0.0% | 54.5% |
| reasoning | deepseek:deepseek-flash-high | mimoplan:mimo-v2.6-pro-default | 24 | 0.292 | n too small | 29.2% | 0.0% | 70.8% |
| reasoning | mimoplan:mimo-v2.6-flash-default | mimoplan:mimo-v2.6-pro-default | 22 | -0.143 | n too small | 9.1% | 22.7% | 68.2% |

## Saturation and headroom

| Family | Tasks scored for every model | Solved by all | Solved by none | Best above the strong anchor | Spread |
| --- | ---: | ---: | ---: | ---: | ---: |
| R3 | 22 | 1 | 5 | — | 0.625 |
| AE | 3 | — | — | 0 | 0.377 |

## Efficiency

Medians per scored trial; tokens are fixed units without prices, cached input counted in full. Reported, never scored.

| Family | Model | Tokens | Wall time (s) | Model calls | Tokens per resolved task |
| --- | --- | ---: | ---: | ---: | ---: |
| R3 | aliplan:qwen3.8-flash-default | 61k | 858 | 1 | 912k |
| R3 | deepseek:deepseek-flash-high | 92k | 389 | 1 | 154k |
| R3 | mimoplan:mimo-v2.6-flash-default | 133k | 2479 | 1 | 341k |
| R3 | mimoplan:mimo-v2.6-pro-default | 133k | 1846 | 1 | 244k |
| AE | reference:naive | 0k | 0 | 0 | 0k |
| AE | reference:greedy | 0k | 0 | 0 | 0k |

## Audit status

| Family | Latest success audit | Verdicts |
| --- | --- | --- |
| R3 | none | — |
| AE | none | — |

## About this report

A fixture suite for PLAN-007 WP1.6, built by `scripts/measurement-proof.ts` without any model run. R3 rows are the 0.3.0 pilot's trials (`runs/e3b89e80-676e-4b9b-a3dc-f5e2ddff6bfb`) re-graded under grader 2.0.0 into v2 outcomes; glm-5.3, step-5-preview and gpt-6-luna are absent because their trials of that run failed on the provider and were never graded. AE rows are reference programs graded through the real grader protocol: `reference:naive` is each problem's naive reference (the anchor that maps to 0), `reference:greedy` the stronger references that exist so far. The suite id and commit are the proof's, not a suite run's.
