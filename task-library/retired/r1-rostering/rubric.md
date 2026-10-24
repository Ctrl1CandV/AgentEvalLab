# Rubric: R1 Shift Roster

Each item is one generated instance. Levels grow in people, days, shifts per day, staff per shift, and the number of optional rules:

| Level | People | Days | Shifts per day | Staff per shift | Optional rules |
| --- | --- | --- | --- | --- | --- |
| L1 | 4 | 4 | 2 | 1 | 3 |
| L2 | 5 | 5 | 2 | 1 | 4 |
| L3 | 6 | 6 | 2 | 2 | 5 |
| L4 | 7 | 7 | 3 | 2 | 6 |

Half of each level's items are feasible and half are not. Every infeasible item's smallest conflict involves at least two rules.

## Checks

- **Feasible items:** one critical check for coverage, and one per optional rule. A rule check passes only if the roster staffs every shift with the required number of people and satisfies that rule. The score is the fraction passed. A wrong verdict yields no roster, so every check fails.
- **Infeasible items:** two critical checks.
  - `verdict` passes when the answer says the instance is infeasible.
  - `conflict` passes when the named rules are a minimal conflict set. The solver checks that they cannot hold together with coverage, and that dropping any one of them leaves a set that can. Any minimal conflict set is accepted.
- **`answer-format` (non-critical).** It passes when the answer is one JSON object, as instructed. An answer that is not one JSON object is recovered when exactly one JSON object can be found in it: the only fenced code block that holds one, or else the only top-level object in surrounding prose. A recovered answer is graded on its content and loses 20% of its score. An answer with no candidate, or with several, fails every check.

## Not scored

Explanations, roster fairness beyond the rules, and key order are not scored.
