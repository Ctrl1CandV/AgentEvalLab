# Public Scoring Rubric: vis-001

## Automated structural and accessibility checks

- Required semantic regions and data-role markers are present.
- At least three feature entries are rendered.
- All fixed copy from public/content.json is present.
- Form fields and labels are associated.
- Empty, error, and success form states are implemented.
- Palette contrast meets the thresholds stated in the task.

The static checker can only inspect source declarations and structure. It cannot prove computed styles, responsive layout, or visual quality.

## Human review

Use anonymous pairwise review to assess fit to the brief, visual clarity, completeness, and personal preference. Review desktop and phone layouts, all form states, and the six-feature long-content variant. Aesthetic quality has no single correct solution. Do not let visual appeal conceal functional or accessibility defects. Do not use screenshot similarity as an aesthetic score.

## Blocked checks

Full rendered responsive testing and axe-core scanning require a rendering backend. They were not completed in this calibration. Do not claim those checks passed.
