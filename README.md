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

Requirements: Node.js 22, npm, and Python 3.13 available as `python3` (task graders and checkers use it). The pinned runtime is defined in `environment.yml`:

```bash
mamba env create -f environment.yml
conda activate agenteval
```

Check task-package integrity without Node.js:

```bash
python3 scripts/task_packages.py check
```

```bash
npm ci
npm run check
npm test
```

Create a local `.env` file and add credentials only for a provider you intend to use. The runner loads this file at startup; keep it out of Git. Credentials are not stored in run records.

Validate a plan without loading credentials or sending requests:

```bash
npm run harness -- --plan examples/eng-001.eval.json --validate-only
```

Results are written under `runs/<run-id>/`. Networked commands go through the host proxy: the `harness` and `provider-check` npm scripts set `NODE_USE_ENV_PROXY=1` so Node's fetch honours `HTTPS_PROXY`. Check a provider with `npm run provider-check -- provider:model`, which sends at most six small requests. A live run requires a token ceiling in the plan (`batch.maxTotalTokens` or `batch.maxTotalTokensPerModel`; tokens are fixed units, without prices) and a clean, committed worktree (`--allow-dirty` overrides; the commit and dirty flag are recorded either way). An interrupted single-run batch can be continued with `--resume runs/<run-id>`. `node --import tsx scripts/null-agent-baseline.ts <plan>` runs a plan offline with an agent that does nothing, as a trivial baseline and an end-to-end check.

### Suites

A suite runs several task families with one command and writes one report ([PLAN-006](docs/plans/PLAN-006-suite-runner-and-hardening-round-2.md)):

```bash
npm run suite -- --suite suites/dev.json --models deepseek:deepseek-flash,aliplan:qwen3.8-flash --families E4,T2 --dry-run
npm run suite -- --resume runs/suites/<id>
```

The suite freezes HEAD into a worktree under `runs/suites/<id>/worktree`, generates one plan per family from the template the suite file names, checks the packages and validates every plan, prints a worst-case token estimate, and runs each family once with the null agent (no tokens; every trial must be graded and earn nothing). `--dry-run` stops there; `--resume` continues a dry run or an interrupted suite. A launch starts every family at once, caps concurrent trials per provider endpoint across all processes, resumes each run once for its infrastructure failures (skipping providers stopped for balance or authentication), and writes `runs/suites/<id>/report.md` and `report.json` with per-family scores, a cross-family table and flags. A model without `?thinking=` runs at its declared middle level; `suites/dev.json` refuses launches that break the dev-run policy (pro models, a second model from the airy.work relay, more than one repetition).

## Project map

- `src/harness/`: Pi Agent runner and tool profiles
- `src/evaluation/`: validation, grading, trajectories, recovery, and reports
- `task-library/candidates/`: task cards and candidate packages
- `task-library/calibration/`: versioned task packages and offline calibration
- `examples/`: sample evaluation plans
- `experiments/`: plans for live runs, each with its protocol README
- `suites/`, `src/suite/`: suite files and the one-command suite runner
- `docs/HANDOFF.md`: current state and next steps

## Evidence limits

Offline reference runs and mutation checks cover only the stated task contracts. They do not establish model capability, task difficulty, broad evaluation validity, or real-provider behavior. Visual review remains a separate human judgment step.

## Data boundaries

- Candidates receive only public task material.
- Private graders and fixtures stay evaluator-side.
- Candidate-written scores are not authoritative.
- Candidate code (the `execute_command` tool, `commands` checks, and programs that graders or public checkers start) runs in a bubblewrap sandbox: only its working directory is writable, and the host home directory, task packages, and network are unreachable. Graders and the harness themselves run as trusted host processes. A plan can opt out with `"isolation": "host"`, which is recorded with the run; preflight fails if bubblewrap is unavailable and no opt-out is given.
- Validation-only commands do not send API requests.
- Run records redact common credential formats and omit secret values.

See [the handoff](docs/HANDOFF.md) before continuing work.
