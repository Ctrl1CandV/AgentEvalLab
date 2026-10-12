# Candidate Task Card: tool-001 Document Evidence Recovery

- ID: `tool-001-doc-evidence-recovery`
- Primary capability: tool use and evidence-based answering
- Task: inspect a fixed synthetic project snapshot, recover requested facts across paginated files, respect access constraints, and recover from tool errors.
- Tool profile: bounded `list`, `read`, and `search`; reads use zero-based Unicode code-point offsets.
- The grader requires the final answer to be supported by actual returned evidence and checks attempts, interceptions, and executions.
- Limits: no live model API run; a single trace cannot establish that additional tools reduce rework or cause better outcomes.
