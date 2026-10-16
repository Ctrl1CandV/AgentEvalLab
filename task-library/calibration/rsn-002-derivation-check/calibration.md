# Offline Calibration Record: rsn-002 Derivation Check

This development package checks a fixed sliding-block derivation with structured numeric evidence. Public samples lie within the stated domain. The grader checks step identification, calculated speeds, dimensions, and recomputable discrimination evidence, including the required boundary limit.

The private oracle and calibration log are evaluator materials and must not be projected into the candidate workspace. Any symbolic equivalence or explanation-quality judgment remains unscored unless a separate human-review protocol is added.

No real model evaluation or general physics-capability claim has been established. See logs/self-calibration.log for the historical run record.


## Version 0.3.0 (2026-10-13)

The English task material in this repository is the canonical baseline; there is no earlier source text to reconcile against. Version 0.2.0 recorded digests for earlier bytes of the instruction and documentation files, so the package no longer passed preflight. This version re-pins every file digest and resolves the grader and public checkers as `python3` from PATH (Python 3.13 required) instead of a host-specific interpreter path. Grader logic is unchanged; only the TASK_VERSION constant in private/acceptance.py changed.

Calibration results above were recorded against version 0.2.0 and remain historical. Recalibration under 0.3.0 is pending a provisioned Node.js 22 and Python 3.13 environment.


## Version 0.4.0 (2026-10-14)

The grader (now 1.1.0) adds a non-critical `answer-format` check under the new requirement `REQ-FORMAT`. The check passes when the final answer parsed as one JSON object, as the instructions require. Scoring stays strict: an answer that does not parse still fails every content check. The objective verdict depends on critical checks only, so the format check reports instruction-following failures separately from wrong answers. Self-calibration now also covers the format check; see `logs/self-calibration-0.4.0.log`.

## Version 0.5.0 (2026-10-16)

Grader 1.2.0 parses the final answer in one of three ways:

- **strict:** one JSON object, as instructed;
- **recovered:** one JSON object once exactly one enclosing Markdown code fence, optionally labelled `json`, and surrounding whitespace are removed;
- **unparsed:** anything else, including prose around a fence or several fences.

Content checks run on strict and recovered answers. `answer-format` passes only for strict answers, and its evidence records the parse mode. The manifest's new `scoring` block declares a format penalty of 0.2, so the harness scores a recovered trial at 80% of its content score. The score is now partial credit: the fraction of content checks passed. This follows the user's decision of 2026-10-16 after the pilot, in which glm-5.3 fenced all three rsn-002 answers; all three pass every content check under 1.2.0. Self-calibration adds parse and format probes; see `logs/self-calibration-0.5.0.log`.
