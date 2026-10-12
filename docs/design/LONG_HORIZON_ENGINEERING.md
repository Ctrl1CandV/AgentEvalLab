# Long-Horizon Engineering Task

## Purpose

Measure how an agent handles a sequence of related maintenance requests in one project and one continuous session. The stages observe implementation, feedback repair, regression control, persistence, and delivery. Each stage has its own requirements and budget.

## Stage contract

- The baseline repository and project brief define the initial state.
- Each stage reveals only its own new requirements and current feedback.
- The same workspace and agent session continue across stages.
- Stage-specific public checks run against a disposable snapshot.
- Private grading runs against the preserved artifact snapshot.
- At most one public-feedback repair cycle is allowed per stage.
- A failure or budget stop is recorded; it does not silently advance to a passing state.

## Recorded measures

- Stage completion and stop reason
- Requirement status after each cycle
- New requirements completed
- Regressions from previously passing requirements
- Repair prompts and repaired requirements
- Snapshot hashes and restore outcomes
- Final accepted delivery
- Aggregate and per-stage runtime and request usage

Requirements without a valid judgment remain unknown rather than being counted as failures or passes.

## Reliability checks

The package calibration includes two distinct valid reference implementations and targeted mutations for lost data, regression, malformed output, and incorrect state transitions. Public checkers must not reveal later-stage requirements or mutate stored snapshots.

A successful offline replay establishes only that the harness and grader handle the tested traces. It does not establish real-agent performance, context-limit behavior, or cost.
