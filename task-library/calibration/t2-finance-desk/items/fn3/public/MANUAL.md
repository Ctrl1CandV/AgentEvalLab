# Finance desk manual: Kestrel Freight B.V.

You keep the books of Kestrel Freight B.V., a Dutch company whose functional currency is the euro (EUR). Today is **Monday 2026-10-05**, during the close of September 2026. You work with `python3 ledger.py` (run it without arguments for its commands). The tool records what you post and checks that entries are well formed; it does not check this manual. That is your job.

Every rule below is exact. Where a rule computes an amount, round **half up to cents** at the step it names, and nowhere else.

## 1. The books

An **entry** has a date, a memo and lines. Each line names an account and a debit or a credit in EUR. An entry's debits and credits are equal. Entries are posted with `ledger.py post FILE` (see its help for the JSON shape).

| Account | Name | Notes |
| --- | --- | --- |
| 1100 | Bank | All money in and out, in EUR |
| 1200 | Accounts receivable | Open-item lines: partner, document, currency, document amount |
| 1210 | Receivables revaluation | Lines name partner and document |
| 1300 | Input VAT recoverable | |
| 2000 | Accounts payable | Open-item lines: partner, document, currency, document amount |
| 2010 | Payables revaluation | Lines name partner and document |
| 2100 | Output VAT payable | |
| 2150 | Customer prepayments | Lines name partner and document |
| 2160 | Unidentified receipts | Lines name the bank line as document |
| 2200 | Goods received not invoiced | Lines name partner and the purchase order |
| 2400 | Deferred revenue | Lines name partner and the contract |
| 4000 | Revenue | |
| 4900 | Early-payment discounts | |
| 6000 | Operating expenses | |
| 6900 | Bank charges | |
| 6950 | Purchase price and rate variance | |
| 7900 | Realised exchange result | |
| 7910 | Unrealised exchange result | |

**Open items.** A line on 1200 or 2000 names a partner, a document, the document's currency and an amount in that currency, signed like the line: a receivable is opened by a debit and cleared by credits, a payable is opened by a credit and cleared by debits. A document's **open amount** is what its lines leave owed, in its currency, and its **EUR balance** is what they leave in EUR (both positive for an open receivable or payable). Its **carrying rate** is the rate of the day it was opened (its document date).

A clearing of part of a document is taken at the carrying rate: its EUR amount is the document amount cleared × the carrying rate, rounded half up. A clearing that settles a document (leaves its open amount at zero) takes instead whatever remains of its EUR balance, so that a settled document has no EUR balance left. When one entry clears a document several times, the clearings count in the order this manual names them (for a receipt: money, then discount, then write-off), so the last of them is the one that settles it.

**Periods.** The period of an entry is the month of its date. `ledger.py periods` shows, for September and October 2026, whether each ledger is open:

- the **AP** ledger: entries with a line on 2000;
- the **AR** ledger: entries with a line on 1200;
- the **GL**: every other entry.

An entry whose date falls in a period closed for its ledger is posted instead on the first day of the next period open for that ledger, keeping the document's own date for every rate and every rule below.

## 2. Exchange rates

`ledger.py rates CURRENCY` lists, for each business day (Monday to Friday), how many EUR one unit of the currency is worth, to six decimals. A weekend date uses the rate of the Friday before. The **month-end rate** of September is the rate of 2026-09-30.

The EUR amount of a document amount is the document amount × the rate, rounded half up to cents.

## 3. Customer receipts

`ledger.py bank` lists the bank lines. A **receipt** is a line with money in: its value date, the EUR amount credited to our account, the payer's name and IBAN, the remittance text, and, for a payment made in another currency, the original currency and amount.

**3.1 The payer.** The customer is the one whose IBANs include the payer's IBAN; failing that, the one whose name or one of whose aliases equals the payer's name, ignoring letter case. With no such customer, the whole receipt goes to 2160 (debit 1100, credit 2160, document the bank line).

**3.2 What is allocated.** A receipt is allocated in the currency it was paid in (the original currency, or EUR), and only to that customer's open receivables in that currency:

1. If the remittance text names invoices (`INV-` and digits), to those of them that are such receivables, in the order named, each up to the amount that settles it (3.3);
2. otherwise, to the one open invoice whose open amount equals the receipt exactly (several: the earliest due date, then the lowest number);
3. otherwise, to the open invoices by due date, earliest first (ties: the lowest number), each up to the amount that settles it.

Money left over after the invoices it may go to is a **prepayment**: a credit to 2150 (partner, document the bank line). Under 1., invoices that are not named never receive money.

**3.3 Early-payment discount.** For a customer with terms `2/10 net 30`, an invoice is settled at a discount of 2% of its gross amount (rounded half up in its currency) when the receipt's value date is at most 10 days after the invoice date, no earlier receipt has cleared any of it, and the money left for it covers its open amount less the discount. It then receives exactly that much money, and is cleared by the discount as well. The discount's VAT part is the discount × the invoice's VAT ÷ its gross amount (rounded half up in its currency): debit 2100 with it converted at the carrying rate (rounded half up), and 4900 with the rest of the discount clearing's EUR amount (section 1). When the money left does not cover it, there is no discount.

**3.4 Short payments.** When the money runs out on an invoice, after it has received some, and leaves it open by at most 5.00 in its currency, the shortfall is written off: the invoice is cleared by it, with 6900 debited with the EUR amount of that clearing. A larger shortfall stays open.

**3.5 Exchange differences.** Money cleared from an invoice is credited to 1200 at the carrying rate (section 1). The same money is worth its document amount × the receipt date's rate, rounded half up, in EUR: the difference goes to 7900 (a credit when the money is worth more). Discounts and write-offs are taken at the carrying rate only and have no exchange difference. A prepayment is credited to 2150 at the receipt date's rate. What then remains between the EUR the bank credited and the EUR value of all the money so allocated (at the receipt date's rate) is the bank's conversion cost (debit 6900) or gain (credit 6900).

**3.6 The entry.** One entry per receipt, dated at its value date: debit 1100 with the EUR received, the credits and debits above, each 1200 and 2150 line naming its partner and document.

## 4. Credit notes

A request may ask for a credit note on an invoice, for units of its lines (`ledger.py show-document INV-...` shows them). The credit note (its number is given) reverses those units at the invoice's prices and VAT rates, in the invoice's currency: per line, the net is units × unit price and the VAT the net × the line's rate, rounded half up in the currency. Its gross is the sum of both. In EUR, at the invoice's carrying rate: the gross and the VAT are each converted (rounded half up), and the net is the gross less the VAT. Debit 4000 with the net and 2100 with the VAT. The credit goes first to the invoice itself, up to its open amount (a clearing, section 1); the rest of the gross becomes customer credit (credit 2150, document the credit note, with the rest of the EUR). The entry is dated today.

## 5. Vendor invoices

`ledger.py inbox` lists incoming vendor invoices. A request asks you to process one. Its outcome is one of:

- **rejected**: a duplicate (5.1). Record it with `ledger.py set-status DOC rejected`; nothing is posted.
- **blocked**: it fails the match (5.2). `set-status DOC blocked`; nothing is posted.
- **held**: it needs an approval it does not have (5.3). `set-status DOC held`; nothing is posted.
- **posted**: otherwise. Post it (5.4, 5.5) and `set-status DOC posted`.

The checks run in this order; the first that applies decides.

**5.1 Duplicates.** An invoice is a duplicate when the same vendor already has a posted invoice (in the ledger or earlier in this queue) whose invoice number is the same after keeping only letters and digits, uppercasing, and removing leading zeros from each run of digits.

**5.2 The match.** Each line of an invoice with a purchase order names a purchase-order line. The quantity invoiced must not exceed the quantity received on that line (`ledger.py receipts PO`) less the quantity already invoiced on it by posted invoices. The unit price may differ from the order's: per line, the variance, (invoiced − ordered unit price) × quantity in the invoice's currency, converted at the invoice date's rate (rounded half up), must be, in absolute value, at most 2% of the ordered line value (ordered unit price × quantity, converted the same way) and at most 50.00. One failing line blocks the whole invoice. Invoices without a purchase order (services) are not matched.

**5.3 Approval.** An invoice whose gross amount in EUR (at the invoice date's rate) exceeds 5,000.00 needs an approval: the request must name an approver whose limit in `ledger.py approvers` is at least that amount and who is not the person who requested the purchase (`requested_by` on the invoice). Otherwise the invoice is held.

**5.4 VAT.**

- A vendor in the Netherlands charges VAT on the invoice: debit 1300 with its VAT in EUR.
- A vendor in another EU country with a VAT number charges none (reverse charge): self-assess 21% of the net amount in EUR, debiting 1300 and crediting 2100 with the same amount.
- A vendor outside the EU charges none. For services, self-assess as for the EU; for goods, nothing is posted (import VAT is settled at the border).

**5.5 The entry.** Amounts are converted at the invoice date's rate: the gross EUR is the gross amount converted, the invoice's VAT EUR its VAT converted (each rounded half up), and the net EUR the gross EUR less the invoice's VAT EUR. The entry is dated at the invoice date, unless the AP period is closed (section 1):

- credit 2000 with the gross EUR (partner the vendor, document the invoice's id `VINV-...`, its currency and gross amount);
- for goods on a purchase order: debit 2200 (partner the vendor, document the purchase order) with the amount accrued when the invoiced units were received, the earliest receipts' units not yet invoiced first (`ledger.py receipts PO` shows each receipt's accrued EUR per unit), and debit 6950 with the net EUR less that accrual (a credit when negative);
- for services: debit 6000 with the net EUR;
- the VAT lines of 5.4, with the self-assessed VAT being 21% of the net EUR, rounded half up.

## 6. Month-end

**6.1 Revaluation.** A request may ask for the September revaluation. It covers every receivable and payable in a currency other than EUR that is open at the end of September, counting only entries dated on or before 2026-09-30. For each, compare its open amount then, converted at the month-end rate (rounded half up), with its EUR balance then:

- a receivable: debit 1210 and credit 7910 with a rise (debit 7910 and credit 1210 with a fall);
- a payable: credit 2010 and debit 7910 with a rise (the reverse with a fall).

Each line names the partner and document; a zero difference gets no line. Post one entry dated 2026-09-30, and one dated 2026-10-01 that reverses it line for line.

**6.2 Deferred revenue.** Subscription contracts (`ledger.py contracts`) were invoiced in advance and their net amount in EUR credited to 2400. A request may ask for September's recognition. For each contract, September's share is its net EUR amount × the days of its service period that fall in September ÷ all days of its service period, rounded half up; for a contract whose service period ends in September, the share is what remains on 2400 for it. Post one entry dated 2026-09-30: per contract, debit 2400 (partner and contract) and credit 4000.

## 7. Requests

Requests come from colleagues in a queue. Handle them in the order given; each sees the effects of the earlier ones. Before changing anything for a request, run `ledger.py begin R3` (with its number), and change nothing for a request once you have begun the next. Do exactly what each request asks and this manual provides for; do not post anything else. Change `data/` only through `ledger.py`.

End with one JSON object that gives each request's outcome: `posted`, `rejected`, `blocked` or `held` for a vendor invoice, and `done` for any other request:

    {"R1": "done", "R2": "held", "R3": "posted"}
