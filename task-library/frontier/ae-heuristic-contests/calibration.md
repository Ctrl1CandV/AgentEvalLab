# Calibration Record: Algorithm Engineering (AE)

## Version 0.1.0 (2026-10-23)

**Why.** By the user's decision (2026-10-23), new families must have a ceiling far above today's models and come from open sources (`docs/design/FRONTIER_TASKS.md`).

AtCoder Heuristic Contest problems have no reachable optimum. ALE-Bench ships, for each problem:

- the official statement and tools;
- the system-test seeds;
- the full human standings.

So a program can be ranked against hundreds of contestants. ALE-Bench reports frontier models at about 600–1,100 performance one-shot and about 1,800–2,200 with a purpose-built iterative agent.

**Items.** Ten four-hour contests with absolute scores:

| Kind | Problems |
| --- | --- |
| batch | AHC026, 028, 032, 039, 041, 042, 044, 046 |
| reactive | AHC015, 035 |

Each has 100–200 private cases and 494–933 ranked contestants.

**Feasibility, checked by hand before the build.**

- The official Rust tools build with cargo 1.99 into this machine's binaries, 0.5–1.1 MB each.
- The private seeds are the contest's system tests: AHC015's winner scored 161,011,437 over 200 cases.
- Solutions run in the bubblewrap sandbox, and the reactive tester drives them interactively.

Simple solutions land low on the scale:

| Problem | Solution | Rank | Performance |
| --- | --- | --- | ---: |
| AHC039 | a tiny square (valid, worthless) | 634.5 (performance rank) of 682 contestants | 723 |
| AHC039 | a 30-line best rectangle of grid cells | 239 of 682 | 1,547 |
| AHC015 | always tilting forward | 625 of 778 | 828 |

The grid solution already beats about 60% of the contestants. Short contests rank many beginners, so the share of contestants beaten crowds strong programs together at the top. The score therefore uses performance, which stretches the top.

**Judge settings.**

- The time limit gets 10% plus 0.1 s of grace, against ALE-Bench's strict wall time inside Docker.
- Cases run four at a time, under a lock that allows one judgement at a time on the machine.
- This machine (Intel i7-13650HX) is probably faster per core than AtCoder's judge. The difference favours the model slightly against the human standings; it is the same for every model.

*Correction (2026-10-24, with 0.2.0):* the table above first gave the number of contestants as the number of rows of the standings file (583 for AHC039, 657 for AHC015), which merges tied ranks. The judge counts contestants by the last rank, 682 and 778. The ranks and performances were right.

## Version 0.2.0 (2026-10-24)

**Why.** PLAN-007 (the v2 restructure, `docs/design/v2/`): the 0.1.0 score was a share of rungs that capped at 3,200, so it could not show progress beyond the winners' level, and the raw performance was only in the evidence. v2 reports raw values first (MEASUREMENT §3).

**Changes.**

- Manifest v2: tier frontier, capability engineering, the capability card `card.md`, the score model (a critical `accepted` check, the normalised performance as the primary, rungs dropped), splits and provenance per item.
- Grader 2.0.0 reports `performance` (uncapped: above the winner's total it extends the winner's performance along the top of the table, flagged), `total` and `performanceRank`.
- Naive references for every problem (`private/references/`), judged by `private/anchors.py` into `private/anchors.json`:

| Item | Split | Naive reference | Naive | Median contestant | Winner |
| --- | --- | --- | ---: | ---: | ---: |
| ahc015 | dev | always tilt forward | 472 | 1,243 | 3,506 |
| ahc026 | validation | carry out in order, move the boxes above to the next stack | 611 | 1,354 | 3,451 |
| ahc028 | validation | type every string in turn on the nearest keys | 805 | 1,325 | 3,512 |
| ahc032 | validation | press no stamp | 495 | 1,302 | 3,529 |
| ahc035 | dev | plant seeds 0 to N²−1 every turn | 439 | 1,286 | 3,471 |
| ahc039 | dev | a tiny square | 723 | 1,336 | 3,390 |
| ahc041 | validation | every vertex its own root | 444 | 1,341 | 3,467 |
| ahc042 | validation | the statement's hint, one Oni at a time | 987 | 1,300 | 3,475 |
| ahc044 | validation | hand the duty round in a circle | 713 | 1,288 | 3,478 |
| ahc046 | dev | single moves only | 638 | 1,333 | 3,523 |

  (AHC015's always-forward program measures 472 here (rank 744) against 828 (rank 625) in the 0.1.0 table above. That table records the hand check made before the 0.1.0 build; the built judge on the private cases places this program below 600, as the 0.1.0 self-calibration already required. `anchors.json` is the judge's value, and the self-calibration checks that the reference reproduces it.)
- Splits by contest: dev AHC015, 035, 039, 046 (calibrated by hand, named in the dev plan); validation the six others.
- The instruction states the new scale.

**Self-calibration** (`logs/self-calibration-0.2.0.log`): every naive reference reproduces its anchor; the 0.1.0 scenarios (bands of the grid, flavour and seed references, Python, tampering, peeking, spinning, compile errors, illegal output, no solution, a busy machine) still hold; the performance rises above the winner and is flagged.

## Grader 2.1.0 (2026-10-24, task 0.2.0 unchanged, PLAN-007 WP3.5)

**References for every problem** (TASK_LIBRARY §3.6): a greedy reference for each of the ten problems, beside the naive one (`private/references/<item>/`). New: AHC026 (move the blocking boxes onto the stack whose smallest box is largest), AHC028 (greedy maximal-overlap text, typed by a dynamic programme over the keys), AHC032 (the best single press while one helps), AHC041 (trees grown depth-first from the least beautiful roots), AHC042 (the cheapest safe removal, shifting back only when needed), AHC044 (hand-offs of half the turns to the least covered employees), AHC046 (shortest moves and slides on the empty rink). The 0.1.0 references keep their roles (AHC015 tilt by flavour, AHC035 highest-value seeds, AHC039 best grid rectangle).

**Fresh seeds.** Each delivery is also judged on 50 seeds of our own (`private/problems/<item>/fresh_seeds.txt`, drawn from `ae-fresh:<item>`), with the official generator and tester and the same rules. `freshTotal` is reported separately, normalised through the naive (0) and greedy (1) references' totals on those seeds, and is never ranked against the humans: it separates generalisation from recall of the public seeds.

| Item | Naive perf. | Greedy perf. | Median | Winner | Fresh naive | Fresh greedy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ahc015 | 472 | 937 | 1243 | 3506 | 7,301,859 | 12,154,287 |
| ahc026 | 611 | 1213 | 1354 | 3451 | 405,762 | 452,297 |
| ahc028 | 805 | 1557 | 1325 | 3512 | 284,490 | 348,769 |
| ahc032 | 495 | 918 | 1302 | 3529 | 2,037,320,860,481 | 3,138,263,567,782 |
| ahc035 | 439 | 909 | 1286 | 3471 | 23,195,510 | 34,513,193 |
| ahc039 | 723 | 1547 | 1336 | 3390 | 100 | 94,982 |
| ahc041 | 444 | 1698 | 1341 | 3467 | 2,531,717 | 23,617,371 |
| ahc042 | 987 | 1429 | 1300 | 3475 | 136,972 | 152,222 |
| ahc044 | 713 | 1774 | 1288 | 3478 | 37,537,324 | 48,789,028 |
| ahc046 | 638 | 1119 | 1333 | 3523 | 56,076 | 68,193 |

Greedy references reach 909–1,774, below the median on six problems and above it on four (AHC028, 039, 041, 044), and far below every winner (3,390–3,529): the scale keeps its headroom. Writing the six validation problems' greedy references meant reading their statements, as their naive references already had (card §9); nothing about the tasks or the grading was tuned on them.

**Self-calibration** (`logs/self-calibration-0.2.0-grader-2.1.0.log`): every naive and greedy reference reproduces its performance and fresh total, the greedy above the naive on both seed sets; the 0.2.0 scenarios still hold.
