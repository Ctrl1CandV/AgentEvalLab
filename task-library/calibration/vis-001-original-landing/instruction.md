# Task: Original Landing Page (vis-001, BookLoop)

Design and implement an original static landing page for the fictional product BookLoop. Product, audience, copy, and palette are fixed below and in public/content.json. Originality is expected in visual design and layout, not by rewriting the copy.

## Product and audience

- Brand: BookLoop, a fictional community platform for exchanging used books.
- Audience: city residents ages 25–40 who want a finished book to keep circulating.
- Tone: warm, restrained, and trustworthy; avoid exaggerated marketing.

## Required copy

Use the exact English copy in public/content.json. Do not rewrite, replace, or omit it. Decorative microcopy may be added.

- Navigation: BookLoop, Home, How it works, About.
- Hero heading: Let a finished book meet its next reader.
- Supporting line: Community book exchange, nearby, with less waste.
- Primary CTA: Start exchanging. Secondary CTA: Learn the rules.
- Features: Nearby matches, Trust points, and Transparent condition. Use each title and description from content.json. The section length may vary from three to six entries; see content_long.json.
- Signup form: fields are specified below.
- Footer: © 2026 BookLoop · Rules · Privacy · Contact.

## Form requirements

- Fields: Book title (required text), Area (required select with Downtown, Jiangbei, Shapingba, and Nan'an), Email (required email), and Condition (radio choices New, Light wear, Visible wear).
- Every field must have an associated label, using label[for] or a wrapping label.
- Show all three states: empty with initial guidance, error with visible styling and copy, and success with confirmation. Use the exact strings in content.json under form.states.

## Visual and accessibility requirements

- Use these CSS variable values from content.json:
  --bg #FFFFFF, --fg #1A1A1A, --muted #555555, --accent #1E40AF,
  --accent-fg #FFFFFF, --line #D9D9D9, --err #B00020.
  Additional decorative colors are allowed, subject to contrast requirements.
- WCAG 2.2 AA contrast: body text, secondary text, primary button text, and error copy need at least 4.5:1 against their backgrounds. Large text and UI components/graphics need at least 3:1.
- Provide associated form labels, keyboard focus with a visible focus style, and a skip link to the main content.
- Aim for primary interactive targets of at least 24 by 24 CSS pixels. Reasonable exceptions include dense inline links and decoration; do not penalize every small element mechanically.
- The page must remain readable without horizontal scrolling at desktop 1440x900 DPR 1 and phone 390x844 DPR 2. The feature section must support three through six items without breaking.

## Deliverables

- index.html, style.css, and app.js. The page must work as a static frontend opened directly in a browser. System fonts are acceptable. If images are used, create them in CSS or use CC0 assets and record the source.
- Use semantic markup and data-role markers for key areas: nav, hero, hero-h1, cta-primary, features, feature, signup-form, form-state, and footer. Acceptance is semantic and behavioral; class names are unrestricted.
- A short README documenting design intent and assumptions.

## Acceptance

Automated checks cover:

- semantic structure and data-role markers;
- at least three features;
- exact fixed copy;
- form fields and label associations;
- form states;
- palette contrast.

Visual quality is judged separately: the page is rendered in a browser at desktop 1440x900 and phone 390x844, including the form's error and success states. Vision-model judges then compare it pairwise with other designs for:

- fit to the brief;
- hierarchy;
- layout;
- typography;
- colour;
- responsive quality;
- the form experience;
- polish.

Aesthetic quality has no single correct answer. Functional and accessibility defects cannot be offset by visual appeal.

## Out of scope

Backend or real form submission, SEO, pixel-perfect copying of an existing site, and framework requirements are out of scope. Do not use screenshot similarity as an aesthetic score.
