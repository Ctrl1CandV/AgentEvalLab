# Suite report v2: fixture (v2.0-fixture)

**Exploratory.** Dev split or fewer than five structure groups in some family: differences here are not conclusions.

Suite run `20261024-000000-fixture-0000` at commit `0123456789ab`; split validation; track fixed; 1 repetition(s); 2026-10-24T00:00:00.000Z to 2026-10-24T01:00:00.000Z; status **completed**.

| Model | Thinking | Temperature |
| --- | --- | --- |
| m:a-high | high | 0 |
| m:b-default | provider-default | 0 |

| Family | Tier | Capability | Package | Budget | Context | Tools | Command limits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CORE | core | reasoning | core-task@0.1.0 | 2M/task | single | workspace-basic | default |
| FRONT | frontier | engineering | frontier-task@0.1.0 | 30M/task | single | workspace-basic | default |
| BASE | basic | agentic | basic-task@0.1.0 | 2M/task | single | workspace-basic | default |

Every number below comes from the trials' outcome records (MEASUREMENT §2). A task is the sample: intervals resample structure groups (2,000 seeded resamples, 95% percentile) and are not given below five groups. Resolved-primary families read as the share of tasks resolved; open-ended families as a normalised value through the family's anchors, which is not capped at 1. Efficiency is reported, never scored.

## Capability profile

| Model | reasoning (core) |
| --- | --- |
| m:a-high | 0.75 [0.583–0.917], 12 tasks |
| m:b-default | 0.167 [0–0.333], 12 tasks |

Families reported as their own rows and never averaged into the core (basic, frontier, and core families of a second protocol):

| Model | FRONT (frontier) | BASE (basic) |
| --- | --- | --- |
| m:a-high | 0.688 [n too small] | 100.0% [n too small] |
| m:b-default | 0.125 [n too small] | 100.0% [n too small] |

## Families

### CORE (core, reasoning)

Primary: resolved rate. Runs: `runs/suites/x/runs/CORE/r1`.

| Model | Tasks | Trials | Coverage | Resolved | Primary | 95% interval | Diagnostic | Format strict / recovered / missing | Penalised | Stops | Infra / refusals |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | --- | ---: | --- | --- |
| m:a-high | 12 | 12 | 12 scored, 0 unscored, 0 not run of 12 planned | 75.0% | 75.0% | 58.3%–91.7% | 87.5% | 9 / 3 / 0 | 70.0% | done 12 | 0 / 0 |
| m:b-default | 12 | 12 | 12 scored, 0 unscored, 0 not run of 12 planned | 16.7% | 16.7% | 0.0%–33.3% | 33.3% | 12 / 0 / 0 | 16.7% | done 11, budget 1 | 0 / 0 |

### FRONT (frontier, engineering)

Primary: normalised metric, uncapped. Runs: `runs/suites/x/runs/FRONT/r1`.

| Model | Tasks | Trials | Coverage | Resolved | Primary | 95% interval | Diagnostic | score (median) | Format strict / recovered / missing | Penalised | Stops | Infra / refusals |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: | --- | ---: | --- | --- |
| m:a-high | 3 | 3 | 3 scored, 0 unscored, 0 not run of 3 planned | 100.0% | 0.688 | n too small | 100.0% | 700 | 0 / 0 / 0 | 0.688 | done 3 | 0 / 0 |
| m:b-default | 3 | 3 | 3 scored, 0 unscored, 1 not run of 4 planned **(incomplete)** | 100.0% | 0.125 | n too small | 100.0% | 100 | 0 / 0 / 0 | 0.125 | done 3 | 0 / 0 |

### BASE (basic, agentic)

Primary: resolved rate. Runs: `runs/suites/x/runs/BASE/r1`.

| Model | Tasks | Trials | Coverage | Resolved | Primary | 95% interval | Diagnostic | Format strict / recovered / missing | Penalised | Stops | Infra / refusals |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | --- | ---: | --- | --- |
| m:a-high | 2 | 2 | 2 scored, 0 unscored, 0 not run of 2 planned | 100.0% | 100.0% | n too small | 100.0% | 2 / 0 / 0 | 100.0% | done 2 | 0 / 0 |
| m:b-default | 2 | 2 | 2 scored, 0 unscored, 0 not run of 2 planned | 100.0% | 100.0% | n too small | 100.0% | 2 / 0 / 0 | 100.0% | done 2 | 0 / 0 |

## Pairwise comparisons

Per core capability, paired by task: A − B in the capability's primary, with a stratified cluster-bootstrap interval and the share of tasks each model is ahead.

| Capability | A | B | Tasks | A − B | 95% interval | A ahead | B ahead | Tied |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| reasoning | m:a-high | m:b-default | 12 | 0.583 | 0.333–0.833 | 58.3% | 0.0% | 41.7% |

## Saturation and headroom

| Family | Tasks scored for every model | Solved by all | Solved by none | Best above the strong anchor | Spread |
| --- | ---: | ---: | ---: | ---: | ---: |
| CORE | 12 | 2 | 3 | — | 0.583 |
| FRONT | 3 | — | — | 1 | 0.563 |
| BASE | 2 | 2 | 0 | — | 0 |

## Efficiency

Medians per scored trial; tokens are fixed units without prices, cached input counted in full. Reported, never scored.

| Family | Model | Tokens | Wall time (s) | Model calls | Tokens per resolved task |
| --- | --- | ---: | ---: | ---: | ---: |
| CORE | m:a-high | 3k | 60 | 12 | 3k |
| CORE | m:b-default | 1k | 60 | 12 | 8k |
| FRONT | m:a-high | 1k | 60 | 12 | 1k |
| FRONT | m:b-default | 1k | 60 | 12 | 1k |
| BASE | m:a-high | 1k | 60 | 12 | 1k |
| BASE | m:b-default | 1k | 60 | 12 | 1k |

## Audit status

| Family | Latest success audit | Verdicts |
| --- | --- | --- |
| CORE | 2026-10-24 | true pass 10 |
| FRONT | none | — |
| BASE | none | — |
