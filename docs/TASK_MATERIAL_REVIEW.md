# Task Material Review

Review each task as a contract, not as a preferred implementation.

## Required checks

1. **Purpose:** The user goal and expected deliverables are concrete.
2. **Inputs:** Files, schemas, data, and assumptions are available and versioned.
3. **Requirements:** Each requirement has a stable ID and a clear pass, fail, or unknown outcome.
4. **Ambiguity:** Unspecified choices are either explicitly allowed or resolved before calibration.
5. **Coverage:** Public examples cover the main workflow; private cases cover meaningful boundary conditions.
6. **Legitimate alternatives:** Valid implementations are not rejected for using a different internal design.
7. **Failure sensitivity:** Targeted mutations demonstrate that important defects are detected.
8. **Exposure:** Private fixtures and grader logic are excluded from the candidate projection.
9. **Reproducibility:** Runtime, dependencies, commands, hashes, and calibration outcomes are recorded.
10. **Human review:** Subjective judgments remain separate from automatic checks and retain cited evidence.

## Decision record

Record the task version, reviewer, date, findings, required changes, and promotion decision. Any change to a public contract, private fixture, or grader requires updated hashes and a new calibration entry.
