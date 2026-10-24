# Calibration Record: AR abstraction and reasoning

## Version 0.1.0 (2026-10-24, PLAN-007 WP3.1)

**Build.** `python3 private/build_package.py` from the ARC-AGI-1 (`fchollet/ARC-AGI` @3990304) and ARC-AGI-2 (`arcprize/ARC-AGI-2` @f3283f7) public evaluation sets, Apache-2.0, with both licences in `private/licenses/`. The six ARC-AGI-1 evaluation tasks that are also ARC-AGI-2 evaluation tasks count once, as ARC-2. A seeded draw (`ar-2026-10`) by task chose 80 of the remaining 394 ARC-1 tasks and dealt them and all 120 ARC-2 tasks to the splits of TASK_LIBRARY §3.2: dev 20 + 20, validation 30 + 50, holdout 30 + 50. Only task ids and counts were read while building. Each item holds the task's training pairs and test inputs, in the prompt and as `public/task.json` (without the test outputs); the outputs are the keys.

**Self-calibration** (`python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.1.0.log`), on every one of the 200 tasks: the official outputs resolve the task in attempt 1 and in attempt 2; a third attempt is ignored; a grid with one cell changed fails; a transposed grid fails unless the output is symmetric; an answer in prose with a fence is recovered on its content and fails the format check; an empty reply and a reply without an object fail; an answer to the first of several test inputs matches that one only.

No model has run AR. Budgets are provisional until the Phase 4 budget curve.
