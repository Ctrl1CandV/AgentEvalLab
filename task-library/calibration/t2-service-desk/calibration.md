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
