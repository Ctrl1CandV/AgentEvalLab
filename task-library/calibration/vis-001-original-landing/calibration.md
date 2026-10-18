# Calibration Record: vis-001 BookLoop Landing Page

The task fixes product, audience, copy, palette, form behavior, accessibility basics, and viewport requirements. It leaves visual composition open for original design.

The browser-free verifier checks semantic roles, minimum feature count, exact required copy, form labels, the three form states, and declared palette contrast. Historical self-calibration expects the reference to pass and targeted mutations for missing features, low contrast, unlabeled fields, and changed copy to fail.

Responsive rendering, long-content layout, visual quality, and full axe-core scanning remain blocked without a rendering backend and human review. No rendered or real-model evaluation result has been established. See logs/verify-frontend-self-calibration.log for the historical offline run.

## Version 0.3.0 (2026-10-18)

The package gains a manifest and a grader in the harness protocol (`private/grader.py`), so it can run in evaluation plans (PLAN-005 WP6).

- **Grader.** The browser-free checks become six critical checks: roles, features, copy, form, states and contrast.
- **Grader defect fixed.** The checker of 0.2.0 required a `feature-list` data-role marker, which neither the instruction nor content.json names. It is removed. The required field names (`title`, `district`, `email`, `condition`) are given in content.json and stay.
- **Visual quality.** Visual quality is no longer human-reviewed. A judging step renders each submission in headless Chromium (playwright-core 1.55.0, Chromium revision 1187, in the bwrap sandbox), and vision-model judges compare it pairwise with anchor designs, following `private/judge/SKILL.md`. The instruction's acceptance section says so.

Self-calibration (`python3 private/grader.py --self-calibrate`, 3/3) checks three things: the reference frontend passes, the targeted mutations are rejected, and a submission without index.html fails every check.
