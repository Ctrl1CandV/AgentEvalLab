# Capability Card: VIS v2 0.1.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-25 (PLAN-007 WP3.4), before any model run. The briefs await the user's review (decision D5); the judge calibration set is judged by the user after the first runs.

## 1. Identity

- Tier: core.
- Capabilities: visual (design and front-end craft).
- Protocol: `workspace-augmented` (workspace tools with command execution, so a model can check its own scripts); one brief per trial; the deliverable is a static site in `site/`, opened offline from its files. Fixed budget track, provisional 1,000,000 tokens and 45 minutes per brief until the budget curve (Phase 4).
- Primary score: a rating per brief from pairwise judging against the brief's two anchor pages and the other models' pages: the plain anchor maps to 0 and the reference to 1 on the Bradley–Terry log-strength scale, uncapped. Functional `resolved` (every scripted check passes) is reported beside it.

## 2. What it measures

Designing and building a page for a stated audience and purpose: visual hierarchy, layout, type, colour, responsive behaviour and the craft of states (errors, empty states, selections), on eight kinds of page: an information-dense dashboard, an editor, a multi-step form, two landing pages for different brands, a phone-first page, a data table with filters, and a set of empty, error and loaded states.

## 3. What it does not measure

- Copywriting: the copy and data are fixed in `public/content.json`.
- Framework knowledge: no libraries can be loaded (offline); plain HTML, CSS and JavaScript suffice.
- Whether a behaviour exists: that is the functional result, reported separately; the judges compare how the page looks and reads.
- Speed: tokens and time are reported, not scored.

## 4. Where the difficulty lies

The functional part is small and fully stated (every hook, every behaviour, every value the scripts read is in the brief); the anchors pass it with ordinary code. The difficulty is design quality across very different briefs: a dense dashboard needs restraint and numeric typography, a landing page needs a voice, a phone-first page needs thumb-sized structure, a state set needs consistent illustrations and tone. There is no ceiling: a page can beat the reference anchor by a wide margin (rating above 1), and the tournament between models keeps separating them after all clear the anchors (vis-001 showed that anchor comparisons alone saturate). The scale's ends are fixed and visible: the plain anchor is the reference's own markup with browser defaults, and the reference is a competent, hand-made design per brief.

## 5. Cheapest shortcut

- An empty or broken page: fails the functional checks and loses every pairing; a missing `site/index.html` loses without a judge call.
- A generic template applied to every brief: the judges see the brief and its audience; `fit` and `polish` decide.
- Gaming the judge: judges see screenshots only, never the source, so hidden text cannot reach them; visible text addressed to judges is a defect by the judging skill; pages are anonymous and judged in both orders; a judge rates no page from its own vendor.
- Hard-coding the checks' values: the checks read behaviour in the running page (the KPIs after a filter, the prices after the toggle, the rows after a search); hard-coded values fail as soon as the state changes.

## 6. Anchors and headroom

| Anchor | Maps to | Source |
| --- | ---: | --- |
| plain | 0 | the reference page's markup and scripts with `private/anchors/plain.css` (browser defaults, only the fixes that keep it working) |
| reference | 1 | a hand-made page per brief (`private/anchors/<brief>/`), written for this version |

Both anchors pass every functional check (self-calibration). Uncapped: a page judged better than the reference scores above 1.

## 7. Source, licence and provenance

Project-authored briefs, content, anchor pages, scenarios and judging skill. Exposure: private to runs.

## 8. Task contract and grading

- The model gets `instruction.md`, the brief (`prompt.md`) and `public/content.json`.
- Function: `private/scenarios.mjs` in headless Chromium inside the sandbox, at 1440×900 and 390×844 (`rubric.md`). Every check is stated in the brief; the instruction states the common ones.
- Design: `scripts/judge-tournament-v2.ts` with `private/judge/SKILL.md`: screenshots only (desktop, phone, the brief's states), eight criteria and an overall verdict, both orders, a judge exam first.
- Raw values: `checksPassed`, `checks`; per brief: Bradley–Terry strengths, wins, ties, order inconsistencies.

## 9. Splits and size

Eight briefs, each its own structure group. Dev: `landing-fernwood`, `dashboard`, `multistep`. Validation: `editor`, `landing-quanta`, `mobile-schedule`, `catalogue`, `states`. No holdout in 0.1.0 (new briefs by version, TASK_LIBRARY §5).

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: the reference and the plain anchor pass every check on every brief | `python3 private/grader.py --self-calibrate --launcher scripts/sandbox_exec.py`, `logs/self-calibration-0.1.0.log` (62/62) |
| Null agent | pass: no `site/index.html` fails every check | self-calibration |
| Negative tests | pass: 38 mutants (one broken behaviour each) fail exactly the checks they target, including vis-001's two false passes (an address without a dot in the domain reaching success; an extra option in the select) | self-calibration |
| Adversarial | candidate scripts run in Chromium inside the sandbox, offline (all requests but the page's own files are refused); judges see screenshots only | `private/scenarios.mjs`, `private/grader.py` |
| Judge agreement | pending (paid): the judge exam on the anchors and the user's calibration set (about 20 pairs, decision D5) come with the first runs | Phase 4 |
| Noise | the functional checks are deterministic up to timing (200 ms settles, retry delay plus 400 ms); judging noise is handled by both orders and intervals over briefs | — |

## 11. Budget

Provisional 1,000,000 tokens and 45 minutes per brief; the budget curve comes first in Phase 4.

## 12. History

- 0.1.0 (2026-10-25): eight briefs, scripted functional checks, anchor pages; no model run.
