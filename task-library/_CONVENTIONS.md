# Calibration Package Conventions

A calibration package contains a manifest, public instruction and fixtures, evaluator-side grader and private cases, environment notes, a rubric, and a calibration record.

## Rules

- Keep public and trusted file lists explicit.
- Hash every file that affects a run or score.
- Keep grader output machine-readable and bounded.
- Use stable requirement and check IDs.
- Include multiple valid references where implementation flexibility is intended.
- Include targeted mutations for important failure modes.
- Record exact commands, runtime versions, exit codes, and logs.
- Do not treat a successful offline calibration as a model score.
