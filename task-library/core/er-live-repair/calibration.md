# Calibration: ER live repair 0.1.0

Date: 2026-10-25.

## Splits

From `python3 private/builder.py package` (2026-10-25 09:21:43):

- dev: 12 tasks, 10 repositories
- validation: 31 tasks, 14 repositories
- holdout: 3 tasks, 2 repositories

No repository appears in two splits; the most tasks of one repository in validation is 6 (pdm-project/pdm).

## Builder rejections

Rejected candidates by stage, from `private/selection.json` (297 entries, 61 admitted):

- issue: 116
- tests: 83
- licence: 16
- gold-run: 7
- runtime: 7
- base-run: 5
- runtime-size: 2

## Review

`private/review.json` holds a decision for every admitted task: 46 kept, 15 excluded.

Exclusions by reason:

- names or a new API the tests need that the issue does not state (5): `python-attrs__attrs-1457`, `kevin1024__vcrpy-1012`, `scrapy__parsel-357`, `Kozea__WeasyPrint-2890`, `hynek__stamina-160`
- tests check what the linked issue does not describe (4): `kevin1024__vcrpy-1001`, `pallets__flask-6133`, `python-babel__babel-1310`, `scrapinghub__dateparser-1430`
- the issue contains the fix itself (2): `joke2k__faker-2461`, `encode__uvicorn-3199`
- machine-dependent or unstable at the base (2): `ipython__ipython-14941`, `pallets__click-3739`
- structure cap, at most six tasks per repository (2): `pdm-project__pdm-3930`, `pdm-project__pdm-3946`

Of the kept tasks, 9 state the names their tests use in the prompt (`## Names the tests use`): `Archmonger__django-dbbackup-605`, `deepset-ai__haystack-9680`, `falconry__falcon-2459`, `falconry__falcon-2475`, `ipython__ipython-14943`, `kevin1024__vcrpy-1008`, `openai__openai-agents-python-1633`, `python-attrs__attrs-1448`, `scrapy__parsel-351`.

4 kept tasks leave tests unchecked through `dropTests` (exact ids or `re:` patterns, removed from FAIL_TO_PASS): `fastapi__typer-1410` (3 -> 1), `pyparsing__pyparsing-652` (36 -> 12), `scrapinghub__dateparser-1434` (10 -> 4), `tox-dev__tox-4172` (6 -> 3).

## Relabel

50 tasks relabelled (41 of the first screening plus 9 mined afterwards), each from 5 base and 5 gold runs through the grader's parser (whole test ids); a test whose outcome varies between identical runs lands in neither FAIL_TO_PASS nor PASS_TO_PASS. Tasks with unstable tests: `Kozea__WeasyPrint-2990` (10, test ids embedding temporary directory paths), `agronholm__anyio-1424` (2, uvloop socket tests), `kevin1024__vcrpy-976` (2). No task was rejected at the relabel stage.

## Self-calibration

`RESULT: PASS (184/184)` — 46 items x 4 scenarios; every gold resolved True, every
no-change / weakened-tests-only / does-not-apply resolved False.
Log: `logs/self-calibration-0.1.0.log`.

## Assets

`du -shL task-library/core/er-live-repair/assets`: 2.7G.

## Data window

- dev: SWE-bench-Live (issues created before 2025-09).
- validation and holdout: mined fixes merged after 2026-06-01 (`--since 2026-06-01`).
