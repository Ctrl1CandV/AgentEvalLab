# Evaluation Specification

## Purpose

Compare model behavior on a small, traceable set of tasks under a fixed Pi Agent harness. Report task outcomes, evidence, delivery status, runtime, and usage. Conclusions apply only to the tested conditions.

## Scope

The maintained dimensions are engineering, structured reasoning, tool use, and frontend implementation. Runtime, model requests, tool attempts, resource limits, cleanup, and accepted delivery are reported separately.


## Stable constraints

1. Pin task versions, model identifiers, tool profiles, prompts, budgets, and relevant environment details.
2. Give candidates only the public task projection. Keep trusted graders, answer keys, hidden fixtures, and scoring evidence evaluator-side.
3. Treat model outputs and tool traces as untrusted input. Validate schemas and paths at every boundary.
4. Keep objective checks separate from human review. Pending review is not a failure or a zero score.
5. Preserve per-trial results, artifacts, hashes, and append-only score runs.
6. Report missing or partial usage as unknown, not zero.
7. Keep task families and tested conditions visible. Do not combine unlike dimensions into one score.
8. Do not call external model APIs without an explicit model, request limit, and batch budget.

## Evidence limits

Reference runs and mutation checks show whether a grader accepts known implementations and rejects selected defects. They do not establish difficulty, discrimination, construct validity, real-provider behavior, or broad generalization.
