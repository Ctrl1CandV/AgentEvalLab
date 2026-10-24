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

## Version 0.3.1 (2026-10-18)

The first model run (`experiments/vis-calibration-2026-10`) exposed three grader defects. Each failed submissions that met the instruction:

- **Copy split by inline markup.** The copy check needed each fixed string contiguous in the raw HTML or in text fragments joined by newlines. A heading such as `Let a finished book meet its <span>next reader</span>.` failed, and so did a footer whose Rules, Privacy and Contact are links, or which uses character entities (`&#169;`, `&#183;`). Copy is now matched against the text as a page renders it: inline pieces joined, entities decoded, whitespace collapsed, and blocks separated. The raw HTML (where a script may read state messages from `data-*` attributes) and app.js are still searched too.
- **Wrapping labels ignored.** The instruction allows "label[for] or a wrapping label", but only `label[for]` was recognised. A control inside a `<label>` now counts as labelled.
- **HTML `required` attribute demanded.** "Required" in the instruction describes behaviour, and the form's error state, which the renderer checks, tests that behaviour. The attribute is one implementation and is no longer demanded. Field names and types, given in content.json, are still checked.

Self-calibration adds four variants that must pass: an inline heading, a linked footer with entities, a wrapping label, and no `required` attributes. A misplaced write in the mutation helper had left some mutations unapplied while they were being added; it now writes both files once for every kind. Result: 3/3; see `logs/self-calibration-0.3.1.log`.

## Grader 1.0.2 (2026-10-19)

The 800,000-token calibration run (`eb491788`) had one luna page fail `states`. It showed the empty state as the form-state element's initial text and switched to error and success in its script. That is what the brief asks for, but the check required the word `empty` in app.js. The check now follows the brief, as the rubric describes. Self-calibration adds a variant with the empty state in HTML only, which must pass, and a script without a submit handler, which must fail. Result: 3/3.
