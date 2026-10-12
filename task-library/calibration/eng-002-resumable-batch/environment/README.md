# eng-002 Runtime and Execution Plan

## Dependencies

Python 3.13.15 and the standard library only. No third-party packages, installation, or network access.

## Host notes

Historical calibration used the LibreOffice Python runtime. Its interpreter could not be spawned directly, so the grader used shutil.which("python") as the launcher. Subprocess crash traces use errors="replace" because the Windows console encoding may not be UTF-8.

## Execution plan

- Candidate: read instruction.md and public/, then create the script in an empty workspace.
- Evaluator: run private/make_fixtures.py to generate seven deterministic resume states; run private/acceptance.py --self-calibrate for calibration or --impl <script> for black-box static recovery checks.
- Keep reference implementations, flawed implementations, fixtures, and acceptance code in private/; do not project them to the candidate.

Historical checks passed static recovery 7/7 and white-box recovery 3/3. The targeted flawed implementations were rejected. External process killing and real model execution remain blocked; no budget has been fixed.

## Reproduction

From task-library/calibration/eng-002-resumable-batch, run:

    python private/make_fixtures.py
    python private/acceptance.py --self-calibrate

The results are historical calibration evidence, not a claim about model performance.
