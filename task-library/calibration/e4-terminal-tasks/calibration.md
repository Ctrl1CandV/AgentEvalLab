# Calibration Record: E4 Command-Line Work

E4 is the command-line family of Task Set v2 (PLAN-005 WP5), in the style of Terminal-Bench: each item is a workspace and a task that needs the command tool, and hidden checks test the result in the sandbox.

## Version 0.1.0 (2026-10-19)

- **Built with** `python3 private/build_package.py`. Generation is seeded, and the Git history uses fixed authors and dates, so the culprit hash is reproducible.
- **perf.** The slow `report.py` is quadratic in the number of users: 7 seconds on the 40,000-line workspace export, close to the 10-second command limit, and 13 seconds on the hidden 60,000-line export. The oracle in `private/perf/oracle.py` takes 0.06 seconds, and it matches the original byte for byte on every hidden input. The inputs include rounding quirks such as `round(-2.25, 1)` giving `-2.2`.
- **migrate.** The oracle matches a small database whose schema 2 content was written by hand from the prompt's rules: comma names, collapsed whitespace, one-word names, emails, dates, totals with thousands separators and one decimal, orphans. It leaves each of three databases with an invalid value unchanged, and it is unchanged by a second run.
- **bisect.** The culprit commit also makes an intended change, half-even rounding (FIN-212), and later commits add shipping, GBP and a minimum order. A full revert of the culprit commit loses the rounding, and the file from before the culprit loses the later features. The checks tell all of these apart.
- **build.** A space-indented recipe, an object missing from the link, a test target that runs a script without execute permission, an incomplete `clean`, an unused variable under `-Werror`, a word lost at end of input and unsorted ties. The repaired project in `private/build/solution` passes; the shipped one fails at the first `make`.
- **Guard checks** count only when the item's main goal is met, so an untouched workspace scores 0 on every item; see the rubric.
- **Self-calibration** (`python3 private/grader.py --self-calibrate --launcher scripts/sandbox_exec.py`, 22/22):
  - each oracle passes every check, and each untouched workspace passes none;
  - partial or wrong solutions pass exactly the checks they should: a fast report that does not lower-case users; a migration that ignores comma names, keeps email case, computes cents through floats, skips the version check, drops orphans without logging them, or is not run on `shop.db`; a copied current file; a full revert; the file from before the culprit; a Makefile-only repair; a repair without the end-of-input fix or the tie fix; and dropped compiler flags.

  See `logs/self-calibration-0.1.0.log`.

### Calibration 2026-10-19 (task 0.1.0)

All five models passed every check of all four items in both repetitions, so the items are easy anchors. See `experiments/e4-calibration-2026-10/README.md`.

## Version 0.2.0 (2026-10-20)

Three compound items, built so that a model has to investigate, not just repair a named fault.

- **stockroom.** A small inventory service with config, SQLite storage, CSV import, a file cache, reports, export and a CLI.
  - It has six faults, and the prompt gives only the users' symptoms.
  - Each symptom has a hidden check written by hand from `README.md`, including cases the symptom does not mention: refs with spaces, a stock change through an import, the New York timezone, and half-cent revenue.
  - The shipped service fails every check, and the export check times out on 30,000 orders. The repaired service in `private/stockroom_item/solution` passes all of them in about 3 seconds.
- **pipeline.** A make, shell and Python pipeline with four faults:
  - exports that end without a line break, whose last line plain concatenation glues to the next file;
  - zero-padded store ids;
  - EU exports, which `README.md` documents but the workspace does not contain;
  - a make dependency missing on `raw/stores.csv`.

  Each fault has its own hidden dataset; one combined dataset and a rebuild test follow. Expected reports were written by hand.
- **recover.** A tarred Git repository whose `search` branch was rebased and then deleted, and whose release-notes stash was stashed twice and dropped. Reflogs are cleared, so `git fsck` finds four lost commits. The checks need the rebased tip, not the pre-rebase one with the same titles, and the stash dropped last. Commit hashes are reproducible; the tar's bytes are not, because Git's index records file times.
- **Self-calibration (40/40).** Each oracle passes everything, and each untouched workspace passes nothing. Every single-fault repair passes exactly its own checks, plus the guard. Three cases earn nothing: a cache invalidated only on restock, a pipeline without EU handling (which misses `eu-format` and `combined`), and the decoy commit or stash. See `logs/self-calibration-0.2.0.log`.
- **Builder.** The package builder skips hidden files, which the sandbox can leave in package directories.
