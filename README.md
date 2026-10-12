# Pi Evaluation Harness

A TypeScript evaluation harness built on Pi Agent. It runs fixed model configurations against versioned engineering, reasoning, tool-use, and visual tasks, then records evidence and results.

This project supports task-specific comparisons. It does not produce a general model ranking or one aggregate score.

## Included dimensions

- Engineering implementation and maintenance
- Structured reasoning and derivation checks
- Tool use and evidence recovery
- Frontend implementation and visual review
- Runtime, request usage, delivery, and failure metrics

## Quick start

Requirements: Node.js 22 or later and npm.

```powershell
npm ci
npm run check
npm test
```

Create a local `.env` file and add credentials only for a provider you intend to use. The runner loads this file at startup; keep it out of Git. Credentials are not stored in run records.

Validate a plan without loading credentials or sending requests:

```powershell
npm run harness -- --plan examples/eng-001.eval.json --validate-only
```

Results are written under `runs/<run-id>/`.

## Project map

- `src/harness/`: Pi Agent runner and tool profiles
- `src/evaluation/`: validation, grading, trajectories, recovery, and reports
- `task-library/candidates/`: task cards and candidate packages
- `task-library/calibration/`: versioned task packages and offline calibration
- `examples/`: sample evaluation plans
- `docs/HANDOFF.md`: current state and next steps

## Evidence limits

Offline reference runs and mutation checks cover only the stated task contracts. They do not establish model capability, task difficulty, broad evaluation validity, or real-provider behavior. Visual review remains a separate human judgment step.

## Data boundaries

- Candidates receive only public task material.
- Private graders and fixtures stay evaluator-side.
- Candidate-written scores are not authoritative.
- Task execution uses trusted host processes, not an operating-system sandbox.
- Validation-only commands do not send API requests.
- Run records redact common credential formats and omit secret values.

See [the handoff](docs/HANDOFF.md) before continuing work.
