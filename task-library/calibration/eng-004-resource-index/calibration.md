# Offline Calibration Record: eng-004 Resource Index

Task version 0.1.1; development use only. Historical environment: Node v22.23.3, no network, no dependency installation.

Two reference implementations used different valid approaches. Across three repetitions, each passed all seven checks. Coverage included search filtering, defaults, Unicode code-point ordering, pagination, input rejection, CSV behavior, and index compatibility. Three targeted flawed implementations were rejected: an off-by-one page start, missing CSV escaping, and an incorrect nextOffset.

CSV checks inspect CRLF record boundaries, quoting, embedded LF, and the required final CRLF. Search, legacy index behavior, and CSV export are checked separately. Failure output is stored only as a bounded digest or summary.

## Limits

Offline calibration only demonstrates compatibility between the contract, checker, and reference implementations. No model API was run and no candidate traces were collected for the two proposed tool profiles. A single basic/augmented comparison cannot establish that extra tools reduce rework.


## Version 0.2.0 (2026-10-13)

The English task material in this repository is the canonical baseline; there is no earlier source text to reconcile against. Version 0.1.1 recorded digests for earlier bytes of the instruction and documentation files, so the package no longer passed preflight. This version re-pins every file digest and resolves the grader and public checkers as `python3` from PATH (Python 3.13 required) instead of a host-specific interpreter path. Grader logic is unchanged; only the TASK_VERSION constant in private/acceptance.py changed.

Calibration results above were recorded against version 0.1.1 and remain historical. Recalibration under 0.2.0 is pending a provisioned Node.js 22 and Python 3.13 environment.

The pinned baseline repository (commit 3b43f3c6c2db454f90765de2ca614b783c624c8e) is not available in this repository: baseline/ is an unresolvable Git link. The task cannot run until a project-owned baseline is rebuilt and pinned, which will be a further version change.


## Version 0.2.1 (2026-10-14)

Candidate code started by the grader now runs through the harness sandbox launcher (`scripts/sandbox_exec.py`, bubblewrap): only the candidate's working directory is writable, and the host home directory, the task package (including `private/`), and the network are unreachable. The launcher path comes from the grader request's `sandbox` field; when a plan opts into `"isolation": "host"`, the field is null and candidates run as before. The task contract and check logic are unchanged; the grader version is now 1.1.0.

Recalibration under 0.2.1 is recorded in `logs/self-calibration-0.2.1.log`.

## Version 0.3.0 (2026-10-20)

The pinned baseline repository (commit 3b43f3c) was a Git link to a repository that is not available, and the user asked to treat it as lost. This version rebuilds a project-owned baseline instead.

- **Sources.** `private/baseline-source` holds the baseline, written from the public contract and the reference variants, which overlay `cli.ts`, `export.ts` and `search.ts`:
  - `catalog.ts` (validation that keeps every field), `index.ts` (stable ascending id order) and `types.ts` work as the contract describes;
  - `export.ts` writes CSV without quoting and with LF line endings, which the contract asks to repair;
  - `cli.ts` has `index` and `export` but no `search`;
  - there is a README, a package.json and `tests/baseline.test.mjs`.
- **Build.** `private/build_baseline.py` builds a two-commit history with fixed authors and dates, so the baseline commit, 0bd1eda866f64c4cdd990e7636cead1ebd2a6cd2, is reproducible. It writes `baseline.bundle`, and `scripts/prepare-baselines.mjs` restores it as a pinned clone before checks and runs, as for eng-005.
- **Guards (grader 1.2.0).** The untouched baseline rejected every bad argument, since it has no `search` command, and kept its index, so it passed `invalid-pagination` and `index-compatibility`. Both now count only when `search-filter` passes, so an untouched workspace earns nothing.
- **Self-calibration.** See `logs/self-calibration-0.3.0.log`: both references on the rebuilt baseline pass 7/7 three times, the three mutants are rejected, the CSV delimiter cases hold, and the untouched baseline earns nothing.
