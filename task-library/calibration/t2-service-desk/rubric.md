# Rubric: T2 Service Desk

Each item is one customer ticket of two to four numbered requests, handled with a desk tool under a written policy, in the form of τ-bench without a simulated user. The tool checks only that records exist and that arguments are well formed; the policy is the agent's to apply, and its rules interact: verified sender addresses, coupon-reduced prices paid, refunds split between store credit and card in order, return windows by category and tier, tier-dependent restocking fees, exchanges against the price paid, price drops, late orders delivered or not, address changes, requests handled in sequence, unidentifiable requests, and doing nothing beyond the ticket.

## Checks

- **Integrity (gate).** The delivered `data/db.json` must equal a replay of `data/audit.log` through the original `desk.py` on the starting data. Otherwise every check fails: the data was changed some other way, or the tool was altered.
- **One critical check per order or customer the ticket should change.** It passes when that record equals the expected state, refunds compared in any order. The expected states come from the actions written by hand for each ticket; `private/oracle.py` derives the same actions from the policy and each request's structured intent, and the self-calibration checks that the two agree.
- **`no-other-changes`** (critical): every other record is unchanged. It counts only when the reply or some record check passes, because an untouched shop passes it.
- **`reply`** (critical): the final JSON lists exactly the done and the declined request numbers.
- **`answer-format`** (non-critical): the reply ends with one JSON object, bare or in a closing fenced block, as POLICY.md asks. Otherwise the shared recovery rule applies, and a recovered reply loses 20%. A missing or unusable reply fails `reply`; it is not also a format failure (grader 1.1.1).

The score is the fraction of critical checks passed, less the format deduction.

## Optimisation tickets (task 0.3.0)

Twelve tickets, `os1`–`os4` (level S), `om1`–`om4` (M) and `ol1`–`ol4` (L), report damaged and missing units under POLICY.md section 11. Each accepted unit is made good by sending the same product, sending a substitute of the same family priced at least at the unit price paid, a refund, or store credit at 110%. The policy asks for the resolution of the whole ticket that costs the shop least: products sent at cost, one carrier rate per delivery address that receives anything, refunds in full and credit at 70%. Stock is shared between orders, orders may share an address, and the customer may refuse credit, insist on the same model or bar an address. Levels grow by orders (1, 2, 3–4 plus a declined report on an old order), lines and units. The 0.2.0 tickets `t01`–`t12` stay as anchors.

- **Integrity (gate)**, as above.
- **`resolved-ORDER`** (critical), one per order with an accepted report: every reported unit made good, each with an option the policy and the customer allow.
- **`no-other-changes`** (critical): every command is a make-good of an accepted report, never more units than reported. It counts only when the reply or some order passes.
- **`reply`** (critical): the accepted reports as done, the others as declined.
- **`cost-5`, `cost-1`, `cost-0`** (critical): the resolution's cost is within 5% and 1% of the least cost, and equal to it (within half a cent). They count only when every order is resolved and nothing else changed. The least cost comes from `private/makegood.py`: for every set of addresses that may receive a shipment, a min-cost flow assigns units to products in stock or to their cheaper money option.
- **`answer-format`**, as above.

## Shifts (task 0.4.0)

Four items, `sh1`–`sh4`, are each a **shift**: eight tickets from six customers, handled in order in one workspace. Each shift has its own shop, a desk tool with dated make-goods, credits and shipments, and its own policy (`private/SHIFT_POLICY.md`). The policy keeps the 0.3.0 rules and adds four whose conditions must be derived and couple the tickets:

- **recalls**: a notice covers a product's units on orders placed within its dates and delivered to one of its countries. Covered units are returned whatever the window and made good only by refund, and a recalled product is never sent;
- **claims review**: when a customer already has three reports made good since 2026-07-22, the next report goes to `review`. Today's earlier tickets and this ticket's accepted reports count;
- **goodwill limit**: no store credit in a ticket for a customer with 80.00 or more of compensation and make-good credit since 2026-09-20, today's included;
- **consolidation**: an address that already received a shipment today costs no further carrier rate.

The generator plants the couplings:

- two households, whose members write in turn;
- a customer whose first compensation crosses the goodwill limit and who writes again;
- a customer one report short of review who writes twice;
- a recall that covers one order and misses another order of the same product;
- history entries on and just before the first counted day of each limit.

**Each ticket is graded against the oracle run on the state the model's own commands had produced when the ticket began.** The tickets are separated by the `desk.py begin T<n>` markers, or, without any marker, by the orders each command touches. So one mistake is deducted in the ticket where it was made: a later ticket is right when it is right for the shop as the model left it.

- **Integrity (gate)**: the delivered data equals a replay of the audit log through the shift's `desk.py`.
- **`tN-reply`** (critical): the reply's entry for the ticket lists exactly the done and the declined requests.
- **`tN-actions`** (critical, when the ticket has returns, compensations or reviews): exactly the oracle's, with a return split over several commands summed per line.
- **`tN-makegood`** (critical, when the ticket accepts reports): every accepted unit made good with an option the policy and the customer allow in that state.
- **`tN-cost-5`, `tN-cost-0`** (critical): the make-good's cost is within 5% of the least cost and equal to it, counted only when `tN-makegood` passes. The least cost counts free carriage to addresses already shipped to today.
- **`tN-clean`** (critical): nothing beyond the ticket. It counts only when the ticket's work passes, or, for a ticket that only declines, when its reply does.

A ticket that was never begun can pass only its reply. The **answer-format** check works as above, on the one JSON object for the whole shift.
