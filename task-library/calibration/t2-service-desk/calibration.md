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
