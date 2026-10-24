# Capability Card: <family id> <version>

Fill this in before building anything beyond a feasibility check. It lives in the package as `card.md` and is hashed with the manifest. Rules: `docs/design/v2/README.md` §3 and `TASK_LIBRARY.md` §4.

## 1. Identity

- Tier: basic / core / frontier
- Capabilities: primary first (engineering, reasoning, agentic, visual)
- Protocol(s): tools, context policy, budget track, command limits
- Primary score: resolved / metric `<id>` / rating

## 2. What it measures

One paragraph: the ability the task needs, stated as behaviour, e.g. "locating the cause of a reported failure in an unfamiliar repository and changing it without regressions".

## 3. What it does not measure

What a reader might assume but the task does not test: speed, knowledge of a library, aesthetic quality, and so on.

## 4. Where the difficulty lies

The specific bottleneck a strong model must overcome. It must not be length, the number of rules, hidden requirements, ambiguity, format or harness limits. If this section cannot be written concretely, stop.

## 5. Cheapest shortcut

- The cheapest way to score well without the measured ability: brute force, a generic solver, recall of a public answer, editing the tests, exploiting the tool, guessing.
- How the task resists it.
- The shortcut's offline score.

## 6. Anchors and headroom

- Anchors, with their source, date and method: naive, baseline, strong, bound or human.
- The offline scores of the naive and strong strategies. A real gap must show here.
- Why the top is not reachable by a short generic search.

## 7. Source, licence and provenance

- Source, its licence, attribution, and the dates of its material.
- Exposure: public, private-to-runs or generated. Contamination risk, and how it is flagged per model.

## 8. Task contract and grading

- What the model receives and what it must deliver.
- The behaviour groups, with weights and the critical flag. The checks of each group, and the public requirement each check traces to.
- Equivalent solutions that must be accepted.
- The resolved criterion.

## 9. Splits and size

- Structure groups.
- dev / validation / holdout counts.
- The split rule.

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | | |
| Null agent | | |
| Mutants | | |
| Alternative valid solutions | | |
| Adversarial | | |
| Coverage invariant | | |
| Global end state | | |
| Noise | | |
| Determinism | | |

## 11. Budget

- Budget curve: levels, results, the chosen B, and the date frozen.

## 12. History

- Versions, with what changed and why.
- Audit results.
