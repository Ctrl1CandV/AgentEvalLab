# Public Scoring Rubric: rsn-001

Score by requirement, not by number of tests. Failure of a hard gate sets that instance's primary score to zero. Explanation quality is a secondary human-reviewed dimension.

## Automated hard gates

| Instance | Required result |
| --- | --- |
| A | feasible=false and conflict_set exactly matches one enumerated minimal unsatisfiable subset (MUS). Set order is ignored; missing, extra, or redundant constraints fail. |
| B | identify gap=daily_need and either ask a non-empty question targeting daily_need, or give two conditional branches with correct conclusions. Silently choosing one interpretation fails. A reviewer judges whether the question is specific and relevant. |
| C | feasible=true and schedule is a valid witness satisfying every constraint. |

## Human review

Review whether the basis is correct and concise. For A, explain why removing any member makes the set feasible. For B, judge whether the clarification question addresses the missing information; conditional answers must cover both interpretations. For C, review readability of the witness.

## Acceptable answers

Different valid MUS reasoning methods, valid schedule witnesses, and either clarification or correct conditional branches are accepted. The checker does not require a particular proof text, ordering, or schedule.

## Not scored

Soft constraints, optimality, hidden chain-of-thought, and answer length are not scored.


## Trial score and answer format

The trial score is the fraction of content checks passed, which gives partial credit. The trial is resolved when every critical check passes. The answer must be one JSON object, as the instruction says. If the answer is not one JSON object, it is recovered when exactly one JSON object can be found in it: the only fenced code block that holds one, or else the only top-level object in surrounding prose. With no candidate, or with several, nothing is recovered. A recovered answer is graded on its content, fails the non-critical `answer-format` check, and loses 20% of its score. An answer that cannot be parsed fails every content check.
