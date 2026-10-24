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

### Calibration 2026-10-20 (task 0.3.0)

codec did not separate the strong models: deepseek, qwen and mimo-v2.6-flash decoded every hidden group. Fixed-answer items, however novel, saturate for this pool, so 0.4.0 adds an item scored on a ladder.

## Version 0.4.0 (2026-10-20)

**speedup**: make the nightly traffic report fast with byte-for-byte identical output.

- **The program.** `analyze.py` (`private/speedup_item/naive.py`) is correct but naive, with quadratic loops and `strptime` for every row. It has quirks the output depends on:
  - `strptime` accepts single-digit fields, a lowercase `t`, offsets without a colon and six fraction digits, and rejects a missing fraction, a lowercase `z` and a leading space;
  - user and path normalisation;
  - nearest-rank percentiles and half-even rounding;
  - a ten-second burst window with both ends included, and sessions split only after *more* than 30 minutes.
- **The reference** (`private/speedup_item/reference.py`) is one pass, O(n log n), with a fast path for canonical timestamps and `strptime` for everything else. Its output equals the original's on every dataset tried, quirk-heavy ones included. On 200,000 events it takes 0.69 s; the original takes 49 s.
- **Checks.**
  - `small`, `quirks`, `large`: the original's exact output on a normal day, a quirk day and a day of 200,000 events. The quirk day has the malformed rows and exact 30-minute gaps and 10-second bursts.
  - `speed-16`, `speed-6`, `speed-3`, `speed-1.5`: the time on the large day against the reference, best of three interleaved runs, on one pinned core. They need the normal and large outputs right.
  - The output checks count only once `speed-16` passes, so the original earns nothing.
  - The check script keeps the original and the reference in memory and writes each to disk only while it runs.
- **Self-calibration** (with every other item, `logs/self-calibration-0.4.0.log`):
  - The reference passes everything; the untouched program and the original pasted back pass nothing.
  - `strptime` for every timestamp, twice (4–5 times the reference) misses `speed-3` and `speed-1.5`.
  - The fast path without the `strptime` fallback misses only `quirks`, and so do sessions split at exactly 30 minutes.
  - A first version of that last mutant passed everything, because no gap was exactly 30 minutes; the quirk day now has such boundaries.

## Version 0.4.1 (2026-10-20)

**Why.** The speedup ladder topped out too early. In the first trials, deepseek's analyze.py ran in 0.51 s against the reference's 0.77 s, and qwen's in 0.97 s, so both passed every check up to `speed-1.5`. Their solutions are seriously engineered: a hand-written timestamp scanner over lookup tables, interned columns, and the csv module only when a field is quoted. That is close to the practical floor for this work in Python, so a much faster reference is not realistic.

**The ladder moves to where the field spreads:** `speed-3`, `speed-1.5`, `speed-1.1` and `speed-0.75`, measured against the same reference. The output checks now count once `speed-3` passes.

**Self-calibration** (`logs/self-calibration-0.4.1.log`):

| Candidate | Time against the reference | Checks |
| --- | --- | --- |
| the reference itself | 1× | everything but `speed-0.75` |
| `csv.DictReader` instead of `csv.reader` | 1.3× | misses `speed-1.1` and `speed-0.75` |
| `strptime` for every row, twice | 4–5× | nothing |
| the fast path without the `strptime` fallback, or sessions split at exactly 30 minutes | 1× | misses `quirks` and `speed-0.75` |

The first run under 0.4.0 is regraded with grader 1.3.1.

## Version 0.5.0 (2026-10-21)

**compress**, a second item scored on a continuous scale (PLAN-006 B1). The logs are a simulated hour of CDN edge traffic (`private/compress_item/logdata.py`).

- **Clients** come from a pool. Each has a fixed address, region, user agent, account and HTTP version. Their sessions walk the shop's pages, edges number their requests, and the collector writes lines slightly out of order.
- **The structure is real but must be found in the data:**
  - the edge, user agent, account and protocol follow from the address;
  - request ids count up per edge;
  - images follow the product a client just viewed;
  - a resource's size depends only on the resource and status;
  - the upstream follows from the route.
- **The task.** Rewrite the gzip-only `packlog.py` (compress and decompress). It must restore any input byte for byte: damaged lines, invalid UTF-8, CRLF, blank lines, empty files. The workspace has a 15,000-line sample with a few damaged lines.
- **The scale.**
  - 0% is `lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)`, 14.4 bytes per line on the sample.
  - 100% is `private/compress_item/packref.py`, 5.9 bytes per line. It codes fields as separate streams:
    - timestamps as deltas;
    - addresses through a recency cache;
    - edge, account, protocol and user agent as "same as this address last time";
    - request ids as deltas per edge;
    - paths as a shape plus numbers, reusing the client's last numbers;
    - sizes and upstreams memoised by resource and route;
    - every stream through LZMA.

    Lines that do not come back exactly from their fields are stored raw. It takes 1.2 seconds for 50,000 lines.
- **Where simpler compressors land** on the hidden days (measured with `packref.py` variants):

  | Compressor | Position |
  | --- | ---: |
  | gzip -9 | −85% |
  | bz2 -9 | 12% |
  | fields split into columns, each through LZMA | 12% |
  | the same, timestamps as deltas | 15% |
  | the reference without the per-address profile or per-edge request ids | 56% |
  | the reference without the per-address profile | 78% |
  | the reference without per-edge request ids | 78% |
  | the reference without the size memo | 89% |
  | the reference without number reuse | 96.5% |

  Splitting columns alone is worth little against LZMA. The ladder's rungs are structural insights about the data.
- **Checks.**
  - `roundtrip`: days a and b (50,000 and 30,000 lines). The time limit is 60 seconds per run, raised to 40 times the reference's measured time when the machine is busy, so load never fails a run.
  - `roundtrip-quirks`: a log with 30% damaged lines, an empty file, a last line without a newline, and 64 KB of random bytes.
  - `ratio-50/80/90/97`.
  - The round trips are guards that count once `ratio-50` passes.
- **Trust boundary.**
  - The check imports the generator and the reference, then deletes their files.
  - Each run starts from a fresh copy of the delivered workspace, made from a copy whose hashes are checked before each decompression.
  - Only the compressed file moves between the two runs, and anything a run leaves in /tmp is removed.
- **Self-calibration** (`logs/self-calibration-0.5.0.log`), all as expected:
  - the reference passes all six checks;
  - the untouched gzip program, an LZMA preset 9e wrapper, a program that stashes the original in /tmp and in the pristine copy, and one over the time limit pass nothing;
  - the variants without the profile and request ids pass `ratio-50` and the guards; without the size memo they reach `ratio-80`, and without number reuse `ratio-90`;
  - a compressor that reads lines as UTF-8 text misses only `roundtrip-quirks`.

**speedup gets a lower rung, `speed-8`.** The formal 0.4.1 run (suite `20261021-120039-dev-fe3b`) put deepseek-flash at 0%. The audit:

- Its delivered program is correct on every hidden day.
- It takes 2.5 seconds against the reference's 0.8, 3.1 times as long, measured again on an idle machine. The trial ended at its token budget in the middle of more tuning.
- Under 0.4.1 a correct program 3.1 times as slow as the reference earned nothing. One 2.9 times as slow earned 4 of 7.

The deduction was the model's own, but such a cliff turns small speed differences into the whole score. In 0.5.0 the output checks count once `speed-8` passes, and the original, about 70 times as slow, still earns nothing. A correct program 3.1 times as slow now earns 4 of 8. The `strptime`-everywhere mutant (4–5 times) passes the outputs and `speed-8`.

**Family score.** E4 is now `speedup` and `compress`, each scored as the fraction of its checks; the family score is their mean. They run from `experiments/e4-calibration-2026-10/speedup-0.5.eval.json` and `compress.eval.json`, because their budgets differ (below).


### Calibration 2026-10-21/22 (task 0.5.0)

Runs `runs/suites/20261021-123806-dev-d275` (speedup and compress for deepseek-flash, qwen3.8-flash and mimo-v2.6-flash) and `runs/suites/20261022-040520-dev-7f6a` (deepseek's compress, which the first suite's token ceiling had left unrun):

| Model | speedup | compress | compress ended |
| --- | --- | --- | --- |
| deepseek-flash | 7/8 | 0/6 | at the budget, its `packlog.py` mid-edit (a range coder that raises a TypeError) |
| qwen3.8-flash | 8/8 | 0/6 | its turn ended with `packlog.py` half-written |
| mimo-v2.6-flash | 7/8 | 0/6 | at the budget; its program round-trips but is larger than LZMA preset 9e |

The check was rerun by hand on each delivered program and agreed. No trial timed out a command.

The compress trials made 30–38 requests within 2,000,000 tokens, about 60,000 tokens each, because every request resends a session full of programs and samples. No model left a working compressor. The budget is meant to let most models finish, so it was too small for this item. compress now has 4,000,000 tokens per trial; speedup keeps 2,000,000.

At 4,000,000 tokens (`runs/suites/20261022-050033-dev-0cdf`), deepseek-flash reached 92.7% of the way to the reference (5/6) and qwen3.8-flash 81.8% (4/6). Both programs round-trip every hidden input within the time limit.


## Grader 1.5.0 (2026-10-24, task 0.5.0 unchanged)

**Why.** The PLAN-007 success audit (`docs/audits/E4-speedup/2026-10-24.md`) ran every recorded speedup delivery against the original on days of its own and found three deliveries that the hidden checks passed but that print something else than the original for some inputs, which the task forbids ("byte for byte the same for every input"):

- deepseek-flash, task 0.5.0 (`runs/suites/20261021-123806-dev-d275`): rows without the referrer column, which the original reads with the referrer "-";
- qwen3.8-flash, task 0.5.0 (same suite, 8/8): a literal "-" referrer, which the original leaves out of the transitions as it does an empty one;
- qwen3.8-flash, task 0.4.0 (`runs/9b2dbac7-7ae8-4546-ac77-8abff5fe1f24`): numbers in full-width or Arabic-Indic digits, which `int()` reads.

None of these appeared on the hidden quirks day.

**Change.** The hidden quirks day (`private/speedup_item/data.py`, drawn with `audited=True`) now holds those rows, and some unusual user names. The small and large days and the public sample are drawn as before and are byte for byte unchanged; so are all item files. Three new self-calibration mutants of the reference, one per slip, fail `quirks` only (`logs/self-calibration-0.5.0-grader-1.5.0-speedup.log`). Every 0.5.0 speedup trial was re-graded under 1.5.0; the 0.4.x trials belong to superseded task versions and keep their graders' numbers, with the audit's finding recorded.

## Grader 1.6.0 and manifest v2 (2026-10-24, task 0.5.0 unchanged, PLAN-007 WP2.2)

**Why.** Two things, both in the measurement, none in the task. The Phase 0 audit found the speedup rungs noisy: four repeated runs of qwen3.8-flash's delivery gave wall-time ratios 0.753, 0.740, 0.781 and 0.770 against the 0.75 rung, and a re-grade flipped `speed-0.75` with no change to the code. And v2 reports the open-ended compress item by its raw size through anchors instead of four rungs (MEASUREMENT §3), and the speedup ratio as a raw value.

**Change.**

- **Speedup** times each run by the CPU time (user and system) of the process it starts (`resource.getrusage`), not the wall time; best of three, interleaved, on one core, as before. The contract's "one process with one thread, on one CPU core" makes the two the same on a quiet machine; on a busy one only CPU time stays put. The ratio is reported as `speedupRatio`.
- **Compress** reports `compressedBytes` (the total of hidden days a and b, when both come back byte for byte; otherwise the logs' uncompressed size, 17,434,253 bytes), and the two ends of its scale, `lzmaBytes` (1,187,944) and `referenceBytes` (461,068). These are the anchors `lzma` (0) and `reference` (1) in the manifest, so the normalised value equals the old `progress` and is uncapped above the reference.
- **Manifest v2**: the card; per item one critical group; the rungs of speedup and compress in non-critical groups; compress headlined by `compressedBytes` (`primaryByItem`), its metric declared for compress only; every item dev, its own structure group.

**Self-calibration** (`logs/self-calibration-0.5.0-grader-1.6.0.log`, 66/66). One expectation changed: the `ascii-digits-only` mutant's per-row check costs about 12% more CPU time than the reference (ratio 1.12), so it stops at `speed-1.5`; under wall time it had passed `speed-1.1` by the machine's noise.

**Noise test** (`python3 private/grader.py --noise`, `logs/noise-0.5.0-grader-1.6.0-speedup.log`, PROTOCOL §9): the oracle, the DictReader variant and the strptime variant, each judged on a quiet machine and with all 20 cores busy: identical verdicts, ratios changing by 1.0%, 2.8% and 4.3% (declared tolerance 15%).

**Re-grade.** Every 0.5.0 trial of speedup and compress was re-graded under 1.6.0 (`runs/suites/20261021-123806-dev-d275/runs/E4/…`, `20261022-040520-dev-7f6a`, `20261022-050033-dev-0cdf`); v1 numbers stay under their graders.
