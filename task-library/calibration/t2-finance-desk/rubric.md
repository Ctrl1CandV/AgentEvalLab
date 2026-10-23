# Rubric: T2 Finance Desk

Each item is one close day for Kestrel Freight B.V. The books are about 45 open receivables and payables in EUR, USD, GBP and CHF, with purchase orders and accrued goods receipts, subscription contracts, bank lines and an inbox of vendor invoices. The queue holds ten requests from colleagues, handled in order in one workspace with `ledger.py` under `MANUAL.md`:

- four customer receipts;
- three vendor invoices;
- a credit note;
- September's deferred revenue;
- the September revaluation;
- today's payment run.

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
- a payment run whose cash and count bind: the three named plans are far apart, one payable is disputed, and the payables inside their discount window are among the ones the queue itself posted.

## Checks

Each request is graded against the oracle (`private/finance.py`) run on the state of the books when the request began. The state is located by the `ledger.py begin R<n>` markers, or, without any marker, by the documents each command touches. So one mistake is deducted in the request where it was made.

- **Integrity (gate).** The delivered `data/books.json` equals a replay of `data/audit.log` through the item's `ledger.py` on the starting books.
- **`rN-outcome`** (critical): the reply's outcome for the request, and for a vendor invoice the status recorded with `set-status`.
- **`rN-allocation`** (critical, receipts and credit notes): which documents were cleared and by how much in their currencies, and which prepayment or suspense documents received money.
- **`rN-amounts`** (critical): every EUR amount the request's entries post, by account, partner and document (where the manual names them) and period. Lines may be split or combined, since only the net per key counts.
- **`rN-clean`** (critical): nothing posted on keys the request does not touch, and no status set on another invoice. It counts only once the request's own allocation or amounts pass.
- **`rN-run-50`, `-80`, `-95`, `-100`** (critical, the payment run): the run's worth is placed between the three plans the manual names, paying by due date (0), paying by worth per unit of cash (0.5) and the most valuable set the run allows (1), and reaches that share of the scale. The run's own `rN-clean` passes when every payment is an open, undisputed payable and the request posts nothing else.
- **`answer-format`** (non-critical): the reply ends with one JSON object. A recovered reply loses 20%; a missing reply already fails every outcome.

A request that was never begun passes nothing. The score is the fraction of critical checks passed, less the format deduction.
