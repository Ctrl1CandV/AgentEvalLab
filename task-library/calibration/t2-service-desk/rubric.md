# Rubric: T2 Service Desk

Each item is one customer ticket of two to four numbered requests, handled with a desk tool under a written policy, in the form of τ-bench without a simulated user. The tool checks only that records exist and that arguments are well formed; the policy is the agent's to apply, and its rules interact: verified sender addresses, coupon-reduced prices paid, refunds split between store credit and card in order, return windows by category and tier, tier-dependent restocking fees, exchanges against the price paid, price drops, late orders delivered or not, address changes, requests handled in sequence, unidentifiable requests, and doing nothing beyond the ticket.

## Checks

- **Integrity (gate).** The delivered `data/db.json` must equal a replay of `data/audit.log` through the original `desk.py` on the starting data. Otherwise every check fails: the data was changed some other way, or the tool was altered.
- **One critical check per order or customer the ticket should change.** It passes when that record equals the expected state, refunds compared in any order. The expected states come from the actions written by hand for each ticket; `private/oracle.py` derives the same actions from the policy and each request's structured intent, and the self-calibration checks that the two agree.
- **`no-other-changes`** (critical): every other record is unchanged. It counts only when the reply or some record check passes, because an untouched shop passes it.
- **`reply`** (critical): the final JSON lists exactly the done and the declined request numbers.
- **`answer-format`** (non-critical): the reply ends with one JSON object, bare or in a closing fenced block, as POLICY.md asks. Otherwise the shared recovery rule applies, and a recovered reply loses 20%.

The score is the fraction of critical checks passed, less the format deduction.
