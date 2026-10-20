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

### Calibration 2026-10-20 (task 0.2.0)

Every model that ran solved every compound item. Even gpt-6-luna repaired all six stockroom faults in 18 responses, so 0.2.0 is saturated too (see `experiments/e4-calibration-2026-10/README.md`). Faults that a model recognises on sight do not separate this pool, however many there are.

## Version 0.3.0 (2026-10-20)

**codec**, a reverse-engineering item. The archived logs were written by an in-house compressor, `lgz`. Only its compiled module survives: CPython 3.13 bytecode, docstrings stripped, built reproducibly from `private/codec_item/lgz.py`. The model must recover the format from the bytecode, write `decode.py`, and restore the archive.

- **The format** has a header with a trailing-newline flag and a line count, and each line has:
  - timestamps as zigzag millisecond deltas from 2000-01-01;
  - runs of spaces in chunks of 63;
  - canonical integers of up to 18 digits as zigzag varints;
  - other tokens as indices into a 48-entry move-to-front table;
  - literals, XORed with a position- and length-dependent key, whose length takes a varint from 63 bytes on.

  Only literals of three bytes or more enter the table. A table reset at each new UTC day is in the bytecode too; a decoder does not need it, because indices only ever reach the front of the table.
- **Checks.** Eleven: ten hidden groups and `restore`. The groups are `words`, `short-tokens`, `numbers`, `timestamps`, `spaces`, `long-literals`, `eviction`, `multi-day`, `bytes` and `edges`. Each runs `decode.py` on freshly compressed hidden logs aimed at one feature, and passes when every file comes back byte for byte. `restore` compares `restored/` with the archive's originals.
- **Trust boundary.** The check script reads the expected logs into memory and deletes its helper modules before running the candidate's decoder, so a decoder cannot read them.
- **Self-calibration.** The reference decoder survived 3,000 random round trips with every feature, plus edge cases.
  - The decoder with its restored files passes everything; the untouched workspace passes nothing.
  - The decoder without restored files misses only `restore`, and the restored files alone pass only `restore`.
  - Three wrong decoders miss exactly their groups (and `restore`): one puts short literals into the table, one counts from 1970, and one reads literal lengths without the varint.
  - Two first attempts at mutants, a table of 64 entries and no day reset, turned out to be equivalent decoders. They were replaced, and `short-tokens` now mixes short tokens with repeated long ones so that the table rule matters.
  - See `logs/self-calibration-0.3.0.log`.
- **Builder.** Rebuilding rewrote `recover`'s tar with new bytes but the same objects, because Git's index records file times. The builder now keeps the existing tar while the answers it encodes are unchanged, so earlier items stay byte for byte as run.
