# eng-002 Black-Box Interruption and Atomic-Publish Protocol

This reproducible prototype evaluates interruption and resume behavior for the resumable batch processor. It uses interrupt_probe.py and a copied reference implementation whose recorded SHA-256 prefix was 0E03FD2E2EFC15D3.

## Trigger protocol

- Generate 5,000 input files so the tool's per-item stdout fills the pipe and blocks while the process is active.
- Read stdout and terminate the process after the 50th observed processed line. The trigger is based on observable output, not a random delay.
- Verify the journal has a nonzero number of completed entries below 5,000; the historical run recorded 164.
- Use only the public progress output, external termination, and resulting file state. Do not depend on an internal crash hook.
- Resume, then independently recompute every expected output.

## Historical result

The process was interrupted while running. Published files were complete, journal entries matched actual outputs, no .part files remained, resume exited successfully, and all 5,000 final outputs and journal records were correct.

## Evidence boundary

This supports black-box verification of published-item integrity, journal consistency, and convergence after resume. It does not reliably hit the short window in which one output is partially written. A white-box injection can test that window only for the reference implementation; a larger output is probabilistic. Do not present reference-only injection as a black-box guarantee.

## Recommendation

Add deterministic output-count-triggered interruption and resume checks where the task requires per-item progress output. Label white-box torn-write injection explicitly. Reap terminated child processes and enforce an outer timeout.
