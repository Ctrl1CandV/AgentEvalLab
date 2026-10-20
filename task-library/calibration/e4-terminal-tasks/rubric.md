# Rubric: E4 Command-Line Work

Each item is a workspace with a task in the style of Terminal-Bench, done through the command tool. Version 0.1.0's four single-fault items (a database migration, a slow program, a Git bisection and a broken build) proved too easy and stay as anchors. Version 0.2.0 adds three compound items: a service with six faults reported only as user symptoms, a make and shell pipeline with four faults between its tools, and lost work to recover from Git's unreachable objects. They proved easy too. Version 0.3.0 adds a reverse-engineering item: a decoder for a log format known only from its encoder's bytecode. It proved easy for the strong models too, so version 0.4.0 adds an item scored on a ladder: a speedup against an optimised reference. Hidden checks run the deliverables in the bubblewrap sandbox, on a fresh copy of the submission and mostly on inputs the model has not seen. Expected results come from oracle solutions. Every check is critical, and the score is the fraction of checks passed.

## Guard checks

Some checks confirm that a change broke nothing, which an untouched workspace would also pass. They count only when the item's main goal is met:

- `perf`: the output checks count only when the program is fast;
- `bisect`: the behaviour checks count only when the regression is fixed;
- `build`: the flags check counts only when the project builds;
- `migrate`: `atomic` and `idempotent` count only when the script migrates valid databases;
- `stockroom` and `pipeline`: `regression` counts only when some other check passes.

An untouched workspace scores 0 on every item.

## Items

| Item | Task | Checks |
| --- | --- | --- |
| perf | Make a slow report script fast with byte-identical output, quirks included | `speed` (a 60,000-line export in under 2 seconds); `workspace-output`, `quirks` (hidden exports, the large one included), `empty` |
| migrate | Write and run `migrate.py`, which moves a SQLite database from schema 1 to schema 2 | `schema`, `names`, `emails`, `dates`, `totals`, `statuses`, `orphans` (each on two hidden databases), `idempotent`, `atomic` (three databases with one invalid value each), `workspace-db` (the delivered `shop.db`) |
| bisect | Find the commit behind a pricing regression in a Git bundle, and undo only the regression | `culprit` (the full hash); `regression-fixed`; `rounding-kept` (the intended change in the same commit stays); `later-features`; `coupons` |
| build | Repair a C project's build and its two bugs | `build` (`make clean` then `make`); `flags` (`-std=c11 -Wall -Wextra -Werror -O2` kept); `tests` (`make test` with the shipped cases unchanged); `eof-word`, `ties`, `options` (hidden runs of the program); `clean` |
| stockroom | Fix six faults in a small inventory service, reported only as user symptoms: an environment flag parsed wrongly, report days in UTC instead of the shop's timezone, a cache not invalidated on stock changes, duplicate imports (spaces around refs included), float money, and an export that scans a table per order | `strict-env`, `timezone`, `stock-cache`, `duplicates`, `money`, `export-speed` (30,000 orders in under 10 seconds), `regression` (guard) |
| pipeline | Fix a make, shell and Python pipeline: exports without a final line break, zero-padded store ids, EU exports with `;` and decimal commas (documented, but absent from the workspace), and a missing make dependency | `line-ends`, `store-ids`, `eu-format`, `rebuild`, `combined`, `regression` (guard) |
| recover | Recover the rebased version of a deleted branch and the last dropped stash from unreachable Git objects, past a pre-rebase tip and an older stash that carry the same titles | `search-commit`, `search-tree`, `stash-commit`, `stash-file` |
| codec | Recover a log compressor's format from its CPython 3.13 bytecode, write `decode.py`, and restore the archive | `words`, `short-tokens`, `numbers`, `timestamps`, `spaces`, `long-literals`, `eviction`, `multi-day`, `bytes`, `edges` (hidden logs aimed at one feature each, compressed afresh; every file must come back byte for byte); `restore` |
| speedup | Make a slow, quirky report program fast with byte-identical output | `small`, `quirks`, `large` (the original's exact output on a normal day, a quirk day and 200,000 events; guards that count once `speed-3` passes); `speed-3`, `speed-1.5`, `speed-1.1`, `speed-0.75` (time on the large day against the reference, on one core, best of three; 0.4.0 used 16, 6, 3 and 1.5) |
