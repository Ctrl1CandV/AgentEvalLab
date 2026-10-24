# Rubric: T2 Finance Desk

Each item is one close day for Kestrel Freight B.V. The books are about 45 open receivables and payables in EUR, USD, GBP and CHF, with purchase orders and accrued goods receipts, subscription contracts, bank lines and an inbox of vendor invoices. The queue holds eleven requests from colleagues, handled in order in one workspace with `ledger.py` under `MANUAL.md`:

- a payment plan for the next two weeks (first);
- four customer receipts;
- three vendor invoices;
- a credit note;
- September's deferred revenue;
- the September revaluation.

The manual defines every rule exactly, with its rounding. The tool checks only that entries are well formed: balanced, known accounts, and open-item lines that clear no more than is open.

Planted in every day:

- a foreign receipt that names another customer's invoice first and two of its own out of due order, short by more than the write-off limit, with a bank conversion cost;
- an early-payment discount with its VAT part, or a payment one day too late for it;
- an oldest-first allocation ending in a write-off within 5.00;
- an exact match by an alias from an unknown account, or a foreign overpayment after month-end;
- a duplicate vendor invoice under another spelling of its number;
- foreign goods spanning two accrued receipts, dated in the closed September AP period;
- a price variance within 2% but above 50.00 EUR (or the reverse), reverse-charged services, or an approval that fails on its limit or on segregation of duties;
- a credit note larger than the invoice's open amount;
- contracts that start, end, span or miss September;
- a revaluation that must count the September receipts but not the October ones, nor the vendor invoices posted into October;
- a payment plan over ten business days for 31–37 payables, with per-vendor discounts, late interest and fixed late fees, opening cash and inflows per currency, and a daily limit across currencies. Overdue payables lose worth every day, while discount and soon-due payables keep it until a deadline. The largest payable is disputed. The named plans are far apart, and single moves and swaps from the greedy plan fall short of the best.

## Checks

Each request is graded against the oracle (`private/finance.py`) run on the state of the books when the request began. The state is located by the `ledger.py begin R<n>` markers, or, without any marker, by the documents each command touches. So one mistake is deducted in the request where it was made.

- **Integrity (gate).** The delivered `data/books.json` equals a replay of `data/audit.log` through the item's `ledger.py` on the starting books.
- **`rN-outcome`** (critical): the reply's outcome for the request, and for a vendor invoice the status recorded with `set-status`.
- **`rN-allocation`** (critical, receipts and credit notes): which documents were cleared and by how much in their currencies, and which prepayment or suspense documents received money.
- **`rN-amounts`** (critical): every EUR amount the request's entries post, by account, partner and document (where the manual names them) and period. Lines may be split or combined, since only the net per key counts.
- **`rN-clean`** (critical): nothing posted on keys the request does not touch, and no status set on another invoice. It counts only once the request's own allocation or amounts pass.
- **`r1-plan-25`, `-50`, `-65`, `-80`, `-90`, `-97`, `-100`** (critical, the payment plan, each weighing 2): the worth of the last plan recorded is placed on a scale. The scale runs from paying by due date on the earliest day that fits (0), through paying by worth per unit of cash on the day of greatest worth (0.5), to the best plan known (1), which equals the exact optimum on all four days. Each check passes when the plan reaches that share of the scale. The plan's `r1-clean` passes when a plan was recorded, every `set-plan` came while R1 was the request under way, and R1 posted nothing.
- **`coverage`** (critical, the whole day; grader 1.2.0): every changing command (`post`, `set-plan`, `set-status`) belongs to exactly one request of the day, handled in the order given (manual §8). It fails on a change under an unknown request number, a change before the first `begin`, a change after a request was begun again once a later one had begun, and a change for a request begun after a later one. Repeating the `begin` of the request under way, or beginning a request and changing nothing, is no violation. Without any `begin` marker, each command must touch something of the request it is attributed to. It needs at least one changing command, so an untouched desk earns nothing. The evidence lists every violation.
- **`end-state`** (critical, the whole day; grader 1.2.0): the books from the original start equal a correctly handled day: the oracle run on every request from the same start gives the same footprint (net EUR per account, partner, document and period, and open-item amounts), the same invoice statuses, and the last plan recorded is one the books allow at the plan request. Its worth is graded by the rungs, not here. A slip anywhere fails it, while the per-request checks still locate the slip.
- **`answer-format`** (non-critical): the reply ends with one JSON object. A recovered reply loses 20%; a missing reply already fails every outcome.

A request that was never begun passes nothing. The score is the weighted fraction of critical checks passed (the plan's rungs weigh 2, every other check 1), less the format deduction. A day is resolved only when every critical check passes, `coverage` and `end-state` included.
