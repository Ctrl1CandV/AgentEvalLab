# Calibration Record: T2 Service Desk

T2 is the policy-bound tool-use family of Task Set v2 (PLAN-005 WP5), after τ-bench: a desk tool, a written policy and customer tickets, graded on the final state of the shop's data and on the reply.

## Version 0.1.0 (2026-10-20)

- **Eight tickets** over one shop of four customers, nine products and eight orders, with today fixed as 2026-10-20.
  - Each ticket's actions, amounts and done/declined lists were worked out by hand from `POLICY.md`, for example 129.00 less the 15% restocking fee, 10% of 286.00 as compensation, and a book returned on day 15 of a 14-day window.
  - The tickets cover allowed and declined requests in the same ticket, a request about another customer's order, an uppercase sender address, a gold customer without a restocking fee, a gift-card order refunded as credit, an exchange with a credit for the difference, an exchange for a dearer product, a second compensation, and a goodwill credit the policy does not provide for.
- **Self-calibration (43 scenarios).** For every ticket:
  - the expected actions, run through `desk.py` with the right reply, pass every check;
  - the same with the reply in prose loses only `answer-format`;
  - doing nothing passes nothing;
  - editing `db.json` directly passes nothing.

  Wrong handlings pass exactly the checks they should: a return without the restocking fee, an unrequested compensation, a refund for another customer's order, and an exchange without the credit. See `logs/self-calibration-0.1.0.log`.
- No model has been run yet.

## Grader 1.0.1 (2026-10-20)

- **Defect.** POLICY.md asks the reply to *end with* one JSON object, so prose before it complies. Grader 1.0.0 counted only a reply that was nothing but JSON as well formed, and the self-calibration even expected prose before the object to lose `answer-format`. Every model but luna explains its handling first, so all their tickets lost 20%.
- **Fix.** A reply that ends with a JSON object, bare or in a closing fenced block, meets the format. Anything else falls back to the shared recovery rule with the 20% deduction, for example an object followed by more prose.
- **Self-calibration (59 scenarios).** For every ticket, the expected handling passes every check with the object alone, after prose, and in a closing fence; followed by prose, it loses only `answer-format`.
- **Regrade.** All 59 graded trials of the first calibration run were regraded; the four infrastructure failures have no grade. See `experiments/t2-calibration-2026-10/README.md`.


## Version 0.2.0 (2026-10-20)

0.1.0 tested its rules one at a time, and four of five models handled every ticket. 0.2.0 makes them interact, with the same tool-and-policy form and the same grader.

- **Policy.** Ten sections instead of seven:
  - only verified sender addresses count;
  - coupons make the *unit price paid* differ from the list price, and returns, exchanges, price drops and compensations are all computed from it;
  - refunds go to store credit first, up to the order's unreturned credit payment, so two returns from one order split differently;
  - return windows by category (books 14 days, clothing 60, food and final-sale never) with 15 more days for gold customers;
  - restocking fees by tier (standard 15%, silver 10%, gold none), waived for defective items;
  - exchanges against the price paid, once per line and not after a return;
  - price drops within 7 days of delivery;
  - late orders include undelivered ones past their promised date, with 15% for gold;
  - requests are handled in sequence, and a request that does not identify one line or order is declined.
- **Tool.** `refund` takes the card and store-credit parts; `adjust-price` records a price drop; `products FAMILY` lists a family; cancellations split their refunds and, when the last line goes, refund the shipping fee.
- **Data and tickets.** Six customers (two with alternate addresses, one unverified), sixteen products, fifteen orders, and twelve tickets of two to four requests. Each ticket's actions were worked out by hand and again by `private/oracle.py` from the policy; they agree.
- **Self-calibration (92 scenarios).** The data adds up (every order's payments equal what was paid). For every ticket, the expected handling passes every check (alone, after prose, fenced), loses only `answer-format` when followed by prose, and passes nothing done directly in `db.json` or left untouched. Nine wrong handlings, one per trap, pass exactly the checks they should. See `logs/self-calibration-0.2.0.log`.

## Version 0.3.0 (2026-10-21)

**Why.** 0.2.0 saturated: in the 2026-10-20 runs qwen scored 100%, deepseek and mimo-pro 97.5%. In the first suite run (2026-10-21, `runs/suites/20261021-120039-dev-fe3b`) deepseek again scored 100% and qwen 96.7%, losing only format deductions. These models apply a written policy almost without error. PLAN-006 B3 moves T2 to optimisation within the policy: several resolutions comply, and the policy states which one is required.

**Policy section 11, damaged and missing items.**

- Reports are accepted within 30 days of delivery, for units still held.
- Every accepted unit is made good by one of four options:
  - the same product sent again;
  - a substitute of the same family priced at least at the unit price paid;
  - a refund;
  - store credit at 110%.
- The required resolution is the one that costs the shop least for the whole ticket:
  - products sent, at cost;
  - one carrier rate per delivery address that receives anything (UK 4.90, EU 9.90, US 24.90);
  - refunds in full;
  - credit at 70% of its amount.
- The decisions are coupled:
  - stock is shared between orders;
  - orders to one address share a shipment;
  - customers may refuse credit, insist on the same model, or bar an address.
- `desk.py` gains `make-good ORDER SKU QTY replace|substitute NEW_SKU|refund|credit`. It computes refunds (store credit first) and credit amounts, and takes products from stock.

**Tickets** (`private/makegood.py`, seed `t2-makegood-2026-10`, written to `private/makegood.json`). A catalogue of 26 products in eight families, with list price, cost and stock, and twelve tickets with their own customers and orders:

| Level | Orders | Reports | Units | Optimum (EUR) | Ignoring carrier rates | Refunding everything |
| --- | --- | --- | --- | --- | --- | --- |
| S (`os1`–`os4`) | 1 | 3 | 4–5 | 119–193 | +0% | +9% to +57% |
| M (`om1`–`om4`) | 2 | 2–5 | 2–9 | 152–389 | +2.2% to +6.5% | +6.5% to +50% |
| L (`ol1`–`ol4`) | 3–4, plus an old order | 7–9 | 9–15 | 260–412 | +1.8% to +4.7% | +31% to +54% |

- **Selection.** A ticket is kept only when:
  - refunding everything costs at least 5% more than the optimum;
  - the optimum both sends something and pays money back for something;
  - at M and L, the shortcut that ignores carrier rates costs at least 1% more.
- **Constraints.** Three tickets refuse credit, two bar an address, and seven ask for the same model on some line. Every L ticket has a report on an order delivered 35–50 days ago, which must be declined.

**Grader 1.1.0:**

- one `resolved-ORDER` check per order with an accepted report;
- `no-other-changes` and `reply`;
- `cost-5`, `cost-1` and `cost-0` against the least cost, counted only for a compliant resolution.

**Self-calibration** (`logs/self-calibration-0.3.0.log`): 171 scenarios, all as expected.

- The data adds up, and on the eight tickets with at most eight units an enumeration of every option reproduces the min-cost flow's optimum.
- On every optimisation ticket:
  - the optimum passes everything; without a reply, it loses only `reply` and the format;
  - the untouched shop passes nothing;
  - refunding everything is compliant and passes no cost rung;
  - ignoring carrier rates is compliant and reaches the rungs its cost reaches: every rung on S tickets, `cost-5` on most M and L tickets;
  - one unit short fails that order and every cost rung;
  - credit despite a refusal fails that order;
  - making good the old order's report fails `no-other-changes`.
- The 0.2.0 tickets pass as before.

## Grader 1.1.1 (2026-10-21)

The first 0.3.0 run (`runs/suites/20261021-124022-dev-1249`) found two grader defects.

- **A closing JSON block after an earlier fenced block failed the format.** The pattern for the closing fence began matching at the reply's first fence, so deepseek-flash (`os1`) and qwen3.8-flash (`om1`) lost 20%. Both had shown their commands in a block before the final block. The pattern now matches only the last block.
- **A missing reply was deducted twice.** It fails `reply`, and the format deduction then took 20% of what the trial's actions earned. This hit three trials stopped by their budget after finishing every make-good: deepseek and mimo-v2.6-flash on `ol4`, mimo on `om4`. The deduction is for a reply that had to be recovered; a missing or unusable reply now fails `reply` only.

Self-calibration: 195 scenarios, including a closing block after another fenced block. All 36 trials of the run were regraded.


## Version 0.4.0 (2026-10-22): shifts

**Why.** In 0.3.0 (`runs/suites/20261021-124022-dev-1249`) deepseek-flash scored 95.2% and qwen3.8-flash 100%. A ticket of at most 15 units is small enough to optimise exactly, and every rule's conditions sat on the order being handled.

**What changes.** The user decided (2026-10-22) that hardening should come from several chains that depend on one another, not from scale alone. So 0.4.0 adds rules whose conditions must be derived from other records, and which couple the tickets of a shift.

**Items.** `sh1`–`sh4`, each one shift of eight tickets from six customers in one workspace (`private/shift.py`, `private/shift_desk.py`, `private/SHIFT_POLICY.md`; data in `private/shifts.json`). The policy adds recalls, a claims review, a goodwill limit and same-day consolidation of shipments (see the rubric).

**Planted couplings.**

- two households;
- a customer whose first compensation crosses the goodwill limit and who writes again;
- a customer one report short of review who writes twice;
- a recall covering one order (a return past its window) and missing another order of the same product (placed after the notice's dates);
- history entries on the first counted day of each limit and on the day before.

**Selection.** Six misreadings are modelled:

- today's reports or today's goodwill left out;
- the first counted day read as excluded;
- consolidation ignored;
- recalls ignored;
- every unit of a recalled product treated as covered.

A shift is kept only when each misreading would fail some ticket's checks, judged on the true state before that ticket. At least four tickets must have make-goods, and the shift must mix reports, returns and compensations. The tickets each misreading changes are recorded in `shifts.json` and in the self-calibration log.

**Grading** (grader 1.2.0): per ticket, against the oracle on the state when the ticket began, as the rubric describes.

**Self-calibration** (`logs/self-calibration-0.4.0.log`), 247 scenarios, all as expected:

- The data adds up. On every shift ticket with at most eight units, an enumeration of every option, with stock and today's shipments, reproduces the min-cost flow's optimum. The recorded misreading effects are reproduced.
- The oracle's commands, run through the shift's `desk.py` itself, pass every check, and so do they without `begin` markers, the boundaries then being inferred.
- An untouched shop scores 0. The oracle's reply alone scores 15–16%: the replies that are also right for an untouched shop, and the no-other-changes check of tickets that only decline.
- **Attribution.** A desk that slips once, then handles every later ticket correctly on the state it produced, loses only the slipped ticket's checks:
  - refunding everything costs that ticket's cost rungs;
  - declining an accepted report costs its reply, make-good and cost rungs.

  Later tickets stay right when the slip changes their correct handling, for instance when the review threshold is then not reached.
- **Misreadings.** A desk that misreads one rule throughout loses the checks of the tickets the misreading touches, 5–22% of the shift.

L1 tickets `t01`–`t12` and the optimisation tickets `os1`–`ol4` are unchanged.

### Pilot 2026-10-22 (task 0.4.0)

Run `runs/suites/20261022-110927-dev-4749`: sh1 and sh2 on deepseek-flash, qwen3.8-flash and mimo-v2.6-flash. No grader defect was found.

| Model | Score | Median tokens per shift |
| --- | ---: | ---: |
| deepseek-flash | 100% | 1.33M |
| qwen3.8-flash | 100% | 1.70M |
| mimo-v2.6-flash | 82.5% | 0.88M |

**deepseek and qwen handled every planted trap.**

- The second report of the review customer went to `review`.
- The goodwill customer's second compensation was declined, and their make-good used no credit.
- The household's later shipment joined the free consolidation.
- Covered recall returns were refunded in full, and the uncovered recalled unit was made good by credit or a substitute.
- Every make-good was at the least cost.

**mimo** made one costlier make-good on sh1 (119.30 against 118.70). On sh2 it was stopped by its budget after T7 and gave no reply.

**Reading.** Coupling the tickets through derived conditions did not trip the strong models. They query the state they need, `show-orders`, `shipments` and `recalls`, and apply each rule as written, in order.
