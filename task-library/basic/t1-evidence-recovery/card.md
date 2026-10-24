# Capability Card: T1 evidence recovery 0.6.0

Template: `docs/templates/CAPABILITY_CARD.md`. Written 2026-10-24 (PLAN-007 WP2.2), for the unchanged task 0.6.0 and grader 1.7.1.

## 1. Identity

- Tier: basic.
- Capabilities: agentic (tool use over a read-only snapshot).
- Protocol: the `doc-evidence` tools (`list`, paged `read` of 400 characters, `search`), nothing writable; one session per item; fixed budget track; 2,000,000 tokens per item in the last v1 configuration (`experiments/t1-calibration-2026-10/cases-dev.eval.json`), stated to the model.
- Primary score: resolved (every answer field of every question right, with the evidence shown in the trace).

## 2. What it measures

Recovering facts from a fictional project snapshot (about 190 small files) through narrow tools, and answering only what the trace supports: following include chains, configuration precedence, change histories with reverts and amendments, rotations across time zones, and declining when the snapshot does not say. At F2–F5 each question asks for a rollback procedure, approver and deadline under written rules, so each answer combines several chains.

## 3. What it does not measure

- Outside knowledge: the project is fictional.
- Writing code or changing files: nothing is writable.
- Search efficiency: tool calls and tokens are reported, not scored.

## 4. Where the difficulty lies

Reliability over many small decisions. Every rule is in the snapshot (`docs/RESPONSE.md`, file conventions), and each question is built around modelled misreadings (a later change not undone, an include skipped, Berlin times read as UTC, a swap ignored; `calibration.md` 0.6.0) that each change its conclusion. Strong models make these decisions reliably: in v1 (0.6.0, grader 1.7.1) qwen3.8-flash resolved 4/4 F4–F5 items and deepseek-flash 2/4, while mimo-v2.6-flash resolved 1/4. It belongs in the basic tier: a slip shows, but it no longer separates strong models.

## 5. Cheapest shortcut

- Guessing from the question text: the conclusions turn on facts in the snapshot, and an answer counts only when the trace shows the files it needs.
- Answering "insufficient evidence" everywhere: fails every answerable question.
- Reading `secrets/`: denied by the tools.
- A reply that is not one clean JSON object: the content is recovered when it ends with the answer object; the PLAN-005 deduction is a separate column (decision D2).

## 6. Anchors and headroom

No metric anchors (contract task). Headroom: F5's counterfactual fields; the D (depth) and L levels are easier.

## 7. Source, licence and provenance

Project generator (`private/generate.py`, seed `t1-2026-10`, four items per level, levels L1–L7, D2–D8, F2–F5), generalising the retired tool-001; no text copied. Exposure: generated, private to runs.

## 8. Task contract and grading

- The model receives `instruction.md`, the item's questions (`prompt.md`) and the snapshot through the tools, and replies with one JSON object, one key per question.
- Checks: one critical check per question (`q<n>`), or per answer field for an adjudication question (`q<n>-<field>`); a field passes when its value matches and the trace shows its supporting lines (search matches or read pages covering them) and the files it cannot be found without. The format check is apart.
- Score model: one group `answers` (rule fraction, critical); resolved when every answer check passes; diagnostic = the share passed; format `answer-format`, deduction 0.2 reported separately.
- Equivalent answers: deadlines compared as UTC minutes in any close format; case and whitespace of names.

## 9. Splits and size

- Structure group: the level (`level:<L>`): a level's items share the generator template.
- All 60 items are dev: every level has been run and inspected. As a basic family it has no validation or holdout split. The basic suite runs F4 and F5 (eight items).

## 10. Verification status

| Gate (VALIDATION §1) | Result | Evidence |
| --- | --- | --- |
| References | pass: an independent solver reproduces every adjudication key; a full trace passes every field | `python3 private/grader.py --self-calibrate`, `logs/self-calibration-0.6.0.log` (2925/2925) |
| Null agent | pass: an empty reply fails every check | self-calibration; the basic suite smoke |
| Mutants | pass: leaving out any needed file fails exactly the fields that need it; wrong values fail | self-calibration |
| Alternative valid solutions | pass: close deadline formats | self-calibration |
| Adversarial | pass: `secrets/` denied; nothing writable | tool profile |
| Success audit | pass: no false pass and no false fail over the 12 F4–F5 trials of the 0.6.0 dev run (288 fields) | `docs/audits/T1/2026-10-24.md` |
| Coverage invariant, global end state | n/a | — |
| Noise | n/a: nothing timed | — |
| Determinism | pass: grading is a function of the reply, the trace and the key | — |

## 11. Budget

2,000,000 tokens per item (the 0.6.0 dev configuration); one of four mimo-v2.6-flash trials stopped on it.

## 12. History

- 0.1.0–0.6.0: see `calibration.md` (0.6.0 added the adjudication ladder F2–F5).
- 2026-10-24: manifest v2 with this card; task and grader unchanged.
