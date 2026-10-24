# Capability Card: E4 terminal tasks 0.5.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP2.2), for grader 1.6.0 on the unchanged task 0.5.0.

## 1. Identity

- Tier: basic for the contract items (perf, migrate, bisect, build, stockroom, pipeline, recover, codec, speedup); **compress** is an open-ended bridge reported in core engineering (TASK_LIBRARY §2). The suites run them as separate families: `E4-speedup` (basic) and `E4-compress` (core bridge).
- Capabilities: engineering.
- Protocol: `workspace-basic` with command execution, the task's files under `public/`; one session per item; fixed budget track, stated to the model: 2,000,000 tokens and one hour for speedup, 4,000,000 tokens and two hours for compress (the last v1 configurations, `experiments/e4-calibration-2026-10/speedup-0.5.eval.json` and `compress.eval.json`); the default command limits.
- Primary score: resolved for the contract items; for compress, the total compressed size of the hidden logs normalised through two anchors, uncapped.

## 2. What it measures

Terminal-style engineering on small, self-contained jobs: making a slow program fast without changing its output (speedup, perf), migrating a database atomically (migrate), finding and fixing a regression in a Git history (bisect), repairing a build (build), stockroom and pipeline fixes under hidden regressions, recovering lost Git objects (recover), writing a decoder for an undocumented format (codec), and, open-ended, writing a compressor for a log format (compress).

## 3. What it does not measure

- Large code bases or long horizons (ER and E3 do).
- Library knowledge: the Python standard library and host tools only.
- Wall-clock speed of the model: tokens and time are reported, not scored.

## 4. Where the difficulty lies

- **Contract items (basic): reliability.** Each item's contract is explicit; the work is getting every stated behaviour right, including the malformed rows, edge cases and regressions the hidden checks name. Strong models resolve most of them; speedup is near its ceiling (both dev models reached the 1.1 rung or better in v1).
- **Compress (bridge): real headroom.** LZMA at its strongest setting is the floor of the scale; reaching the reference compressor, written for this log format, needs modelling the format: field-wise coding, dictionaries of repeated values, delta coding of numbers and times, while restoring any input byte for byte, damaged lines included. In v1 deepseek-flash and qwen3.8-flash spread on it (66.7% and 83.3% of the rung scale under grader 1.5.0), and nothing caps a delivery that beats the reference.

## 5. Cheapest shortcut

- Untouched workspaces: nothing passes (each item's guards; for speedup the output checks count only once `speed-8` passes, for compress the round trips only once `ratio-50` passes).
- Compress: gzip or LZMA alone sits at or below the floor and fails the 50% gate; stashing the input for the decompressing run is defeated (it runs in a fresh copy and gets only the compressed file).
- Speedup: changing the output to gain speed fails `small`, `large` or `quirks`; the hidden days differ from the sample.

## 6. Anchors and headroom

| Item | Metric | Anchor | Maps to | Raw value | Source |
| --- | --- | --- | --- | ---: | --- |
| compress | `compressedBytes` (lower is better) | lzma | 0 | 1,187,944 | `lzma.compress(day, preset=9 \| PRESET_EXTREME)` on hidden days a and b |
| compress | | reference | 1 | 461,068 | the reference compressor `private/compress_item/packref.py` on the same days |

- Uncapped: a delivery smaller than the reference's total normalises above 1 (flagged as extrapolated). The rungs 50/80/90/97% are labels on this scale, in a non-critical group.
- Validity: both normal days must come back byte for byte and the damaged inputs too, and the size must reach 50% of the way (the contract's gate); otherwise the delivery is not resolved and its primary is 0. An invalid delivery is reported at the logs' uncompressed size (17,434,253 bytes).
- Speedup reports its raw ratio (`speedupRatio`, CPU time against the reference's, best of three) without anchors; its rungs 3/1.5/1.1/0.75 are labels in a non-critical group.

## 7. Source, licence and provenance

Project-authored tasks, data generators, reference programs and checks (`private/build_package.py`); no third-party text or code. Exposure: private to runs.

## 8. Task contract and grading

- Each item's `prompt.md` states its deliverables and hidden checks; graders run every delivered program in the sandbox on hidden inputs.
- Score model: one critical group per item (rule fraction) over its contract checks; for speedup the critical group is `small`, `large`, `quirks` and `speed-8`, with `speed-3`…`speed-0.75` in `speedup-rungs`; for compress the critical group is `roundtrip` and `roundtrip-quirks`, with `ratio-50`…`ratio-97` in `compress-rungs` and the metric group `compress-size`. `primaryByItem` makes compress metric-primary.
- **Timing (grader 1.6.0).** Speedup times each run by the CPU time (user and system) of the process it starts, not by wall time, so a busy machine does not change a verdict (PROTOCOL §9). The contract's "one process with one thread, on one CPU core" makes the two the same on a quiet machine.
- Equivalent solutions: any program in the allowed runtime; only outputs and measured sizes count.

## 9. Splits and size

- Every item is its own task and structure group (`item:<id>`), all dev: each has been run or inspected. Basic tier: no validation or holdout. Compress, a single task, is a bridge for linking releases, not a discriminating family on its own (one structure group, no interval).

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: each item's oracle passes its checks (speedup's oracle short of the 0.75 rung by design); the compress oracle normalises to 1 | `python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.5.0-grader-1.6.0.log` |
| Null agent | pass: untouched workspaces pass nothing | self-calibration; the suite smokes |
| Mutants | pass: per item (speedup: seven, compress: eight) | self-calibration |
| Alternative valid solutions | pass: compress without each modelling step passes fewer rungs, still valid | self-calibration |
| Adversarial | pass: compress stash and peeking defeated | self-calibration |
| Success audit | speedup: three false passes found (Phase 0) and fixed by grader 1.5.0 | `docs/audits/E4-speedup/2026-10-24.md` |
| Noise | speedup: the same deliveries judged on a quiet machine and with every core busy give identical verdicts; ratio change within the declared tolerance (15%) | `logs/noise-0.5.0-grader-1.6.0-speedup.log` |
| Determinism | pass for everything but timing; compress sizes are exact | self-calibration |

## 11. Budget

Speedup 2,000,000 tokens, compress 4,000,000 tokens (the v1 dev configurations); compress uses its whole budget by design (open-ended). The other contract items have no current configuration and are in no suite.

## 12. History

- 0.1.0–0.5.0 and grader 1.5.0: see `calibration.md`.
- Grader 1.6.0 (2026-10-24): manifest v2; speedup timed by CPU time with its raw ratio reported; compress headlined by its compressed size through the LZMA and reference anchors. Every 0.5.0 trial re-graded.
