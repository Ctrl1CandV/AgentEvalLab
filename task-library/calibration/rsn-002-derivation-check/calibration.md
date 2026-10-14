# Offline Calibration Record: rsn-002 Derivation Check

This development package checks a fixed sliding-block derivation with structured numeric evidence. Public samples lie within the stated domain. The grader checks step identification, calculated speeds, dimensions, and recomputable discrimination evidence, including the required boundary limit.

The private oracle and calibration log are evaluator materials and must not be projected into the candidate workspace. Any symbolic equivalence or explanation-quality judgment remains unscored unless a separate human-review protocol is added.

No real model evaluation or general physics-capability claim has been established. See logs/self-calibration.log for the historical run record.


## Version 0.3.0 (2026-10-13)

The English task material in this repository is the canonical baseline; there is no earlier source text to reconcile against. Version 0.2.0 recorded digests for earlier bytes of the instruction and documentation files, so the package no longer passed preflight. This version re-pins every file digest and resolves the grader and public checkers as `python3` from PATH (Python 3.13 required) instead of a host-specific interpreter path. Grader logic is unchanged; only the TASK_VERSION constant in private/acceptance.py changed.

Calibration results above were recorded against version 0.2.0 and remain historical. Recalibration under 0.3.0 is pending a provisioned Node.js 22 and Python 3.13 environment.
