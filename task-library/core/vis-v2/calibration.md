# Calibration: VIS v2 0.1.0

Date: 2026-10-25 (PLAN-007 WP3.4). No model run yet.

## Functional checks

`python3 private/grader.py --self-calibrate --launcher scripts/sandbox_exec.py` (from the repository root, Node 22 of the agenteval environment on the PATH): **PASS 62/62** (`logs/self-calibration-0.1.0.log`). Per brief:

- the reference page and the plain anchor pass every check;
- two common mutants: a script error at load (fails `renders` and every behaviour; the scenario stops where a control it needs is missing) and a page wider than the phone (fails `no-overflow` only);
- two or three brief mutants, each failing exactly the checks it targets: KPIs not following the filter, a chart under 200×120, an unlabelled select (dashboard); no unsaved state, a save that keeps the old title, a list that always opens the first note (editor); any email accepted, Back resetting the plan, no success message (multistep); an address without a dot in the domain accepted and an extra interest option, vis-001's two false passes, and a missing product card (landing-fernwood); yearly prices × 12, a one-way toggle (landing-quanta); no `aria-pressed`, 18-pixel buttons, both days shown (mobile-schedule); a case-sensitive search, a genre filter ignoring the search, a descending sort (catalogue); a retry that never loads, every state shown at once (states);
- a submission without `index.html` fails every check.

A scenario takes 5 to 25 seconds per page. Clicks fall back to the element's own `click()` when a decorative layer intercepts the pointer (the multistep reference's card-wide labels needed it); the result is then checked through the page's visible state, as for any click.

## Tournament pipeline (offline)

`node --import tsx scripts/judge-tournament-v2.ts --package task-library/core/vis-v2 --out <dir> --dry-run` renders the 16 anchor pages and the 8 degraded exam pages in the sandbox and counts the judge calls without credentials: 16 exam cases, at most 160 exam calls with the five default judges. The anchors' screenshots: desktop and phone for every brief, plus the brief's states (unsaved; error and review; form error and success; yearly prices; one saved session; empty and error).

## Pending (paid, Phase 4)

- The judge exam on the anchors (each judge must prefer the reference over the plain anchor and over degraded copies in both orders, score ≥ 0.75, order flips ≤ 25%).
- Judge agreement on the first runs' games, and the user's calibration set (`calibration-pairs.csv`, about 20 contested pairs, decision D5).
- The budget curve on the dev briefs.
