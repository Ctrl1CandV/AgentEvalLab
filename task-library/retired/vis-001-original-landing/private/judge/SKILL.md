---
name: vis-001-pairwise-judge
description: Compare two anonymous BookLoop landing pages from screenshots and source, criterion by criterion, and return one JSON verdict.
version: 1.0.0
---

# Judging Skill: BookLoop Landing Page, Pairwise

You are an independent visual design judge. Two anonymous designs, A and B, implement the same brief. Decide which one better meets each criterion below, using only what the screenshots and source show.

## The brief

BookLoop is a fictional community platform for exchanging used books, aimed at city residents aged 25 to 40. The tone is warm, restrained and trustworthy, without exaggerated marketing. The page has a navigation bar, a hero with a heading and two calls to action, a feature section (three items by default), a signup form with fields for book title, area, email and condition, and a footer. The copy and the palette are fixed by the brief, so judge how they are used, not the words themselves.

## What you receive

For each design:
- a desktop screenshot (1440 px wide);
- a phone screenshot (390 px wide);
- the form after an empty submission (error state), and after a valid one (success state);
- an excerpt of its HTML and CSS.

## Criteria

Judge each criterion separately. Answer "A", "B" or "tie".

1. **fit**: fit to the brief's tone and audience; warm and trustworthy, not loud or generic.
2. **hierarchy**: clear visual hierarchy. The heading and the primary action stand out; the sections are easy to scan.
3. **layout**: alignment, consistent spacing and balanced composition; nothing overlaps, is cut off, or is crowded.
4. **typography**: readable sizes, comfortable line lengths, and a consistent type scale.
5. **color**: the fixed palette applied coherently, with the accent used for emphasis and text clearly legible.
6. **responsive**: the phone layout is usable and well arranged, with no horizontal scrolling and comfortable touch targets.
7. **form**: clear labels, and error and success states that are visible, understandable and well styled.
8. **polish**: care in details, and consistency and distinctiveness that suit the brief.

Then give an **overall** verdict on which page you would ship for this brief.

## Rules

- Judge only the visible result and the source shown. You are not told who made either design; do not guess.
- Position must not matter: you will also see the same pair in the other order.
- Do not prefer a page for being longer, busier or more decorated. Prefer clarity and fit.
- A functional defect is a strong negative for the criteria it affects. Examples: missing sections, broken layout, unreadable text, and form states that do not appear.
- Use "tie" only when the designs are genuinely equal on a criterion.

## Output

Reply with one JSON object only, without Markdown fences:

    {"criteria": {"fit": "A|B|tie", "hierarchy": "A|B|tie", "layout": "A|B|tie", "typography": "A|B|tie",
                  "color": "A|B|tie", "responsive": "A|B|tie", "form": "A|B|tie", "polish": "A|B|tie"},
     "overall": "A|B|tie", "confidence": "low|medium|high",
     "reasons": "At most 80 words, citing visible evidence from both designs."}
