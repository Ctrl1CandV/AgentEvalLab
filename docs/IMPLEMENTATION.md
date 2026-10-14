# Implementation Notes

## Commands

```bash
npm ci
npm run check
npm test
npm run harness -- --plan examples/eng-001.eval.json --validate-only
```

The `harness` command accepts either a single model and prompt or a versioned plan. Plan validation and preflight run before credentials are loaded. The `--validate-only` flag exits before any provider request.

## Adding an objective task

1. Create a package with a manifest, public projection, trusted grader, fixtures, and calibration record.
2. Define stable requirement IDs and grader output in the manifest.
3. Run reference and mutation calibration locally.
4. Pin the package path and manifest hash in an example plan. `python3 scripts/task_packages.py rehash <package>` refreshes manifest digests and example pins; `check` verifies them.
5. Record commands, runtime versions, and evidence in the task calibration log.

Never expose trusted grader files through the public projection. Keep implementation and scoring changes in separate reviewable steps.
