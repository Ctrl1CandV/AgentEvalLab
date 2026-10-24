# Public Scoring Rubric: vis-001

## Objective checks (grader)

These checks are browser-free and critical:

- **roles**: the required data-role markers are present (nav, hero, hero-h1, cta-primary, features, signup-form, form-state and footer).
- **features**: at least three feature entries.
- **copy**: all fixed copy from public/content.json is present.
- **form**: form fields and label associations, using the field names given in content.json.
- **states**: empty, error and success form states: a form-state element, each state's exact text in the page or its script (the empty state may be the element's initial text), and a script that handles the submission. Before grader 1.0.2 the check searched app.js for the words `empty`, `error` and `success`, which failed a page that showed the empty state as initial HTML text.
- **contrast**: palette contrast meets the thresholds in the task.

The trial score is the fraction passed.

## Visual quality (judging step)

A separate step renders each submission in headless Chromium:

- a desktop and a phone screenshot;
- the form's error and success states;
- objective rendered measurements, such as horizontal overflow.

Vision-model judges then compare it pairwise with fixed anchor designs, in both orders, following `private/judge/SKILL.md`. Each judge returns a verdict on eight criteria and an overall verdict. Judges never see who made a page, and no judge rates a page from its own vendor. Visual scores are reported as a separate dimension, next to the judges' measured consistency, and never offset functional or accessibility defects. Screenshot similarity is not used as an aesthetic score.
