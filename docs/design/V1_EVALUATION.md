# Version 1 Evaluation Design

## Objective

Build a narrow, reproducible evaluation workflow for selected engineering, reasoning, tool-use, and frontend tasks under Pi Agent. Preserve enough evidence to explain each result and rerun a grader without rerunning a candidate.

The first version supports task-level comparisons. It does not claim to measure general intelligence, overall productivity, or a universal ranking.

## Dimensions and reports

| Dimension | Evidence | Scoring |
| --- | --- | --- |
| Engineering | Task artifacts, trusted grader checks, execution events | Objective checks by requirement |
| Reasoning | Structured answers, certificates, counterexamples, or witnesses | Objective checks where defined; otherwise human review remains pending |
| Tool use | Tool attempts, evidence trace, and task result | Task-level evidence and execution metrics |
| Frontend | Rendered page, behavior, accessibility checks, screenshots | Objective behavior checks plus human visual review |

Runtime, request usage, tool counts, timeout, cleanup, and accepted delivery are independent measures. They are not combined into a single weighted score.

## Run conditions

Each plan pins the model provider and ID, task package and manifest hash, tool profile, prompt, budget, and execution policy. Record environment details and package versions where they affect results. Use one independent trial per model and case unless a task explicitly requires a continuous session.

Candidate, probe, and evaluator activity are labeled separately in usage records. Missing usage remains unknown. Validation-only preflight checks plans without loading credentials or sending requests.

## Task packages and scoring

A package separates public instructions and fixtures from trusted grader code and private fixtures. The manifest names the task family, version, requirements, file hashes, runtime, and grader entry point.

The grader receives a frozen artifact snapshot and a bounded request. Its output is schema-validated and linked to the source trial. Grader error, resource limit, pending review, and candidate failure are distinct states. Regrading appends a new score run against the original snapshot.

## Continuous engineering tasks

The continuous task uses one project and one agent session across five stages. Each stage reveals only its current requirements. Public checks run against temporary copies; private grading uses immutable artifacts. Stage budgets, repair attempts, regressions, retention, and final delivery are reported explicitly.

## Calibration and limits

Reference implementations test acceptance. Mutation variants test selected failure detection. Repeated deterministic runs test grader stability. These checks do not demonstrate real-model difficulty or provider compatibility.

An authorized pilot should record exact model versions, conditions, request and cost caps, per-task outcomes, incomplete runs, and deviations. Human review must retain its own rubric and evidence; it is not represented as an automatic score.
