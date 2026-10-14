# Harness Orientation

The execution path is:

1. `src/main.ts` parses CLI arguments and selects a run mode.
2. `src/evaluation/validate.ts` validates the plan and case structure.
3. `src/evaluation/preflight.ts` verifies pinned package manifests.
4. `src/evaluation/run.ts` or `src/evaluation/trajectory.ts` creates a workspace and invokes the Pi runner.
5. The evaluator collects artifacts and evidence, then calls a trusted grader or leaves the result pending for human review.
6. Reports preserve per-run results, usage, and delivery status.

Start with `src/types.ts`, then inspect an example plan, the run lifecycle, and one task grader. Pi integration is in `src/harness/pi.ts`; provider configuration is in `src/providers.ts`.

Budget limits define the evaluated condition. They are not security controls. Candidate commands run in a bubblewrap sandbox (`scripts/sandbox_exec.py`, `src/sandbox.ts`); the harness, tools, and graders run with trusted host permissions.
