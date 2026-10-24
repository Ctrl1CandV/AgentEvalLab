# Task: Shift Roster (R1)

Decide whether the roster instance below can be staffed under all its rules. If it can, give one valid roster. If it cannot, name a minimal conflict set. The instance follows from the text alone; the workspace contains no further material.

A minimal conflict set is a set of optional rules (not coverage) that cannot hold together with coverage, while dropping any one of them leaves a set that can. There may be more than one; any one is accepted.

## Answer

Emit one JSON object only, without Markdown fences. If the instance can be staffed:

    {"feasible": true, "roster": {"Day 1": {"<shift>": ["<person>", ...], ...}, "Day 2": {...}, ...}}

Give every day and every shift, each with exactly the required number of people.

If it cannot be staffed:

    {"feasible": false, "conflict": ["<rule>", ...]}

Use the rule names as written in the instance, for example `max_shifts`.

## Grading

- **Feasible instance:** coverage and each optional rule are checked against your roster. The optional rules count only when every shift is fully staffed.
- **Infeasible instance:** the verdict and the conflict set are checked.
