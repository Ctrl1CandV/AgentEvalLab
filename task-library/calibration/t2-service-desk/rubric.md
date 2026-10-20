# Rubric: T2 Service Desk

Each item is one customer ticket of one to three numbered requests, handled with a desk tool under a written policy, in the form of τ-bench without a simulated user. The tool checks only that records exist and that arguments are well formed; the policy is the agent's to apply: who may ask, cancellation, return windows and restocking fees, refund methods, exchanges, late-delivery compensation, address changes, and doing nothing beyond the ticket.

## Checks

- **Integrity (gate).** The delivered `data/db.json` must equal a replay of `data/audit.log` through the original `desk.py` on the starting data. Otherwise every check fails: the data was changed some other way, or the tool was altered.
- **One critical check per order or customer the ticket should change.** It passes when that record equals the expected state, refunds compared in any order. The expected states come from the actions written by hand for each ticket.
- **`no-other-changes`** (critical): every other record is unchanged. It counts only when the reply or some record check passes, because an untouched shop passes it.
- **`reply`** (critical): the final JSON lists exactly the done and the declined request numbers.
- **`answer-format`** (non-critical): the reply is one JSON object. A recovered reply loses 20% (the shared recovery rule).

The score is the fraction of critical checks passed, less the format deduction.
