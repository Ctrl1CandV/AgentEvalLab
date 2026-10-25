# Capability Card: E3 long-cycle maintenance (eng-005) 0.5.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP2.2), for grader 2.4.0 on the unchanged task 0.5.0; updated 2026-10-25 for grader 2.5.0 (speed not scored).

## 1. Identity

- Tier: basic (a long-horizon consistency check).
- Capabilities: engineering.
- Protocol: a trajectory of seven stages on one repository (the pinned baseline), one session per stage (`contextPolicy: per-stage`, user decision 2026-10-23); `workspace-basic` or `workspace-augmented`; one public-checker repair per stage; fixed budget track, 5,000,000 tokens per stage and 25,000,000 per trajectory (user decision 2026-10-23), stated to the model.
- Primary score: resolved (every correctness check of the final stage passes on the final snapshot). The trajectory is one task.

## 2. What it measures

Keeping a TypeScript work-order CLI correct while it grows over seven requests: filtering, sorting and pagination (S1); a dependency graph with cycle and prerequisite rules (S2); atomic rejection (S3); a v1→v2 store migration with events (S4); a unified error protocol and documentation (S5); a 100,000-order store fast enough against a reference (S6); and a crew planning command (S7). Each stage is graded on everything released so far, so a later change that breaks an earlier behaviour shows.

## 3. What it does not measure

- One-shot implementation from a full specification (E2): the requirements arrive one stage at a time.
- Large-repository navigation: the code base is small.
- Speed: S6's speed rungs are measured and reported, not scored (grader 2.5.0). S7's plan quality is a ladder in the diagnostic, not the headline.

## 4. Where the difficulty lies

Reliability over a long horizon. No stage is hard on its own; the work is not regressing: a faster write path in S6 that corrupts the store after two writes (deepseek-flash, per-stage pilot), new fields that earlier commands must keep (S7), a migration that must stay idempotent. With 5M tokens per stage both dev models completed every correctness requirement (deepseek-flash 90%, qwen3.8-flash 94–95% of the v1 score, losing only top speed rungs and one field check), so E3 is saturated for strong models and stays in the basic tier.

## 5. Cheapest shortcut

- An untouched baseline: earns nothing (the base and seed checks guard against regressions and count only with a stage's own check).
- Editing the public checkers or writing self-tests: the hidden grader ignores candidate tests and runs the pinned checker.
- Late repair: each snapshot is graded on its own; the final snapshot is the task's outcome, earlier ones are evidence.

## 6. Anchors and headroom

No anchors for the headline (contract task). Raw diagnostics (grader 2.4.0): `scaleSpeedRatio`, the CPU time of S6's workload against the reference's (rungs 3, 1.5, 1.1, 0.75 are labels), and `planQuality`, the plans' mean place between the naive (0), greedy (0.5) and best known (1) plans (rungs 25–97% are labels).

## 7. Source, licence and provenance

Project-authored baseline (`baseline.bundle`), stage briefs, public checkers, references (`references/ref-a`, `ref-b`) and hidden grader. Exposure: private to runs.

## 8. Task contract and grading

- Each stage releases its brief and public checker; the hidden grader runs the requirements active so far on each snapshot.
- Score model (grader 2.5.0, user decision of 2026-10-25): `correctness` (weight 0.5, rule fraction, critical) over every check of BASE_CLI … PLAN, the completion; `plan-rungs` (weight 0.5, not critical), the quality; speed is not scored: its rungs sit in `speed-rungs`, a group of weight 0, reported in every outcome and scored nowhere. The headline is resolved (MEASUREMENT §2, basic tier), read on the final stage's snapshot; if Phase 4 shows the headline too high, completion and quality enter it (to be decided on that evidence).
- **Timing (grader 2.4.0).** S6's workload is timed by the CPU time of every command it starts, the candidate's and the reference's alike, best of three; S7's 10-second limit has been CPU time since grader 2.3.0. Wall time is only a hard stop (30 s per command).
- Equivalent solutions: two structurally different references pass every stage.

## 9. Splits and size

One task (a trajectory): split dev, structure group `package:eng-005`. Basic tier: no validation or holdout.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: ref-a and ref-b through all seven stages | `run-calibration.mjs`, `logs/acceptance-self-calibration.json`; `tests/trajectory.test.ts` |
| Null agent | pass: the untouched baseline earns nothing at every stage | self-calibration; the basic suite smoke (14 snapshots) |
| Mutants | pass: late repair, lost migration data, a query regression in S4 | self-calibration |
| Alternative valid solutions | pass: two references | self-calibration |
| Adversarial | pass: tampered checker copies and fabricated self-tests change nothing | self-calibration |
| Success audit | one false fail (grading noise), fixed by grader 2.3.0 | `docs/audits/E3/2026-10-24.md` |
| Noise | S6: both references judged quiet and with every core busy | `logs/noise-0.5.0-grader-2.4.0-s6.log` |
| Determinism | pass apart from timing, which the noise gate bounds | — |

## 11. Budget

5,000,000 tokens per stage, 25,000,000 per trajectory (user decision 2026-10-23); S6 and S7 use their whole stage budget by design.

## 12. History

- 0.2.0–0.5.0 and graders up to 2.3.0: see `calibration.md`.
- Grader 2.4.0 (2026-10-24): S6 timed by CPU time; raw `scaleSpeedRatio` and `planQuality`; manifest v2 with this card. The final snapshot of every 0.5.0 trajectory re-graded.
- Grader 2.5.0 (2026-10-25): speed no longer scored; the diagnostic is half completion, half plan quality. Checks unchanged; every 0.5.0 trajectory re-graded.
