# Rubric: VIS v2 0.1.0

Two separate results per trial.

## Function (the grader, `private/grader.py`)

The brief's scenario (`private/scenarios.mjs`) opens `site/index.html` from its files in headless Chromium inside the sandbox, offline, and checks:

- every brief: `renders` (no script error; every role the brief lists is present), `labels` (every visible input, select and textarea has a label or an accessible name), `no-overflow` (nothing scrolls horizontally at 1440×900 or 390×844);
- the brief's own behaviours, each exactly as its prompt states (`private/briefs.py` lists them per brief).

All are critical: `resolved` means every check passed. A submission without `site/index.html` fails every check. Clicks are made as a user makes them; when a decorative layer intercepts the pointer, the element's own `click()` is used, so a check tests behaviour, not hit-testing. The grader also saves the screenshots the judges see (`render/`).

## Design (the tournament, `scripts/judge-tournament-v2.ts`)

Per brief, every page meets the brief's two anchors (the reference page and the plain page: the same markup with browser defaults) and the other models' pages, in both orders, judged by every exam-passing judge whose vendor made neither page (`private/judge/SKILL.md`). A result counts as a win or loss only when it holds in both orders; otherwise it is a tie. Bradley–Terry strengths per brief give the rating: the plain anchor maps to 0 and the reference to 1, on the log-strength scale, uncapped. The family rating is the mean over briefs, with an interval by bootstrap over briefs. Functional `resolved` is reported beside it, not folded in.
