# Frontier Tasks: High-Ceiling Families from Open Sources

Status: **superseded** on 2026-10-24 by the v2 restructure (`docs/design/v2/`, PLAN-007). Kept as history. Two corrections, from the third-party review of 2026-10-24:

- AE no longer scores the share of contestants beaten. Since 0.1.0 it scores AtCoder performance in rungs from 600 to 3,200. v2 reports raw performance, uncapped.
- "Agents carry out any specified procedure exactly" overstates the evidence. The evidence shows these models reliably carried out the procedures we tested, under our tools and budgets.

Originally: draft, 2026-10-23, decided by the user on 2026-10-23.

## Why

Three hardening rounds added rules, dimensions, couplings and branches to our own task families (T1, T2, E3). deepseek-flash and qwen3.8-flash still scored 94–100% on every fully specified procedure. Agents that read rules, write scripts, query state and check their work carried out the procedures we tested reliably, under our tools and budgets (the draft said "any specified procedure exactly", which overstates the evidence; see the corrections above). More rules make a task longer, not harder.

Our tasks spread models in only two ways:

- deep combinatorial reasoning (R3);
- open-ended optimisation that cannot be brute-forced (E2, E4, the T2 0.3.0 payment plan).

Even there, the best plan known was within reach of a short annealing run.

The user's direction (2026-10-23):

- choose tasks whose ceiling is high in themselves, so that future models do not saturate them quickly;
- take them from open-source projects on GitHub;
- raise the token quota more than tenfold.

## Principles

1. **A ceiling far above today's models.** The scale is anchored to human experts or to the full behaviour of real software, never to a "best known" that a short search reaches.
2. **Real material under a usable licence.** Statements, tools, code and tests come from open projects and are used unmodified where the licence requires it. Every source is recorded in the manifest with its licence and attribution.
3. **Deterministic, attributable grading.** Scores come from official scorers or the projects' own tests, run in our sandbox. No speed-based scores: wall-clock speedups are not reproducible across machines (Are Performance-Optimization Benchmarks Reliably Measuring Coding Agents?, 2026). Where a time limit decides quality, the grader runs alone with fixed parallelism, and its noise is measured.
4. **Sufficient budgets.** Long horizons and generous budgets are part of the design. Efficiency is reported, not scored.
5. **Contamination is acknowledged.** Public problems and libraries may be in training data. We prefer material where recall does not substitute for work: a heuristic contest's best ideas are known, yet only careful engineering scores well. We record the dates of every source.

## Family AE: algorithm engineering (ALE-Bench)

**Source.** ALE-Bench (Sakana AI with AtCoder, NeurIPS 2025 D&B), 38 AtCoder Heuristic Contest problems.

- Data on Hugging Face (`SakanaAI/ALE-Bench`), CC BY-ND 4.0, officially provided by AtCoder.
- Code on GitHub, Apache-2.0.
- Each problem has:
  - the statement (English and Japanese, with images);
  - the official tools as Rust source: a generator, a scorer, and an interactive tester for reactive problems;
  - 50 public seeds, plus the private seeds of the system test;
  - the final human standings on those private seeds (460–1,217 contestants);
  - AtCoder's rank-to-performance table.

The problems are NP-hard routing, scheduling, packing and puzzle problems with no reachable optimum. Contestants refine for hours (short contests, 4 h) or weeks (long contests, 200–367 h).

**Task.**

- The model receives:
  - the statement, unmodified;
  - compiled official tools: generator, scorer and tester;
  - the public inputs;
  - a helper that runs a solution on them under the time limit.
- It writes a C++ (g++ 11, `-O2 -std=gnu++20`) or Python solution and may iterate as long as its budget allows.

**Grading.**

- The grader compiles the solution in the sandbox and runs it on the private seeds under the problem's time limit, at fixed parallelism with nothing else running.
- It scores each case with the official tool and sums the scores as AtCoder did.
- The total is ranked among the human standings, and the rank is mapped to AtCoder's performance.
- *As drafted:* the item score was to be the share of human contestants the solution beats, in rungs every 5%. *As built (0.1.0):* AtCoder performance in 27 rungs from 600 to 3,200, which a percentile tops out too early to show; v2 (AE 0.2.0) reports the raw performance, uncapped.

**Ceiling.**

- Reference results on the human scale: the median contestant scores 1,150–1,430 in AtCoder performance, the winner about 3,500.
- ALE-Bench reports frontier models at about 600–1,100 one-shot and 1,800–2,200 with a purpose-built iterative agent; that agent once won a contest outright.
- Our models should land well inside the human range, with room above.

**Licence handling.** Statements and tool sources are used unmodified. Compiling the tools is a format shift, which CC BY-ND 4.0 permits. The repository is private and the material is not redistributed.

**Calibration.**

- **Machine speed against AtCoder:** run reference solutions near the time limit.
- **Noise:** rerun one solution several times and record the spread of its rank.
- **Anchors:** a trivial and a greedy reference solution per problem, which must land low and in the middle.
- **Integrity:** the solution may not read private inputs, and the scorer's output is not exposed.

## Family LR: library rebuild (Commit0)

**Source.** Commit0 (Cornell and Cohere, ICLR 2025), MIT. Its 54 Python libraries have their implementations erased behind kept signatures and docstrings. The task is to rebuild them against their documentation and unit tests. Each library keeps its own licence (MIT, BSD or Apache).

**Task.**

- The model receives the stubbed repository, the library's documentation, and part of its test suite.
- It implements the library.

**Grading.** The grader runs the full original test suite in the sandbox; the item score is the share of tests that pass. The paper reports 6% for the best model on all libraries and 29% on the lite set, so the ceiling is high.

**Selection.** Libraries with pure-Python dependencies only, since there is no network and no apt. Mid-popularity libraries are preferred, to limit recall. The dependencies are vendored as wheels into a read-only runtime directory outside the workspace.

**Harness work.**

- A per-package runtime directory, mounted read-only and put on the path.
- Long test runs in the grader.

## Later candidates

- **Repository maintenance with hidden tests**, from commits after the models' training cutoffs (SWE-style).
- **Arenas** (CodeClash): code that competes against a fixed ladder of open-source bots, if the engines can run on this machine without Go or Java.

## What happens to the existing families

T1, T2, E3, R3 and the rest become the **basic tier**. They test exact procedure-following, format, long-horizon consistency and planning at a lower cost. The rating keeps them, but the new families carry the spread. They are not hardened further.

## Budgets

- Each AE item gets 4–8 hours and about 20–40M tokens, so that iteration is possible.
- An LR item gets similar or more.
- Dev rounds stay at deepseek-flash plus about two references and one repetition. With the user's tenfold quota, a two-family pilot on four items each costs on the order of 300–500M tokens at most.
