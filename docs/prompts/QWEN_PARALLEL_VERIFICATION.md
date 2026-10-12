# Parallel Task Verification Checklist

Use this checklist when reviewing an offline task calibration. It does not authorize a live provider request.

## Verify

1. Confirm the exact task version, runtime, dependency lock, and manifest hashes.
2. Run at least two independent valid references where alternative implementations are allowed.
3. Run targeted mutations for important requirements and verify that each is detected.
4. Check timeout, malformed output, missing artifact, and grader failure attribution.
5. Verify public projection boundaries and that grading uses an immutable artifact snapshot.
6. Compare repeated outputs for deterministic checks.
7. Record commands, exit codes, logs, and untested assumptions.

Keep task outcomes separate from process and infrastructure failures. Do not infer model capability from package calibration alone.
