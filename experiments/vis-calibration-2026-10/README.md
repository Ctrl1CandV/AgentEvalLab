# Visual Calibration 2026-10

The first run of vis-001 0.3.0 with model judging (PLAN-005 WP6). The four calibration models each build the BookLoop page twice. The browser-free grader scores structure, copy, form and contrast. A separate judging step then renders every page and has vision-model judges compare it with two anchor designs.

## Running

```bash
npm run harness -- --plan experiments/vis-calibration-2026-10/calibration.eval.json
node --import tsx scripts/judge-visual.ts --run runs/<id> --package task-library/calibration/vis-001-original-landing --dry-run
node --import tsx scripts/judge-visual.ts --run runs/<id> --package task-library/calibration/vis-001-original-landing
```

## Judging

- **Rendering.** Headless Chromium (playwright-core 1.55.0, revision 1187) runs in the bubblewrap sandbox. It captures a desktop page at 1440 px and a phone page at 390 px (both capped at 2,600 px tall), and the form after an empty and after a valid submission. It also measures horizontal overflow and whether the form states appear.
- **Judges.** The vision-verified models are gpt-6-luna (medium), step-5-preview (medium), deepseek-flash (high) and glm-5.3-flash. Each page gets a panel of three, never including the page's own vendor. glm-5.3 cannot judge, because the relay drops its image input.
- **Comparisons.** Every page is compared with the reference anchor and the plain anchor, in both orders. A result counts only if it holds in both orders. The visual score is win 1, tie 0.5 and loss 0, averaged over judges and anchors.
- **Anchor gate.** A judge's verdicts count only if it prefers the reference over the plain anchor in both orders.
- **Consistency.** The report gives the position-inconsistent rate and the agreement between judges. The project has no expert reviewers; the user's own comments on a sample of pages are a reference, not a gate.
