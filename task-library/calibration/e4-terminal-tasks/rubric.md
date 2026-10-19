# Rubric: E4 Command-Line Work

Each item is a workspace with a task in the style of Terminal-Bench: working with a database, a slow program, a Git history and a broken build through the command tool. Hidden checks run the deliverables in the bubblewrap sandbox, on a fresh copy of the submission and mostly on inputs the model has not seen. Expected results come from oracle solutions. Every check is critical, and the score is the fraction of checks passed.

## Guard checks

Some checks confirm that a change broke nothing, which an untouched workspace would also pass. They count only when the item's main goal is met:

- `perf`: the output checks count only when the program is fast;
- `bisect`: the behaviour checks count only when the regression is fixed;
- `build`: the flags check counts only when the project builds;
- `migrate`: `atomic` and `idempotent` count only when the script migrates valid databases.

An untouched workspace scores 0 on every item.

## Items

| Item | Task | Checks |
| --- | --- | --- |
| perf | Make a slow report script fast with byte-identical output, quirks included | `speed` (a 60,000-line export in under 2 seconds); `workspace-output`, `quirks` (hidden exports, the large one included), `empty` |
| migrate | Write and run `migrate.py`, which moves a SQLite database from schema 1 to schema 2 | `schema`, `names`, `emails`, `dates`, `totals`, `statuses`, `orphans` (each on two hidden databases), `idempotent`, `atomic` (three databases with one invalid value each), `workspace-db` (the delivered `shop.db`) |
| bisect | Find the commit behind a pricing regression in a Git bundle, and undo only the regression | `culprit` (the full hash); `regression-fixed`; `rounding-kept` (the intended change in the same commit stays); `later-features`; `coupons` |
| build | Repair a C project's build and its two bugs | `build` (`make clean` then `make`); `flags` (`-std=c11 -Wall -Wextra -Werror -O2` kept); `tests` (`make test` with the shipped cases unchanged); `eof-word`, `ties`, `options` (hidden runs of the program); `clean` |
