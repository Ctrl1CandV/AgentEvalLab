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
| AHC039 | a tiny square (valid, worthless) | 634.5 of 583 | 723 |
| AHC039 | a 30-line best rectangle of grid cells | 239 of 583 | 1,547 |
| AHC015 | always tilting forward | 625 of 657 | 828 |

The grid solution already beats about 60% of the contestants. Short contests rank many beginners, so the share of contestants beaten crowds strong programs together at the top. The score therefore uses performance, which stretches the top.

**Judge settings.**

- The time limit gets 10% plus 0.1 s of grace, against ALE-Bench's strict wall time inside Docker.
- Cases run four at a time, under a lock that allows one judgement at a time on the machine.
- This machine (Intel i7-13650HX) is probably faster per core than AtCoder's judge. The difference favours the model slightly against the human standings; it is the same for every model.
