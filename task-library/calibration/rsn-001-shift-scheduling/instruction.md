# Task: Check Scheduling Constraints and Provide Verifiable Evidence (rsn-001)

Answer the three independent instances A, B, and C in public/instances.json. Use only the data supplied for each instance. people and days provide context; all other available fields describe hard constraints that must be satisfied together.

## Definitions

- coverage: schedule exactly daily_need distinct people each day.
- per_person_max: no person may be scheduled on more days this week than the given maximum.
- availability: people listed in unavailable must not be scheduled.
- Feasibility: an assignment exists that satisfies every supplied hard constraint.
- A minimal unsatisfiable subset (MUS) is a constraint subset that is itself infeasible and becomes feasible after removing any one member. Context fields are not constraints.

## Output

Emit one JSON object only. Include A, B, and C. Do not use Markdown fences.

    {
      "A": {"feasible": false, "conflict_set": ["<constraint name>"], "reasoning": "<brief basis>"},
      "B": {"gap": "<missing parameter>", "clarify": true, "clarificationTarget": "daily_need", "question": "<specific clarification question>"},
      "C": {"feasible": true, "schedule": {"0": ["<person name>"], "...": []}, "reasoning": "<brief basis>"}
    }

For every infeasible case, provide a MUS. If a required parameter is missing, either ask for it explicitly or give conditional conclusions that are correct for reasonable values. Feasible instances require a complete day-by-day witness. Field names, person names, and day keys must match the input.

Automated checks validate conclusions, conflict sets or conditional branches, and witnesses. The reasoning field is for later human review; do not expose hidden chain-of-thought.
