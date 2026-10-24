"""T2 finance desk (task t2-finance-desk 0.3.0): the books of Kestrel Freight B.V. for the September 2026 close, a
queue of requests, and MANUAL.md as code.

An item is one close day: about 45 open receivables and payables in four currencies, purchase orders with accrued
goods receipts, subscription contracts, bank lines and an inbox of vendor invoices, and a queue of eleven requests:
a two-week payment plan, customer receipts, vendor invoices, a credit note, deferred revenue and the revaluation.
The payment plan is open-ended: it is placed on a scale between two named plans and the best plan known. The difficulty is in the
data and the rules together: exchange rates by document date with weekend fallbacks, carrying rates and settlement
rounding, an allocation order with an exact-match exception, early-payment discounts with their VAT, short-payment
write-offs, bank conversion costs, duplicate invoice numbers, a three-way match with a percentage and an absolute
tolerance, approval limits with segregation of duties, VAT by vendor country and supply, FIFO accruals, a closed AP
period, day-count recognition, and a revaluation that counts only entries up to the month's end.

The oracle applies the manual to a state of the books; the grader runs it on the state each request began from
(conditional grading, as for T2 shifts), so one mistake is deducted once.
"""
import copy
import datetime as dt
import hashlib
import json
import math
import random
import re
from decimal import ROUND_HALF_UP, Decimal

import ledger

TODAY = dt.date(2026, 10, 5)
MONTH_END = "2026-09-30"
CENT = Decimal("0.01")
ACCOUNTS = {"1100": "Bank", "1200": "Accounts receivable", "1210": "Receivables revaluation", "1300": "Input VAT recoverable",
            "2000": "Accounts payable", "2010": "Payables revaluation", "2100": "Output VAT payable", "2150": "Customer prepayments",
            "2160": "Unidentified receipts", "2200": "Goods received not invoiced", "2400": "Deferred revenue", "4000": "Revenue",
            "4900": "Early-payment discounts", "4910": "Purchase discounts received", "6000": "Operating expenses", "6900": "Bank charges", "6950": "Purchase price and rate variance",
            "7900": "Realised exchange result", "7910": "Unrealised exchange result"}
PARTNER_KEYED = {"1200", "2000", "1210", "2010", "2150", "2200", "2400"}
APPROVERS = [{"name": "Eva Jansen", "role": "Team lead", "limit": "5000.00"}, {"name": "Marta Kovacs", "role": "Finance manager", "limit": "25000.00"},
             {"name": "Pieter de Wit", "role": "CFO", "limit": "250000.00"}]
REQUESTERS = ["Eva Jansen", "Marta Kovacs", "Joris Bakker", "Sanne Visser", "Tomas Novak"]
EU = {"NL", "DE", "FR", "BE"}
D = Decimal


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def text(value):
    return f"{value:.2f}"


def day(value):
    return dt.date.fromisoformat(value)


# Rates and the state of the books.

def make_rates(rng):
    rates = {}
    for currency, start in (("USD", 0.9150), ("GBP", 1.1680), ("CHF", 1.0640)):
        value, series, current = start, {}, dt.date(2026, 6, 1)
        while current <= TODAY:
            if current.weekday() < 5:
                value *= 1 + rng.gauss(0, 0.0045)
                series[current.isoformat()] = f"{value:.6f}"
            current += dt.timedelta(days=1)
        rates[currency] = series
    return rates


def rate(books, currency, date):
    """EUR per unit on a date; a weekend takes the Friday before."""
    if currency == "EUR":
        return D(1)
    series, current = books["rates"][currency], day(date)
    while current.isoformat() not in series:
        current -= dt.timedelta(days=1)
    return D(series[current.isoformat()])


def items(books, as_of=None):
    """{document: {account, partner, currency, open, eur}} of open-item documents, counting entries up to `as_of`."""
    result = {}
    for entry in books["entries"]:
        if as_of is not None and entry["date"] > as_of:
            continue
        for line in entry["lines"]:
            if line["account"] in ledger.OPEN_ITEMS:
                item = result.setdefault(line["document"], {"account": line["account"], "partner": line["partner"], "currency": line["currency"],
                                                            "open": D(0), "eur": D(0)})
                sign = 1 if ("debit" in line) == (ledger.OPEN_ITEMS[line["account"]] == "debit") else -1
                item["open"] += sign * D(line["amount"])
                item["eur"] += sign * D(line.get("debit") or line.get("credit"))
    return result


def document_date(books, document):
    record = books["documents"].get(document) or books["inbox"].get(document)
    return record["date"]


class Entry:
    """An entry under construction; clearings follow section 1 (a settling clearing takes the EUR balance left)."""

    def __init__(self, books, date, memo):
        self.books, self.date, self.memo, self.lines = books, date, memo, []
        self.state = {key: dict(value) for key, value in items(books).items()}

    def line(self, account, amount, partner=None, document=None, currency=None, doc_amount=None):
        """A signed EUR amount: positive debits, negative credits; zero amounts add no line."""
        if amount == 0:
            return
        line = {"account": account, "debit" if amount > 0 else "credit": text(abs(amount))}
        if partner is not None:
            line["partner"] = partner
        if document is not None:
            line["document"] = document
        if currency is not None:
            line["currency"], line["amount"] = currency, text(doc_amount)
        self.lines.append(line)

    def open_item(self, account, partner, document, currency, doc_amount, eur):
        """Open a receivable (debit 1200) or a payable (credit 2000)."""
        self.state[document] = {"account": account, "partner": partner, "currency": currency, "open": doc_amount, "eur": eur}
        self.line(account, eur if account == "1200" else -eur, partner, document, currency, doc_amount)

    def clear(self, document, doc_amount):
        """Clear part of a document; returns the EUR amount (section 1)."""
        item = self.state[document]
        if doc_amount == item["open"]:
            eur = item["eur"]
        else:
            eur = cents(doc_amount * rate(self.books, item["currency"], document_date(self.books, document)))
        item["open"] -= doc_amount
        item["eur"] -= eur
        self.line(item["account"], -eur if item["account"] == "1200" else eur, item["partner"], document, item["currency"], doc_amount)
        return eur

    def done(self):
        assert sum(D(line.get("debit", "0")) - D(line.get("credit", "0")) for line in self.lines) == 0, self.lines
        return {"date": self.date, "memo": self.memo, "lines": self.lines}


def posting_date(books, date, ledger_name):
    """Section 1: a date in a period closed for the ledger moves to the first day of the next open period."""
    current = day(date)
    while books["periods"].get(current.strftime("%Y-%m"), {}).get(ledger_name) == "closed":
        current = (current.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    return current.isoformat()


# The manual's rules.

def identify(books, line):
    for key, partner in sorted(books["partners"].items()):
        if partner["kind"] == "customer" and line["iban"] in partner["ibans"]:
            return key
    for key, partner in sorted(books["partners"].items()):
        names = [partner["name"], *partner["aliases"]]
        if partner["kind"] == "customer" and any(name.lower() == line["payer"].lower() for name in names):
            return key
    return None


def receipt(books, bank_id, mistakes=()):
    """Section 3: the entry for one receipt."""
    line = next(item for item in books["bank"] if item["id"] == bank_id)
    entry = Entry(books, posting_date(books, line["date"], "AR"), f"Receipt {bank_id}")
    eur_received = D(line["eur"])
    entry.line("1100", eur_received)
    customer = identify(books, line)
    if customer is None:
        entry.line("2160", -eur_received, document=bank_id)
        return [entry.done()]
    currency = line["original"]["currency"] if line.get("original") else "EUR"
    money = D(line["original"]["amount"]) if line.get("original") else eur_received
    today_rate = rate(books, currency, line["date"])
    candidates = {key: item for key, item in entry.state.items()
                  if item["account"] == "1200" and item["partner"] == customer and item["currency"] == currency and item["open"] > 0}
    due = lambda key: (books["documents"][key]["due"], key)  # noqa: E731
    named = re.findall(r"INV-\d+", line["text"])
    if named and "oldest-first" not in mistakes:
        targets = [key for key in dict.fromkeys(named) if key in candidates]
    else:
        exact = sorted((key for key, item in candidates.items() if item["open"] == money), key=due)
        targets = exact[:1] if exact and "oldest-first" not in mistakes else sorted(candidates, key=due)
    terms = books["partners"][customer]["terms"]
    allocated_value = D(0)
    for key in targets:
        if money <= 0:
            break
        document = books["documents"][key]
        open_amount = entry.state[key]["open"]
        discount = None
        if terms == "2/10 net 30" and (day(line["date"]) - day(document["date"])).days <= 10 and not receipted(books, key) \
                and "no-discount" not in mistakes:
            candidate = cents(D(document["gross"]) * D("0.02"))
            if money >= open_amount - candidate:
                discount = candidate
        paid = open_amount - discount if discount is not None else min(money, open_amount)
        money -= paid
        cleared_eur = entry.clear(key, paid)
        value = cents(paid * today_rate)
        allocated_value += value
        entry.line("7900", cleared_eur - value)  # a gain (value above the carrying amount) is a credit
        if discount is not None:
            vat_part = cents(discount * D(document["vat"]) / D(document["gross"]))
            vat_eur = cents(vat_part * rate(books, currency, document["date"]))
            discount_eur = entry.clear(key, discount)
            entry.line("2100", vat_eur)
            entry.line("4900", discount_eur - vat_eur)
        shortfall = entry.state[key]["open"]
        if discount is None and money == 0 and paid > 0 and 0 < shortfall <= D("5.00") and "no-writeoff" not in mistakes:
            entry.line("6900", entry.clear(key, shortfall))
    if money > 0:
        prepayment = cents(money * today_rate)
        allocated_value += prepayment
        entry.line("2150", -prepayment, customer, bank_id)
    spread = eur_received - allocated_value
    entry.line("7900" if "spread-to-fx" in mistakes else "6900", -spread)
    return [entry.done()]


def receipted(books, document):
    """Whether a receipt (an entry with money in on 1100) has already cleared some of a document."""
    return any(any(line["account"] == "1100" and "debit" in line for line in entry["lines"]) and
               any(line.get("document") == document and line["account"] == "1200" and "credit" in line for line in entry["lines"])
               for entry in books["entries"])


def credit_note(books, request):
    """Section 4."""
    invoice = books["documents"][request["invoice"]]
    entry = Entry(books, posting_date(books, TODAY.isoformat(), "AR"), f"Credit note {request['number']}")
    net = vat = D(0)
    for index, units in request["units"].items():
        row = invoice["lines"][int(index)]
        line_net = D(units) * D(row["unit_price"])
        net += line_net
        vat += cents(line_net * D(row["vat_rate"]))
    gross = net + vat
    carrying = rate(books, invoice["currency"], invoice["date"])
    gross_eur, vat_eur = cents(gross * carrying), cents(vat * carrying)
    entry.line("4000", gross_eur - vat_eur)
    entry.line("2100", vat_eur)
    applied = min(entry.state[request["invoice"]]["open"], gross)
    applied_eur = entry.clear(request["invoice"], applied) if applied > 0 else D(0)
    entry.line("2150", -(gross_eur - applied_eur), invoice["partner"], request["number"])
    return [entry.done()]


def normalized_number(number):
    return "".join(re.sub(r"^0+(?=\d)", "", run) if run.isdigit() else run.upper() for run in re.findall(r"[A-Za-z]+|\d+", number))


def vendor_outcome(books, inbox_id, approver, mistakes=()):
    """Section 5: (outcome, entries)."""
    invoice = books["inbox"][inbox_id]
    vendor = books["partners"][invoice["vendor"]]
    posted = [record for record in list(books["documents"].values()) + list(books["inbox"].values())
              if record.get("type") == "vendor-invoice" and record["vendor"] == invoice["vendor"] and record.get("status") == "posted"]
    if any(normalized_number(record["number"]) == normalized_number(invoice["number"]) for record in posted):
        return "rejected", []
    invoice_rate = rate(books, invoice["currency"], invoice["date"])
    if invoice.get("po"):
        order = books["documents"][invoice["po"]]
        for row in invoice["lines"]:
            ordered = order["lines"][row["po_line"]]
            received = sum(receipt_row["qty"] for receipt_row in books["receipts"] if receipt_row["po"] == invoice["po"] and receipt_row["line"] == row["po_line"])
            if row["qty"] > received - invoiced(books, invoice["po"], row["po_line"]):
                return "blocked", []
            variance = cents((D(row["unit_price"]) - D(ordered["unit_price"])) * row["qty"] * invoice_rate)
            value = cents(D(ordered["unit_price"]) * row["qty"] * invoice_rate)
            if abs(variance) > value * D("0.02") or abs(variance) > D("50.00"):
                return "blocked", []
    gross_eur = cents(D(invoice["gross"]) * invoice_rate)
    if gross_eur > D("5000.00"):
        limits = {item["name"]: D(item["limit"]) for item in books["approvers"]}
        if approver not in limits or limits[approver] < gross_eur or approver == invoice["requested_by"]:
            return "held", []
    date = invoice["date"] if "no-closed-period" in mistakes else posting_date(books, invoice["date"], "AP")
    entry = Entry(books, date, f"Vendor invoice {inbox_id}")
    vat_eur = cents(D(invoice["vat"]) * invoice_rate)
    net_eur = gross_eur - vat_eur
    entry.open_item("2000", invoice["vendor"], inbox_id, invoice["currency"], D(invoice["gross"]), gross_eur)
    if invoice.get("po"):
        accrual = D(0)
        for row in invoice["lines"]:
            accrual += fifo_accrual(books, invoice["po"], row["po_line"], row["qty"])
        entry.line("2200", accrual, invoice["vendor"], invoice["po"])
        entry.line("6950", net_eur - accrual)
    else:
        entry.line("6000", net_eur)
    if vendor["country"] == "NL":
        entry.line("1300", vat_eur)
    elif (vendor["country"] in EU and vendor.get("vat_id")) or invoice["category"] == "services":
        self_assessed = cents(net_eur * D("0.21"))
        entry.line("1300", self_assessed)
        entry.line("2100", -self_assessed)
    return "posted", [entry.done()]


def invoiced(books, po, po_line):
    return sum(row["qty"] for record in list(books["documents"].values()) + list(books["inbox"].values())
               if record.get("type") == "vendor-invoice" and record.get("po") == po and record.get("status") == "posted"
               for row in record["lines"] if row["po_line"] == po_line)


def fifo_accrual(books, po, po_line, quantity):
    """The EUR accrued for `quantity` units of a purchase-order line, earliest receipts' uninvoiced units first."""
    already = invoiced(books, po, po_line)
    total = D(0)
    for row in sorted((item for item in books["receipts"] if item["po"] == po and item["line"] == po_line), key=lambda item: (item["date"], item["id"])):
        skip = min(already, row["qty"])
        already -= skip
        take = min(quantity, row["qty"] - skip)
        total += take * D(row["accrued_per_unit"])
        quantity -= take
        if quantity == 0:
            break
    return total


def deferred(books):
    """Section 6.2."""
    entry = Entry(books, posting_date(books, MONTH_END, "GL"), "Deferred revenue, September")
    remaining = {}
    for record in books["entries"]:
        for line in record["lines"]:
            if line["account"] == "2400":
                remaining[line["document"]] = remaining.get(line["document"], D(0)) + D(line.get("credit") or "0") - D(line.get("debit") or "0")
    total = D(0)
    for key, contract in sorted(books["contracts"].items()):
        start, end = day(contract["start"]), day(contract["end"])
        overlap = (min(end, dt.date(2026, 9, 30)) - max(start, dt.date(2026, 9, 1))).days + 1
        if overlap <= 0 or remaining.get(key, D(0)) <= 0:
            continue
        if end.strftime("%Y-%m") == "2026-09":
            share = remaining[key]
        else:
            share = cents(D(contract["net_eur"]) * overlap / ((end - start).days + 1))
        entry.line("2400", share, contract["partner"], key)
        total += share
    entry.line("4000", -total)
    return [entry.done()]


def revaluation(books, mistakes=()):
    """Section 6.1: the month-end entry and its reversal."""
    as_of = None if "revalue-now" in mistakes else MONTH_END
    entry = Entry(books, MONTH_END, "Revaluation, September")
    total = D(0)
    for key, item in sorted(items(books, as_of).items()):
        if item["currency"] == "EUR" or item["open"] <= 0:
            continue
        difference = cents(item["open"] * rate(books, item["currency"], MONTH_END)) - item["eur"]
        if difference == 0:
            continue
        if item["account"] == "1200":
            entry.line("1210", difference, item["partner"], key)
            total += difference
        else:
            entry.line("2010", -difference, item["partner"], key)
            total -= difference
    entry.line("7910", -total)
    first = entry.done()
    reverse = {"date": "2026-10-01", "memo": "Revaluation reversal", "lines": [
        {key: value for key, value in line.items() if key not in ("debit", "credit")} | ({"credit": line["debit"]} if "debit" in line else {"debit": line["credit"]})
        for line in first["lines"]]}
    return [first, reverse] if first["lines"] else []


def handle(books, request, mistakes=()):
    """The oracle for one request on a state: {entries, statuses, outcome}."""
    kind = request["kind"]
    if kind == "payment-plan":
        problem = PlanProblem(books)
        slots = naive_plan(problem) if "pay-by-due-date" in mistakes else best_plan(problem)[1]
        return {"entries": [], "plan": problem.schedule(slots), "statuses": {}, "outcome": "done"}
    if kind == "receipt":
        return {"entries": receipt(books, request["bank"], mistakes), "statuses": {}, "outcome": "done"}
    if kind == "credit-note":
        return {"entries": credit_note(books, request), "statuses": {}, "outcome": "done"}
    if kind == "deferred":
        return {"entries": deferred(books), "statuses": {}, "outcome": "done"}
    if kind == "revaluation":
        return {"entries": revaluation(books, mistakes), "statuses": {}, "outcome": "done"}
    outcome, entries = vendor_outcome(books, request["inbox"], request.get("approver"), mistakes)
    return {"entries": entries, "statuses": {request["inbox"]: outcome}, "outcome": outcome}


def apply_result(books, request, result):
    """The books after a request's result, through the tool's own commands."""
    ledger.apply(books, "begin", [request["id"]])
    for entry in result["entries"]:
        ledger.apply(books, "post", [entry])
    if "plan" in result:
        ledger.apply(books, "set-plan", [result["plan"]])
    for document, status in result["statuses"].items():
        ledger.apply(books, "set-status", [document, status])
    return books


def commands_of(request, result):
    return [["begin", request["id"]]] + [["post", entry] for entry in result["entries"]] + \
        ([["set-plan", result["plan"]]] if "plan" in result else []) + \
        [["set-status", document, status] for document, status in result["statuses"].items()]


def run(books, requests, mistakes=()):
    books = copy.deepcopy(books)
    results = []
    for request in requests:
        result = handle(books, request, mistakes)
        results.append((copy.deepcopy(books), result))
        apply_result(books, request, result)
    return results, books


# Grading.

def footprint(entries):
    """What entries do: per (account, partner, document, period) the net EUR, and per open-item document the net
    document amount. Partner and document count only on the accounts the manual keys by them."""
    eur, documents = {}, {}
    for entry in entries:
        period = entry["date"][:7]
        for line in entry["lines"]:
            account = line["account"]
            partner = line.get("partner") if account in PARTNER_KEYED else None
            document = line.get("document") if account in PARTNER_KEYED or account == "2160" else None
            key = (account, partner, document, period)
            eur[key] = eur.get(key, D(0)) + D(line.get("debit") or "0") - D(line.get("credit") or "0")
            if account in ledger.OPEN_ITEMS:
                doc_key = (account, partner, document, line.get("currency"))
                sign = 1 if "debit" in line else -1
                documents[doc_key] = documents.get(doc_key, D(0)) + sign * D(line["amount"])
    return {key: value for key, value in eur.items() if value != 0}, {key: value for key, value in documents.items() if value != 0}


def where(entries):
    """The allocation view: open-item document amounts, and which partner accounts and documents received EUR."""
    eur, documents = footprint(entries)
    return documents, sorted({key[:3] for key in eur if key[0] in ("2150", "2160", "2200", "2400", "1210", "2010")})


def segments(commands, requests, books):
    """Each request's commands, by begin markers; without markers, by the documents the commands touch."""
    by_request, start = {}, {}
    if any(command[0] == "begin" for command in commands):
        current = None
        for position, command in enumerate(commands):
            if command[0] == "begin":
                current = command[1]
                start.setdefault(current, position)
                by_request.setdefault(current, [])
            elif current is not None:
                by_request[current].append(command)
        return by_request, start
    pointer = 0
    payment_plan = next((request["id"] for request in requests if request["kind"] == "payment-plan"), None)
    for position, command in enumerate(commands):
        # Only the payment plan sets a plan, so its commands need no other mark.
        if command[0] == "set-plan" and payment_plan is not None:
            start.setdefault(payment_plan, position)
            by_request.setdefault(payment_plan, []).append(command)
            continue
        touched = touched_by(command)
        later = [index for index in range(pointer, len(requests)) if touched & owned(requests[index], books)]
        if later:
            pointer = later[0]
        request_id = requests[pointer]["id"]
        start.setdefault(request_id, position)
        by_request.setdefault(request_id, []).append(command)
    return by_request, start


def touched_by(command):
    if command[0] == "set-status":
        return {command[1]}
    if command[0] == "post" and isinstance(command[1], dict):
        return {line.get("document") for line in command[1].get("lines", []) if isinstance(line, dict)} - {None} | {"@" + command[1].get("date", "")}
    return set()


def owned(request, books):
    if request["kind"] == "payment-plan":
        return set()
    if request["kind"] == "receipt":
        line = next(item for item in books["bank"] if item["id"] == request["bank"])
        customer = identify(books, line)
        return {request["bank"]} | {key for key, record in books["documents"].items() if record.get("partner") == customer and customer}
    if request["kind"] == "vendor":
        return {request["inbox"]}
    if request["kind"] == "credit-note":
        return {request["invoice"], request["number"]}
    if request["kind"] == "deferred":
        return set(books["contracts"])
    return {"@" + MONTH_END, "@2026-10-01"}


def check_names(requests):
    """Per request, then the two checks of the whole day (grader 1.2.0): coverage and end state."""
    names = []
    for request in requests:
        prefix = request["id"].lower()
        names.append(f"{prefix}-outcome")
        if request["kind"] == "payment-plan":
            names += [f"{prefix}-plan-{label}" for label, _ in PLAN_RUNGS] + [f"{prefix}-clean"]
            continue
        if request["kind"] in ("receipt", "credit-note"):
            names.append(f"{prefix}-allocation")
        names += [f"{prefix}-amounts", f"{prefix}-clean"]
    return names + list(DAY_CHECKS)


DAY_CHECKS = ("coverage", "end-state")


def coverage(commands, requests, books):
    """Manual §8: every changing command belongs to exactly one request of the day, handled in the order given; once the
    next request is begun, nothing changes for an earlier one. Returns the violations, each {position, command,
    request, rule}; repeating the begin of the request under way is not a violation, nor is a begun request that
    changes nothing. Without any begin marker, each command must touch something of the request it is attributed to
    (the same attribution the per-request grading uses)."""
    order = {request["id"]: index for index, request in enumerate(requests)}
    violations = []
    if any(command[0] == "begin" for command in commands):
        history, current, rule_now = [], None, "before-first-begin"
        for position, command in enumerate(commands):
            if command[0] == "begin":
                request_id = command[1]
                if history and history[-1] == request_id:
                    continue
                if request_id not in order:
                    rule_now = "unknown-request"
                elif request_id in history:
                    rule_now = "reopened-request"
                elif any(order.get(other, -1) > order[request_id] for other in history):
                    rule_now = "out-of-order"
                else:
                    rule_now = None
                history.append(request_id)
                current = request_id
                continue
            if rule_now:
                violations.append({"position": position, "command": command[0], "request": current, "rule": rule_now})
        return violations
    pointer = 0
    plans = any(request["kind"] == "payment-plan" for request in requests)
    for position, command in enumerate(commands):
        if command[0] == "set-plan" and plans:
            continue
        touched = touched_by(command)
        later = [index for index in range(pointer, len(requests)) if touched & owned(requests[index], books)]
        if later:
            pointer = later[0]
            continue
        violations.append({"position": position, "command": command[0], "request": requests[pointer]["id"], "rule": "unattributed"})
    return violations


def end_state(base, requests, commands):
    """The day's books from the original start, against the oracle handling every request right from the same start:
    the same net postings per account, partner, document and period and the same open-item amounts (the footprint the
    per-request checks use, so lines may be split or combined), the same invoice statuses, and a payment plan recorded
    that the books at the plan request allow. Any plan the books allow counts here; its worth is graded by the rungs."""
    results, expected_books = run(base, requests)
    delivered = copy.deepcopy(base)
    for command in commands:
        ledger.apply(delivered, command[0], command[1:])
    start = len(base["entries"])
    statuses = lambda books: {key: item["status"] for key, item in books["inbox"].items()}
    detail = {"postings": footprint(delivered["entries"][start:]) == footprint(expected_books["entries"][start:]),
              "statuses": statuses(delivered) == statuses(expected_books)}
    for request, (state, _) in zip(requests, results):
        if request["kind"] == "payment-plan":
            plans = [command for command in commands if command[0] == "set-plan"]
            problem = PlanProblem(state)
            detail["plan"] = bool(plans) and isinstance(plans[-1][1], dict) and plan_value(problem, problem.slots_of(plans[-1][1])) is not None
    return detail


def day_checks(base, requests, commands):
    """({coverage, end-state}, evidence). Coverage needs at least one changing command, so that an untouched desk earns
    nothing; it fails on any violation, the end state on any difference."""
    violations = coverage(commands, requests, base)
    changes = [command for command in commands if command[0] != "begin"]
    detail = end_state(base, requests, commands)
    return ({"coverage": bool(changes) and not violations, "end-state": all(detail.values())},
            {"violations": violations[:50], "violationCount": len(violations), "changingCommands": len(changes), "endState": detail})


def grade(base, requests, commands, reply, evidence=None):
    """Per request, against the oracle on the state when it began: outcome (reply and, for vendor invoices, status),
    allocation (receipts and credit notes: which documents, how much in their currencies), amounts (every EUR line by
    account, partner, document and period) and clean (nothing else changed; counts only once the request's own
    work passes). Then the whole day (grader 1.2.0): coverage and end state (day_checks), whose evidence goes into
    `evidence` when given."""
    by_request, start = segments(commands, requests, base)
    results, state = {}, copy.deepcopy(base)
    for request in requests:
        prefix = request["id"].lower()
        if request["id"] in start:
            state = copy.deepcopy(base)
            for command in commands[:start[request["id"]]]:
                ledger.apply(state, command[0], command[1:])
        mine = by_request.get(request["id"], [])
        begun = request["id"] in start
        entries = [command[1] for command in mine if command[0] == "post"]
        statuses = {command[1]: command[2] for command in mine if command[0] == "set-status"}
        given = reply.get(request["id"]) if isinstance(reply, dict) else None
        if request["kind"] == "payment-plan":
            # The plan is the last one recorded, on the books as the request found them; a plan set while another
            # request was under way breaks the request order and costs the request its clean check.
            plans = [command for command in commands if command[0] == "set-plan"]
            own = {id(command) for command in mine}
            begun = begun or bool(plans)
            results[f"{prefix}-outcome"] = begun and isinstance(given, str) and given.strip().lower() == "done"
            place = plan_place(state, plans[-1][1]) if plans else D(0)
            for label, threshold in PLAN_RUNGS:
                results[f"{prefix}-plan-{label}"] = begun and place >= threshold
            results[f"{prefix}-clean"] = begun and bool(plans) and all(id(command) in own for command in plans) and not entries and not statuses
            for command in mine:
                ledger.apply(state, command[0], command[1:])
            continue
        expected = handle(state, request)
        outcome_ok = begun and isinstance(given, str) and given.strip().lower() == expected["outcome"] and \
            (request["kind"] != "vendor" or statuses == expected["statuses"])
        results[f"{prefix}-outcome"] = outcome_ok
        if request["kind"] in ("receipt", "credit-note"):
            results[f"{prefix}-allocation"] = begun and where(entries) == where(expected["entries"])
        amounts_ok = begun and footprint(entries) == footprint(expected["entries"]) and (request["kind"] != "vendor" or statuses == expected["statuses"])
        results[f"{prefix}-amounts"] = amounts_ok
        unexpected_status = any(document not in expected["statuses"] for document in statuses)
        work = [results[name] for name in (f"{prefix}-allocation", f"{prefix}-amounts") if name in results]
        results[f"{prefix}-clean"] = begun and not unexpected_status and any(work) and \
            set(footprint(entries)[0]) <= set(footprint(expected["entries"])[0])
        for command in mine:
            ledger.apply(state, command[0], command[1:])
    day, detail = day_checks(base, requests, commands)
    results.update(day)
    if evidence is not None:
        evidence.update(detail)
    return results


# Generation.

CUSTOMER_PLAN = [("NL", "EUR", "net 30"), ("NL", "EUR", "2/10 net 30"), ("NL", "EUR", "net 30"), ("NL", "EUR", "2/10 net 30"), ("NL", "EUR", "net 30"),
                 ("DE", "EUR", "net 30"), ("DE", "EUR", "2/10 net 30"), ("BE", "EUR", "net 30"), ("FR", "EUR", "net 30"),
                 ("US", "USD", "net 30"), ("US", "USD", "2/10 net 30"), ("UK", "GBP", "net 30"), ("CH", "CHF", "net 30")]
VENDOR_PLAN = [("NL", "EUR", "goods"), ("NL", "EUR", "services"), ("DE", "EUR", "goods"), ("FR", "EUR", "services"), ("UK", "GBP", "services"),
               ("US", "USD", "goods"), ("CH", "CHF", "goods")]
WORDS = ["Amber", "Basalt", "Cobalt", "Delta", "Ember", "Fjord", "Granite", "Harbor", "Indigo", "Juniper", "Kelvin", "Lumen", "Meridian", "Nimbus",
         "Orchid", "Pioneer", "Quarry", "Ridge", "Summit", "Tundra", "Umber", "Vertex", "Willow", "Zenith"]
SUFFIX = {"NL": "B.V.", "DE": "GmbH", "BE": "BV", "FR": "SAS", "US": "Inc.", "UK": "Ltd", "CH": "AG"}
TRADES = ["Logistics", "Retail", "Foods", "Systems", "Supplies", "Trading", "Packaging", "Marine", "Parts", "Labs"]


def weekday_between(rng, first, last):
    while True:
        value = first + dt.timedelta(days=rng.randrange((last - first).days + 1))
        if value.weekday() < 5:
            return value


def opening(books, record, revenue_account="4000"):
    """The entry that issued a customer invoice: debit 1200 gross, credit revenue (or 2400) net and 2100 VAT."""
    carrying = rate(books, record["currency"], record["date"])
    gross_eur, vat_eur = cents(D(record["gross"]) * carrying), cents(D(record["vat"]) * carrying)
    entry = Entry(books, record["date"], f"Invoice {record['id']}")
    entry.open_item("1200", record["partner"], record["id"], record["currency"], D(record["gross"]), gross_eur)
    entry.line(revenue_account, -(gross_eur - vat_eur), record["partner"] if revenue_account == "2400" else None,
               record.get("contract") if revenue_account == "2400" else None)
    entry.line("2100", -vat_eur)
    return entry.done(), gross_eur - vat_eur


def invoice_lines(rng, country, count, subscription=False):
    lines = []
    for index in range(count):
        quantity = 1 if subscription else rng.randrange(1, 13)
        price = D(rng.randrange(2500, 150000)) / 100 if not subscription else D(rng.randrange(120000, 960000)) / 100
        vat_rate = rng.choice(["0.21", "0.21", "0.09"]) if country == "NL" else "0.00"
        lines.append({"description": "Annual subscription" if subscription else f"{rng.choice(['Freight', 'Handling', 'Storage', 'Customs filing', 'Insurance'])} {index + 1}",
                      "qty": quantity, "unit_price": text(price), "vat_rate": vat_rate})
    return lines


def totals(lines):
    net = sum((D(line["unit_price"]) * line["qty"] for line in lines), D(0))
    vat = sum((cents(D(line["unit_price"]) * line["qty"] * D(line["vat_rate"])) for line in lines), D(0))
    return net, vat, net + vat


class Builder:
    def __init__(self, rng):
        self.rng = rng
        self.books = {"company": {"name": "Kestrel Freight B.V.", "country": "NL", "vat_id": "NL861234567B01", "currency": "EUR"},
                      "today": TODAY.isoformat(), "accounts": ACCOUNTS,
                      "periods": {"2026-08": {"AP": "closed", "AR": "closed", "GL": "closed"}, "2026-09": {"AP": "closed", "AR": "open", "GL": "open"},
                                  "2026-10": {"AP": "open", "AR": "open", "GL": "open"}},
                      "rates": make_rates(rng), "partners": {}, "documents": {}, "receipts": [], "contracts": {}, "approvers": APPROVERS,
                      "bank": [], "inbox": {}, "entries": []}
        self.numbers = iter(rng.sample(range(5001, 5999), 400))
        self.bank_numbers = iter(rng.sample(range(100, 999), 300))

    def post(self, entry):
        ledger.apply(self.books, "post", [entry])

    def name(self, country):
        return f"{self.rng.choice(WORDS)} {self.rng.choice(TRADES)} {SUFFIX[country]}"

    def partners(self):
        used = set()
        for index, (country, currency, terms) in enumerate(CUSTOMER_PLAN):
            name = self.name(country)
            while name in used:
                name = self.name(country)
            used.add(name)
            short = name.split()[0]
            self.books["partners"][f"C-{101 + index}"] = {
                "kind": "customer", "name": name, "aliases": [name.upper().replace(".", ""), f"{short} {name.split()[1]}"], "country": country,
                "vat_id": f"{country}{self.rng.randrange(10 ** 8, 10 ** 9)}" if country in EU else None, "currency": currency, "terms": terms,
                "ibans": [f"{country if country != 'UK' else 'GB'}{self.rng.randrange(10, 99)}BANK{self.rng.randrange(10 ** 9, 10 ** 10)}"]}
        for index, (country, currency, supply) in enumerate(VENDOR_PLAN):
            name = self.name(country)
            while name in used:
                name = self.name(country)
            used.add(name)
            discounting = self.rng.random() < 0.6
            days, share = self.rng.choice([(7, "0.03"), (10, "0.02"), (14, "0.01")])
            self.books["partners"][f"V-{201 + index}"] = {"kind": "vendor", "name": name, "country": country, "currency": currency, "supply": supply,
                                                         "vat_id": f"{country}{self.rng.randrange(10 ** 8, 10 ** 9)}" if country in EU else None,
                                                         "terms": f"{int(D(share) * 100)}/{days} net 30" if discounting else "net 30",
                                                         "discount_days": days if discounting else None,
                                                         "discount_rate": share if discounting else None,
                                                         "late_rate": self.rng.choice(["0.0003", "0.0005", "0.0008", "0.0012"]),
                                                         "late_fee": self.rng.choice(["0.00", "40.00", "75.00"])}

    def invoice(self, customer, date, lines=None, subscription=None):
        partner = self.books["partners"][customer]
        lines = lines or invoice_lines(self.rng, partner["country"], self.rng.randrange(1, 4))
        net, vat, gross = totals(lines)
        number = f"INV-{next(self.numbers)}"
        record = {"type": "invoice", "id": number, "partner": customer, "date": date.isoformat(), "due": (date + dt.timedelta(days=30)).isoformat(),
                  "currency": partner["currency"], "lines": lines, "net": text(net), "vat": text(vat), "gross": text(gross)}
        if subscription:
            record["contract"] = subscription
        self.books["documents"][number] = record
        entry, net_eur = opening(self.books, record, "2400" if subscription else "4000")
        self.post(entry)
        return number, net_eur

    def bank_line(self, date, customer, eur, currency=None, amount=None, text_value="Payment", payer=None, iban=None, posted=False):
        partner = self.books["partners"][customer] if customer else None
        line = {"id": f"BNK-{date.strftime('%m%d')}-{next(self.bank_numbers)}", "date": date.isoformat(), "eur": text(eur),
                "payer": payer or (partner["name"] if partner else "Unknown"), "iban": iban or (partner["ibans"][0] if partner else "NL00BANK0000000000"),
                "text": text_value, "original": {"currency": currency, "amount": text(amount)} if currency and currency != "EUR" else None, "posted": posted}
        self.books["bank"].append(line)
        return line["id"]

    def history(self):
        """Customer invoices from mid-July on, some paid in part or in full; contracts; purchase orders, receipts and
        posted vendor invoices; a few payables paid."""
        rng, books = self.rng, self.books
        for customer in sorted(key for key, partner in books["partners"].items() if partner["kind"] == "customer"):
            for _ in range(rng.randrange(3, 5)):
                self.invoice(customer, weekday_between(rng, dt.date(2026, 7, 13), dt.date(2026, 9, 25)))
        for key in sorted(books["documents"]):
            record = books["documents"][key]
            if record["date"] < "2026-09-10" and rng.random() < 0.3:
                paid_on = day(record["date"]) + dt.timedelta(days=rng.randrange(12, 40))
                if paid_on > dt.date(2026, 9, 25):
                    continue
                gross = D(record["gross"])
                amount = gross if rng.random() < 0.5 else cents(gross * D(rng.randrange(30, 70)) / 100)
                eur = cents(amount * rate(books, record["currency"], paid_on.isoformat()))
                line = self.bank_line(paid_on, record["partner"], eur, record["currency"], amount, f"Payment {key}", posted=True)
                for entry in receipt(books, line):
                    self.post(entry)
        # Subscription contracts, invoiced in advance, recognised for past months.
        periods = [(dt.date(2026, 7, 1), dt.date(2027, 6, 30)), (dt.date(2026, 8, 15), dt.date(2026, 9, 14)), (dt.date(2026, 9, 10), dt.date(2027, 3, 9)),
                   (dt.date(2026, 10, 1), dt.date(2027, 9, 30)), (dt.date(2026, 3, 1), dt.date(2026, 8, 31)), (dt.date(2026, 6, 16), dt.date(2026, 12, 15))]
        customers = [key for key, partner in sorted(books["partners"].items()) if partner["kind"] == "customer"]
        for index, (start, end) in enumerate(periods):
            contract = f"CTR-{7001 + index}"
            customer = rng.choice(customers)
            issued = min(start, dt.date(2026, 9, 25)) if start > dt.date(2026, 7, 1) else dt.date(2026, 7, 1)
            number, net_eur = self.invoice(customer, issued, invoice_lines(rng, books["partners"][customer]["country"], 1, subscription=True), contract)
            books["contracts"][contract] = {"id": contract, "partner": customer, "invoice": number, "start": start.isoformat(), "end": end.isoformat(),
                                            "net_eur": text(net_eur)}
            month = dt.date(2026, 7, 1)
            recognised = D(0)
            while month < dt.date(2026, 9, 1):
                last = (month + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
                overlap = (min(end, last) - max(start, month)).days + 1
                if overlap > 0 and month >= start.replace(day=1) and issued <= last:
                    share = net_eur - recognised if end <= last else cents(net_eur * overlap / ((end - start).days + 1))
                    if share > 0:
                        entry = Entry(books, last.isoformat(), f"Deferred revenue, {month:%B}")
                        entry.line("2400", share, customer, contract)
                        entry.line("4000", -share)
                        self.post(entry.done())
                        recognised += share
                month = last + dt.timedelta(days=1)
        # Purchase orders, goods receipts with their accruals, and posted vendor invoices.
        vendors = {key: partner for key, partner in books["partners"].items() if partner["kind"] == "vendor"}
        po_number = iter(range(6101, 6200))
        for key, vendor in sorted(vendors.items()):
            if vendor["supply"] != "goods":
                continue
            for _ in range(rng.randrange(1, 3)):
                po = f"PO-{next(po_number)}"
                lines = [{"line": index, "item": f"{rng.choice(['Pallets', 'Straps', 'Crates', 'Labels', 'Seals', 'Liners'])} {index + 1}",
                          "qty": rng.randrange(20, 80), "unit_price": text(D(rng.randrange(500, 40000)) / 100)} for index in range(rng.randrange(2, 4))]
                books["documents"][po] = {"type": "purchase-order", "id": po, "vendor": key, "date": "2026-08-03", "currency": vendor["currency"],
                                          "requested_by": rng.choice(REQUESTERS), "lines": lines}
                for row in lines:
                    left = row["qty"]
                    for receipt_index in range(rng.randrange(1, 3)):
                        quantity = left if receipt_index else max(1, left // rng.randrange(2, 4))
                        received = weekday_between(rng, dt.date(2026, 8, 10), dt.date(2026, 9, 25))
                        per_unit = cents(D(row["unit_price"]) * rate(books, vendor["currency"], received.isoformat()))
                        identifier = f"GR-{len(books['receipts']) + 1:04d}"
                        books["receipts"].append({"id": identifier, "po": po, "line": row["line"], "date": received.isoformat(), "qty": quantity,
                                                  "accrued_per_unit": text(per_unit)})
                        entry = Entry(books, received.isoformat(), f"Goods received {identifier}")
                        entry.line("6000", per_unit * quantity)
                        entry.line("2200", -per_unit * quantity, key, po)
                        self.post(entry.done())
                        left -= quantity
                        if left <= 0:
                            break
                books["receipts"].sort(key=lambda item: (item["date"], item["id"]))
        vinv = iter(range(101, 300))
        for key, vendor in sorted(vendors.items()):
            for _ in range(rng.randrange(1, 3)):
                self.vendor_invoice(key, weekday_between(rng, dt.date(2026, 8, 20), dt.date(2026, 9, 18)), f"VINV-{next(vinv)}", history=True)
        self.vinv = vinv
        self.open_payables(vendors)

    def open_payables(self, vendors):
        """Payables for the payment plan: fresh ones inside their discount window or with nothing to gain, ones falling
        due within the plan's two weeks, and overdue ones, in sizes that differ, so that when each is paid decides the
        plan's worth."""
        rng = self.rng
        services = [key for key, vendor in sorted(vendors.items()) if vendor["supply"] == "services"]
        for key, vendor in sorted(vendors.items()):
            for profile in ("fresh", "fresh", "due-soon", "due-soon", "overdue", "late"):
                if rng.random() < 0.3:
                    continue
                issued = {"fresh": TODAY - dt.timedelta(days=rng.randrange(0, 9)),
                          "due-soon": TODAY + dt.timedelta(days=rng.randrange(1, 12) - 30),
                          "overdue": TODAY - dt.timedelta(days=rng.randrange(33, 45)),
                          "late": TODAY - dt.timedelta(days=rng.randrange(50, 70))}[profile]
                amount = D(rng.choice([rng.randrange(40000, 120000), rng.randrange(150000, 400000), rng.randrange(450000, 900000)])) / 100
                identifier = f"VINV-{next(self.vinv)}"
                if key in services or vendor["supply"] == "services":
                    self.vendor_invoice(key, issued, identifier, history=True, gross_target=amount, approver="Pieter de Wit")
                else:
                    # Goods without a purchase order are recorded as a service accrual, so the plan has payables in every
                    # currency without disturbing the three-way match of the queue's own invoices.
                    self.service_payable(key, issued, identifier, amount)

    def service_payable(self, vendor_key, issued, identifier, amount):
        """An open payable posted straight to operating expenses, with the vendor's own terms and a 30-day due date."""
        books, vendor = self.books, self.books["partners"][vendor_key]
        vat = cents(amount * D("0.21")) if vendor["country"] == "NL" else D(0)
        gross = amount + vat
        record = {"type": "vendor-invoice", "id": identifier, "vendor": vendor_key, "number": f"S{self.rng.randrange(1000, 9999)}",
                  "date": issued.isoformat(), "due": (issued + dt.timedelta(days=30)).isoformat(), "currency": vendor["currency"],
                  "category": "services", "po": None, "requested_by": "Marta Kovacs", "status": "posted",
                  "lines": [{"po_line": None, "description": "Freight handling", "qty": 1, "unit_price": text(amount), "vat_rate": "0.21" if vat else "0.00"}],
                  "net": text(amount), "vat": text(vat), "gross": text(gross)}
        books["documents"][identifier] = record
        invoice_rate = rate(books, vendor["currency"], record["date"])
        gross_eur, vat_eur = cents(gross * invoice_rate), cents(vat * invoice_rate)
        entry = Entry(books, record["date"], f"Vendor invoice {identifier}")
        entry.open_item("2000", vendor_key, identifier, vendor["currency"], gross, gross_eur)
        entry.line("6000", gross_eur - vat_eur)
        if vat_eur:
            entry.line("1300", vat_eur)
        self.post(entry.done())

    def vendor_invoice(self, vendor_key, date, identifier, history=False, number=None, prices=None, quantities=None, po=None, approver=None,
                       requested_by=None, gross_target=None):
        """A vendor invoice; history invoices are posted at once and recorded among the documents."""
        rng, books = self.rng, self.books
        vendor = books["partners"][vendor_key]
        record = {"type": "vendor-invoice", "id": identifier, "vendor": vendor_key, "number": number or f"{rng.choice(['', 'INV', 'F'])}{rng.randrange(2026, 2027)}-{rng.randrange(10, 9999):04d}",
                  "date": date.isoformat(), "due": (date + dt.timedelta(days=30)).isoformat(),
                  "currency": vendor["currency"], "category": vendor["supply"], "po": None, "lines": [],
                  "requested_by": requested_by or rng.choice(REQUESTERS), "status": "new"}
        if vendor["supply"] == "goods":
            orders = [key for key, item in books["documents"].items() if item.get("type") == "purchase-order" and item["vendor"] == vendor_key]
            po = po or rng.choice(orders)
            order = books["documents"][po]
            record["po"], record["requested_by"] = po, order["requested_by"]
            for row in order["lines"]:
                available = sum(item["qty"] for item in books["receipts"] if item["po"] == po and item["line"] == row["line"]) - invoiced(books, po, row["line"])
                quantity = (quantities or {}).get(row["line"], min(available, rng.randrange(5, 30)))
                if quantity <= 0:
                    continue
                price = (prices or {}).get(row["line"], D(row["unit_price"]))
                record["lines"].append({"po_line": row["line"], "description": row["item"], "qty": quantity, "unit_price": text(price), "vat_rate": "0.21" if vendor["country"] == "NL" else "0.00"})
        else:
            amount = gross_target or D(rng.randrange(40000, 400000)) / 100
            record["lines"].append({"po_line": None, "description": rng.choice(["Customs brokerage", "IT support", "Consulting", "Audit fees", "Software licences"]),
                                    "qty": 1, "unit_price": text(amount), "vat_rate": "0.21" if vendor["country"] == "NL" else "0.00"})
        if not record["lines"]:
            return None
        net, vat, gross = totals(record["lines"])
        record.update(net=text(net), vat=text(vat), gross=text(gross))
        books["inbox"][identifier] = record
        if history:
            outcome, entries = vendor_outcome(books, identifier, approver or "Pieter de Wit", ("no-closed-period",))
            del books["inbox"][identifier]
            if outcome != "posted":
                return None
            for entry in entries:
                self.post(entry)
            record["status"] = "posted"
            books["documents"][identifier] = record
            if rng.random() < 0.15:  # paid in full at the carrying amount
                state = items(books)[identifier]
                payment = {"date": min(date + dt.timedelta(days=rng.randrange(5, 20)), dt.date(2026, 9, 28)).isoformat(), "memo": f"Payment {identifier}",
                           "lines": [{"account": "2000", "debit": text(state["eur"]), "partner": vendor_key, "document": identifier,
                                      "currency": state["currency"], "amount": text(state["open"])}, {"account": "1100", "credit": text(state["eur"])}]}
                self.post(payment)
        return identifier


PLAN_DAYS = tuple(when.isoformat() for when in (TODAY + dt.timedelta(days=offset) for offset in range(12)) if when.weekday() < 5)
PLAN_LATER = "2026-10-19"  # the first business day after the plan: every payable it does not schedule is paid then
PLAN_RUNGS = (("25", D("0.25")), ("50", D("0.5")), ("65", D("0.65")), ("80", D("0.8")), ("90", D("0.9")), ("97", D("0.97")), ("100", D("1")))
KNOWN_BEST = {}  # problem signature -> (value in cents, slots); the build stores the searched plans in days.json


def record_of(books, key):
    """A document's record, whether it is in the ledger's documents or still in the inbox."""
    return books["documents"].get(key) or books["inbox"].get(key)


def late_charge(books, record, when):
    """The late charge of a payable paid on `when`, in its currency: the vendor's fixed fee once it is past due, plus its
    daily rate on the gross amount for each calendar day after the due date (rounded half up)."""
    vendor = books["partners"][record["vendor"]]
    days = (day(when) - day(record["due"])).days
    if days <= 0:
        return D(0)
    return D(vendor.get("late_fee") or "0") + cents(D(record["gross"]) * D(vendor.get("late_rate") or "0") * days)


def plan_table(books):
    """{document: (currency, due, {day: (cash used, worth in EUR)})} of the payables a plan may schedule. A payment's
    worth is what paying on its day saves against paying on the day after the plan: the late charge avoided and the
    discount gained, at today's rate."""
    settings = books["payment_plan"]
    table = {}
    for key, facts in ledger.payables(books).items():
        if facts["disputed"]:
            continue
        record = record_of(books, key)
        today_rate = rate(books, facts["currency"], TODAY.isoformat())
        later = late_charge(books, record, settings["later"]) - ledger.discount_on(books, record, settings["later"])
        options = {}
        for when in settings["days"]:
            discount = ledger.discount_on(books, record, when)
            options[when] = (D(facts["open"]) - discount, cents((later - late_charge(books, record, when) + discount) * today_rate))
        table[key] = (facts["currency"], record["due"], options)
    return table


class PlanProblem:
    """A payment plan in whole cents: per payable its currency and, per day of the plan, the cash it uses and its worth;
    per currency the cash available by the end of each day (the opening cash and the inflows so far)."""

    def __init__(self, books):
        settings = books["payment_plan"]
        self.days = list(settings["days"])
        self.limit = settings["max_per_day"]
        table = plan_table(books)
        self.docs = sorted(table)
        self.currencies = sorted({table[key][0] for key in self.docs})
        self.currency = [self.currencies.index(table[key][0]) for key in self.docs]
        self.due = [table[key][1] for key in self.docs]
        self.cost = [[int(table[key][2][when][0] * 100) for when in self.days] for key in self.docs]
        self.worth = [[int(table[key][2][when][1] * 100) for when in self.days] for key in self.docs]
        self.available = []
        for currency in self.currencies:
            running, row = D(settings["opening"].get(currency, "0")), []
            for when in self.days:
                running += D(settings["inflows"].get(currency, {}).get(when, "0"))
                row.append(int(running * 100))
            self.available.append(row)

    def signature(self):
        rows = [self.days, self.limit, self.currencies, self.available, [list(row) for row in zip(self.docs, self.currency, self.cost, self.worth)]]
        return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

    def slots_of(self, schedule):
        """A schedule {document: day} as slots (day index, or -1), or None when it names a payable or day outside the plan."""
        slots = [-1] * len(self.docs)
        index = {key: position for position, key in enumerate(self.docs)}
        for key, when in schedule.items():
            if key not in index or when not in self.days:
                return None
            slots[index[key]] = self.days.index(when)
        return slots

    def schedule(self, slots):
        return {self.docs[position]: self.days[slot] for position, slot in enumerate(slots) if slot >= 0}


class PlanState:
    """Slots with their spending per currency and day, their counts per day and their worth, for the searches."""

    def __init__(self, problem, slots):
        self.problem = problem
        self.slot = list(slots)
        self.spend = [[0] * len(problem.days) for _ in problem.currencies]
        self.count = [0] * len(problem.days)
        self.value = 0
        for position, slot in enumerate(self.slot):
            if slot >= 0:
                self.add(position, slot)

    def add(self, position, slot):
        self.slot[position] = slot
        self.spend[self.problem.currency[position]][slot] += self.problem.cost[position][slot]
        self.count[slot] += 1
        self.value += self.problem.worth[position][slot]

    def remove(self, position):
        slot = self.slot[position]
        self.spend[self.problem.currency[position]][slot] -= self.problem.cost[position][slot]
        self.count[slot] -= 1
        self.value -= self.problem.worth[position][slot]
        self.slot[position] = -1

    def cash_holds(self, currency):
        running, available = 0, self.problem.available[currency]
        for slot, spent in enumerate(self.spend[currency]):
            running += spent
            if running > available[slot]:
                return False
        return True

    def valid(self):
        return all(count <= self.problem.limit for count in self.count) and all(self.cash_holds(currency) for currency in range(len(self.problem.currencies)))

    def fits(self, position, slot):
        """Whether the payable fits on the day, given the rest of the plan."""
        if self.count[slot] >= self.problem.limit:
            return False
        self.add(position, slot)
        holds = self.cash_holds(self.problem.currency[position])
        self.remove(position)
        return holds


def naive_plan(problem):
    """0 on the scale: the payables by due date, earliest first (ties by document), each on the earliest day the cash
    and the daily limit allow."""
    state = PlanState(problem, [-1] * len(problem.docs))
    for position in sorted(range(len(problem.docs)), key=lambda index: (problem.due[index], problem.docs[index])):
        for slot in range(len(problem.days)):
            if state.fits(position, slot):
                state.add(position, slot)
                break
    return state.slot


def greedy_plan(problem):
    """0.5 on the scale: the payables by their best worth per unit of cash on any day, highest first (ties by document),
    each on the day, of those the cash and the daily limit still allow, on which it is worth the most (ties: the
    earliest), unless it is worth nothing there."""
    def ratio(position):
        return max(D(problem.worth[position][slot]) / problem.cost[position][slot] if problem.cost[position][slot] else D(0)
                   for slot in range(len(problem.days)))
    state = PlanState(problem, [-1] * len(problem.docs))
    for position in sorted(range(len(problem.docs)), key=lambda index: (-ratio(index), problem.docs[index])):
        open_days = [slot for slot in range(len(problem.days)) if state.fits(position, slot)]
        if not open_days:
            continue
        slot = max(open_days, key=lambda day_index: (problem.worth[position][day_index], -day_index))
        if problem.worth[position][slot] > 0:
            state.add(position, slot)
    return state.slot


def improve(problem, slots):
    """Local search: moves of one payable to another day (or out of the plan) and swaps of two payables' days, taking
    any that raises the worth, until none does."""
    state = PlanState(problem, slots)
    count, improved = len(problem.docs), True
    while improved:
        improved = False
        for position in range(count):
            for slot in range(len(problem.days)):
                old = state.slot[position]
                if problem.worth[position][slot] <= (problem.worth[position][old] if old >= 0 else 0):
                    continue
                if old >= 0:
                    state.remove(position)
                if state.fits(position, slot):
                    state.add(position, slot)
                    improved = True
                    break
                if old >= 0:
                    state.add(position, old)
        for first in range(count):
            for second in range(first + 1, count):
                a, b = state.slot[first], state.slot[second]
                if a == b:
                    continue
                gain = (problem.worth[first][b] if b >= 0 else 0) + (problem.worth[second][a] if a >= 0 else 0) - \
                    (problem.worth[first][a] if a >= 0 else 0) - (problem.worth[second][b] if b >= 0 else 0)
                if gain <= 0:
                    continue
                for position in (first, second):
                    if state.slot[position] >= 0:
                        state.remove(position)
                if b >= 0:
                    state.add(first, b)
                if a >= 0:
                    state.add(second, a)
                if state.valid():
                    improved = True
                    continue
                for position in (first, second):
                    if state.slot[position] >= 0:
                        state.remove(position)
                if a >= 0:
                    state.add(first, a)
                if b >= 0:
                    state.add(second, b)
    return state.slot


def anneal(problem, slots, rng, steps):
    """Simulated annealing over the same moves and swaps; returns the best slots it met."""
    state = PlanState(problem, slots)
    best_value, best_slots = state.value, list(state.slot)
    options = [[slot for slot in range(len(problem.days)) if problem.worth[position][slot] > 0] for position in range(len(problem.docs))]
    movable = [position for position in range(len(problem.docs)) if options[position]]
    if not movable:
        return best_value, best_slots
    scale = max(1, sum(max(problem.worth[position]) for position in movable) // len(movable))

    def worth(position, slot):
        return problem.worth[position][slot] if slot >= 0 else 0

    for step in range(steps):
        temperature = scale * 0.5 * (1 - step / steps) + 1
        if rng.random() < 0.5:
            position = rng.choice(movable)
            old, new = state.slot[position], rng.choice(options[position] + [-1])
            if new == old:
                continue
            delta = worth(position, new) - worth(position, old)
            if delta < 0 and rng.random() >= math.exp(delta / temperature):
                continue
            if old >= 0:
                state.remove(position)
            if new >= 0:
                if state.count[new] >= problem.limit:
                    state.add(position, old) if old >= 0 else None
                    continue
                state.add(position, new)
                if not state.cash_holds(problem.currency[position]):
                    state.remove(position)
                    if old >= 0:
                        state.add(position, old)
                    continue
        else:
            first, second = rng.sample(movable, 2)
            a, b = state.slot[first], state.slot[second]
            if a == b or (b >= 0 and b not in options[first]) or (a >= 0 and a not in options[second]):
                continue
            delta = worth(first, b) + worth(second, a) - worth(first, a) - worth(second, b)
            if delta < 0 and rng.random() >= math.exp(delta / temperature):
                continue
            for position in (first, second):
                if state.slot[position] >= 0:
                    state.remove(position)
            if b >= 0:
                state.add(first, b)
            if a >= 0:
                state.add(second, a)
            if not (state.cash_holds(problem.currency[first]) and state.cash_holds(problem.currency[second])):
                for position in (first, second):
                    if state.slot[position] >= 0:
                        state.remove(position)
                if a >= 0:
                    state.add(first, a)
                if b >= 0:
                    state.add(second, b)
                continue
        if state.value > best_value:
            best_value, best_slots = state.value, list(state.slot)
    return best_value, best_slots


def rebuild(problem, slots, rng, rounds):
    """Large-neighbourhood search: take a few payables out of the plan, then put every unscheduled payable back, in a
    random order, on its day of greatest worth that still fits; keep the result when it is worth no less."""
    state = PlanState(problem, slots)
    worthwhile = [position for position in range(len(problem.docs)) if max(problem.worth[position]) > 0]
    best_value, best_slots = state.value, list(state.slot)
    for _ in range(rounds):
        before_value, before = state.value, list(state.slot)
        scheduled = [position for position in worthwhile if state.slot[position] >= 0]
        for position in rng.sample(scheduled, min(len(scheduled), rng.randrange(1, 6))):
            state.remove(position)
        waiting = [position for position in worthwhile if state.slot[position] < 0]
        rng.shuffle(waiting)
        for position in waiting:
            fitting = [slot for slot in range(len(problem.days)) if problem.worth[position][slot] > 0 and state.fits(position, slot)]
            if fitting:
                state.add(position, max(fitting, key=lambda slot: (problem.worth[position][slot], rng.random())))
        if state.value < before_value:
            state = PlanState(problem, before)
        elif state.value > best_value:
            best_value, best_slots = state.value, list(state.slot)
    return best_value, best_slots


def search_best(problem, steps=400000, restarts=8, rounds=6000):
    """The best plan known: annealing from the greedy plan, the naive plan's worthwhile part and an empty plan, each
    polished by local search; deterministic for a problem."""
    rng = random.Random(problem.signature())
    naive = [slot if slot >= 0 and problem.worth[position][slot] > 0 else -1 for position, slot in enumerate(naive_plan(problem))]
    starts = [greedy_plan(problem), naive, [-1] * len(problem.docs)]
    best = (PlanState(problem, starts[0]).value, starts[0])
    for index in range(restarts):
        value, slots = anneal(problem, starts[index % len(starts)], rng, steps)
        if rounds:
            value, slots = rebuild(problem, slots, rng, rounds)
        slots = improve(problem, slots)
        value = PlanState(problem, slots).value
        if value > best[0]:
            best = (value, slots)
    return best


def best_plan(problem):
    """(value in cents, slots) of the best plan known for the problem."""
    key = problem.signature()
    if key not in KNOWN_BEST:
        KNOWN_BEST[key] = search_best(problem)
    return KNOWN_BEST[key]


def plan_value(problem, slots):
    """A valid plan's worth in cents, or None for a plan the problem does not allow."""
    if slots is None:
        return None
    state = PlanState(problem, slots)
    return state.value if state.valid() else None


def plan_place(books, schedule):
    """A plan's place between the naive plan (0), the greedy plan (0.5) and the best known (1)."""
    problem = PlanProblem(books)
    value = plan_value(problem, problem.slots_of(schedule) if isinstance(schedule, dict) else None)
    if value is None:
        return D(0)
    naive_value = PlanState(problem, naive_plan(problem)).value
    greedy_value = PlanState(problem, greedy_plan(problem)).value
    best_value = max(best_plan(problem)[0], greedy_value)
    if value >= greedy_value:
        if greedy_value >= best_value or value >= best_value:
            return D(1)
        return D("0.5") + D("0.5") * D(value - greedy_value) / D(best_value - greedy_value)
    if naive_value >= greedy_value:
        return D(0)
    return max(D(0), D("0.5") * D(value - naive_value) / D(greedy_value - naive_value))


COLLEAGUES = {"receipt": "Anna de Boer, receivables", "credit-note": "Anna de Boer, receivables", "vendor": "Jonas Smit, payables",
              "deferred": "Lotte Mulder, controller", "revaluation": "Lotte Mulder, controller", "payment-plan": "Jonas Smit, payables"}


class Unsuitable(Exception):
    pass


def open_receivables(books, customer, currency=None):
    return {key: item for key, item in items(books).items()
            if item["account"] == "1200" and item["partner"] == customer and item["open"] > 0 and (currency is None or item["currency"] == currency)}


def customers_with(books, currency=None, terms=None, minimum=2, country=None):
    found = []
    for key, partner in sorted(books["partners"].items()):
        if partner["kind"] != "customer" or (currency and partner["currency"] != currency) or (terms and partner["terms"] != terms):
            continue
        if country and partner["country"] != country:
            continue
        if len(open_receivables(books, key, partner["currency"])) >= minimum:
            found.append(key)
    return found


def due_order(books, keys):
    return sorted(keys, key=lambda key: (books["documents"][key]["due"], key))


def queue(builder):
    """Ten requests with planted hard points; raises Unsuitable when the drawn books cannot host one."""
    rng, books = builder.rng, builder.books
    requests = []

    def add(kind, text_value, **fields):
        requests.append({"id": f"R{len(requests) + 1}", "kind": kind, "text": text_value, **fields})

    # Receipts. A foreign receipt naming an ineligible invoice first, then two of the customer's in an order other than
    # their due dates, short by more than the write-off limit, with a bank conversion cost.
    foreign = [key for key in customers_with(books, terms="net 30", minimum=2) if books["partners"][key]["currency"] != "EUR"]
    if not foreign:
        raise Unsuitable("foreign")
    customer = rng.choice(foreign)
    currency = books["partners"][customer]["currency"]
    first, second = due_order(books, open_receivables(books, customer, currency))[:2]
    stranger = rng.choice([key for key, record in books["documents"].items() if record.get("type") == "invoice" and record["partner"] != customer])
    state = items(books)
    shortfall = D(rng.randrange(600, 6000)) / 100
    if state[first]["open"] <= shortfall + 1:
        raise Unsuitable("short invoice")
    money = state[first]["open"] + state[second]["open"] - shortfall
    paid_on = dt.date(2026, 9, 29)
    eur = cents(money * rate(books, currency, paid_on.isoformat()) * (1 - D(rng.randrange(20, 60)) / 10000))
    line = builder.bank_line(paid_on, customer, eur, currency, money, f"Settlement {stranger} {second} {first}")
    receipts = [("named", line)]
    # An early-payment discount on a fresh invoice, or a payment one day too late for it.
    discounting = [key for key, partner in sorted(books["partners"].items()) if partner["kind"] == "customer" and partner["terms"] == "2/10 net 30"
                   and partner["currency"] == "EUR" and partner["country"] == "NL"]
    customer = rng.choice(discounting)
    late = rng.random() < 0.3
    issued = dt.date(2026, 9, rng.choice([21, 22, 23]))
    number, _ = builder.invoice(customer, issued, invoice_lines(rng, "NL", 3))
    record = books["documents"][number]
    discount = cents(D(record["gross"]) * D("0.02"))
    paid_on = issued + dt.timedelta(days=11 if late else rng.choice([9, 10]))
    money = D(record["gross"]) - discount
    receipts.append(("late-discount" if late else "discount", builder.bank_line(paid_on, customer, money, text_value=f"{number} less 2% discount")))
    # Oldest first, ending in a write-off within the limit; no single invoice equals the money.
    plain = [key for key in customers_with(books, currency="EUR", terms="net 30", minimum=3)]
    if not plain:
        raise Unsuitable("plain")
    customer = rng.choice(plain)
    ordered = due_order(books, open_receivables(books, customer, "EUR"))
    state = items(books)
    small = D(rng.randrange(50, 499)) / 100
    money = state[ordered[0]]["open"] + state[ordered[1]]["open"] - small
    if any(item["open"] == money for item in open_receivables(books, customer, "EUR").values()):
        raise Unsuitable("exact clash")
    receipts.append(("oldest", builder.bank_line(dt.date(2026, 9, 30), customer, money, text_value="Payment outstanding items")))
    # One more: an alias with an unknown account paying a later invoice exactly, or a foreign overpayment after month-end.
    if rng.random() < 0.5:
        others = [key for key in customers_with(books, currency="EUR", minimum=2) if key not in (customer,)]
        target_customer = rng.choice(others)
        ordered = due_order(books, open_receivables(books, target_customer, "EUR"))
        target = ordered[-1]
        amount = items(books)[target]["open"]
        if sum(1 for item in open_receivables(books, target_customer, "EUR").values() if item["open"] == amount) > 1:
            raise Unsuitable("twin amounts")
        partner = books["partners"][target_customer]
        receipts.append(("alias", builder.bank_line(dt.date(2026, 9, 30), target_customer, amount, text_value=f"Ref {rng.randrange(1000, 9999)}",
                                                    payer=partner["aliases"][0], iban=f"NL{rng.randrange(10, 99)}BANK{rng.randrange(10 ** 9, 10 ** 10)}")))
    else:
        overseas = [key for key in customers_with(books, minimum=1) if books["partners"][key]["currency"] in ("GBP", "CHF")]
        if not overseas:
            raise Unsuitable("overseas")
        target_customer = rng.choice(overseas)
        currency = books["partners"][target_customer]["currency"]
        target = due_order(books, open_receivables(books, target_customer, currency))[0]
        money = items(books)[target]["open"] + D(rng.randrange(2000, 30000)) / 100
        receipts.append(("overpaid", builder.bank_line(dt.date(2026, 10, 1), target_customer, cents(money * rate(books, currency, "2026-10-01")), currency, money,
                                                       f"Invoice {target}")))
    receipts.sort(key=lambda pair: next(item["date"] for item in books["bank"] if item["id"] == pair[1]))
    for trap, line in receipts:
        add("receipt", f"Please book the receipt on bank line {line}.", bank=line, trap=trap)
    # Vendor invoices: a duplicate under another spelling of its number; foreign goods spanning two receipts, dated in the
    # closed September; and one of a tolerance block, reverse-charged services or a missing approval.
    posted = [record for record in books["documents"].values() if record.get("type") == "vendor-invoice"]
    original = rng.choice(posted)
    digits = re.findall(r"\d+", original["number"])
    variant = original["number"].lower().replace("-", " / ")
    variant = re.sub(r"\d+", lambda match: "0" + match.group(0), variant, count=1) if digits else variant + "-A"
    if normalized_number(variant) != normalized_number(original["number"]):
        raise Unsuitable("variant")
    duplicate = builder.vendor_invoice(original["vendor"], dt.date(2026, 10, 1), f"VINV-{next(builder.vinv)}", number=variant, po=original.get("po"))
    vendors = []
    if duplicate:
        vendors.append(("duplicate", duplicate, None))
    goods = next(key for key, partner in sorted(books["partners"].items()) if partner["kind"] == "vendor" and partner["currency"] == "USD")
    spanning = None
    for po, order in sorted(books["documents"].items()):
        if order.get("type") != "purchase-order" or order["vendor"] != goods:
            continue
        for row in order["lines"]:
            receipts_rows = [item for item in books["receipts"] if item["po"] == po and item["line"] == row["line"]]
            already = invoiced(books, po, row["line"])
            if len(receipts_rows) >= 2 and receipts_rows[0]["qty"] > already and receipts_rows[0]["accrued_per_unit"] != receipts_rows[1]["accrued_per_unit"]:
                spanning = (po, row, receipts_rows[0]["qty"] - already + rng.randrange(1, receipts_rows[1]["qty"] + 1))
                break
        if spanning:
            break
    if not spanning:
        raise Unsuitable("fifo")
    po, row, quantity = spanning
    price = D(row["unit_price"]) * (1 + D(rng.randrange(1, 15)) / 1000)
    price = cents(price)
    goods_invoice = builder.vendor_invoice(goods, dt.date(2026, 9, rng.choice([28, 29])), f"VINV-{next(builder.vinv)}", po=po,
                                           quantities={other["line"]: (quantity if other["line"] == row["line"] else 0) for other in books["documents"][po]["lines"]},
                                           prices={row["line"]: price})
    vendors.append(("fifo-closed-period", goods_invoice, rng.choice([None, "Eva Jansen"])))
    choice = rng.choice(["tolerance", "reverse-charge", "approval"])
    if choice == "tolerance":
        swiss = next(key for key, partner in sorted(books["partners"].items()) if partner["kind"] == "vendor" and partner["currency"] == "CHF")
        orders = [key for key, item in sorted(books["documents"].items()) if item.get("type") == "purchase-order" and item["vendor"] == swiss]
        po = rng.choice(orders)
        row = max(books["documents"][po]["lines"], key=lambda item: D(item["unit_price"]) * item["qty"])
        available = sum(item["qty"] for item in books["receipts"] if item["po"] == po and item["line"] == row["line"]) - invoiced(books, po, row["line"])
        if available < 5:
            raise Unsuitable("tolerance stock")
        # Within 2% but above 50.00 EUR, or the other way round.
        value = D(row["unit_price"]) * available * rate(books, "CHF", "2026-10-01")
        bump = D("0.019") if value * D("0.019") > 55 else D("0.025")
        identifier = builder.vendor_invoice(swiss, dt.date(2026, 10, 1), f"VINV-{next(builder.vinv)}", po=po,
                                            quantities={other["line"]: (available if other["line"] == row["line"] else 0) for other in books["documents"][po]["lines"]},
                                            prices={row["line"]: cents(D(row["unit_price"]) * (1 + bump))})
        vendors.append(("tolerance", identifier, None))
    elif choice == "reverse-charge":
        french = next(key for key, partner in sorted(books["partners"].items()) if partner["kind"] == "vendor" and partner["country"] == "FR")
        identifier = builder.vendor_invoice(french, dt.date(2026, 10, 2), f"VINV-{next(builder.vinv)}", gross_target=D(rng.randrange(80000, 450000)) / 100)
        vendors.append(("reverse-charge", identifier, None))
    else:
        british = next(key for key, partner in sorted(books["partners"].items()) if partner["kind"] == "vendor" and partner["currency"] == "GBP")
        requester = rng.choice(["Marta Kovacs", "Joris Bakker"])
        amount = D(rng.randrange(470000, 900000)) / 100
        identifier = builder.vendor_invoice(british, dt.date(2026, 10, 2), f"VINV-{next(builder.vinv)}", gross_target=amount, requested_by=requester)
        approver = "Marta Kovacs" if requester == "Marta Kovacs" else "Eva Jansen"
        vendors.append(("approval", identifier, approver))
    for trap, identifier, approver in vendors:
        if identifier is None:
            raise Unsuitable("vendor invoice")
        add("vendor", f"Please process vendor invoice {identifier} from the inbox." + (f" It was approved by {approver}." if approver else ""),
            inbox=identifier, approver=approver, trap=trap)
    # A credit note on a partly paid invoice, for more than is still open.
    state = items(books)
    partly = [key for key, record in sorted(books["documents"].items()) if record.get("type") == "invoice" and key in state
              and 0 < state[key]["open"] < D(record["gross"]) and not record.get("contract") and any(line["qty"] >= 2 for line in record["lines"])]
    if not partly:
        raise Unsuitable("credit note")
    # Prefer a credit larger than what is still open, so that part of it becomes customer credit.
    def biggest(key):
        lines = books["documents"][key]["lines"]
        index = max(range(len(lines)), key=lambda position: D(lines[position]["unit_price"]) * lines[position]["qty"] * (1 + D(lines[position]["vat_rate"])))
        return index, D(lines[index]["unit_price"]) * lines[index]["qty"] * (1 + D(lines[index]["vat_rate"]))
    larger = [key for key in partly if biggest(key)[1] > state[key]["open"]]
    invoice = rng.choice(larger or partly)
    record = books["documents"][invoice]
    index = biggest(invoice)[0]
    units = record["lines"][index]["qty"] if larger else max(1, record["lines"][index]["qty"] - rng.randrange(0, 2))
    add("credit-note", f"The customer returned {units} unit{'s' if units > 1 else ''} of '{record['lines'][index]['description']}' invoiced on {invoice}. "
        f"Please issue credit note CN-{rng.randrange(8001, 8999)} for them.", invoice=invoice, units={str(index): units}, number=None, trap="credit-note")
    requests[-1]["number"] = re.search(r"CN-\d+", requests[-1]["text"]).group(0)
    add("deferred", "Please run September's deferred revenue recognition.", trap="deferred")
    add("revaluation", "Please run the September revaluation.", trap="revaluation")
    # The payment plan comes first, on the books as they stand: one payable is disputed and must not be paid (the
    # largest, so that leaving it out matters), and the cash and the daily limit are drawn so that the named plans are
    # clearly apart.
    found = ledger.payables(books)
    if len(found) < 20:
        raise Unsuitable("payables")
    largest = max(found, key=lambda key: D(found[key]["gross"]) * rate(books, found[key]["currency"], TODAY.isoformat()))
    record_of(books, largest)["disputed"] = True
    books["payment_plan"] = plan_settings(rng, books)
    requests.insert(0, {"id": "R0", "kind": "payment-plan", "trap": "payment-plan",
                        "text": f"Please plan the vendor payments for the next two weeks, {PLAN_DAYS[0]} to {PLAN_DAYS[-1]}, as the manual says."})
    for index, request in enumerate(requests):
        request["id"] = f"R{index + 1}"
    return requests


def plan_settings(rng, books):
    """Opening cash, inflows and a daily limit under which planning well pays: the cash of each currency covers part of
    its worthwhile payments, arriving over the two weeks, and the naive, greedy and best plans are clearly apart. Raises
    Unsuitable when no such setting is found for these payables."""
    books["payment_plan"] = {"days": list(PLAN_DAYS), "later": PLAN_LATER, "opening": {}, "inflows": {}, "max_per_day": 3, "schedule": {}}
    needed = {}
    for key, (currency, _, options) in plan_table(books).items():
        best_day = max(options, key=lambda when: options[when][1])
        if options[best_day][1] > 0:
            needed[currency] = needed.get(currency, D(0)) + options[best_day][0]
    for _ in range(60):
        opening, inflows = {}, {}
        for currency in ("CHF", "EUR", "GBP", "USD"):
            total = needed.get(currency, D(0))
            opening[currency] = text(cents(total * D(rng.randrange(10, 26)) / 100))
            inflows[currency] = {when: text(cents(total * D(rng.randrange(8, 22)) / 100)) for when in sorted(rng.sample(PLAN_DAYS[1:], rng.randrange(2, 4)))}
        settings = {"days": list(PLAN_DAYS), "later": PLAN_LATER, "opening": opening, "inflows": inflows, "max_per_day": rng.choice([2, 3, 3]), "schedule": {}}
        books["payment_plan"] = settings
        problem = PlanProblem(books)
        naive_value = PlanState(problem, naive_plan(problem)).value
        greedy_slots = greedy_plan(problem)
        greedy_value = PlanState(problem, greedy_slots).value
        if greedy_value <= 0 or naive_value > greedy_value * 0.85:
            continue
        # The greedy plan polished by single moves and swaps should still fall short of the best plan known, so that
        # the top of the scale takes a search over the whole plan.
        polished = PlanState(problem, improve(problem, greedy_slots)).value
        best_value = search_best(problem, steps=60000, restarts=3, rounds=0)[0]
        if greedy_value <= best_value * 0.9 and polished <= best_value * 0.97:
            return settings
    raise Unsuitable("payment plan settings")


MISTAKES = {
    "pay-by-due-date": "plans the payments by due date, as early as the cash allows, instead of by what paying them is worth",
    "oldest-first": "ignores the named invoices and the exact match, and pays the oldest first",
    "no-discount": "grants no early-payment discount",
    "no-writeoff": "leaves short payments within the limit open",
    "spread-to-fx": "puts the bank's conversion cost into the exchange result",
    "no-closed-period": "posts vendor invoices at their date in the closed September",
    "revalue-now": "revalues the open items as they are now, not at the end of September",
}


def mistake_effects(books, requests):
    """For each modelled misreading, the requests whose handling it changes, on the true state before each request."""
    results, _ = run(books, requests)
    effects = {}
    for mistake in MISTAKES:
        effects[mistake] = []
        for request, (state, result) in zip(requests, results):
            wrong = handle(state, request, (mistake,))
            if footprint(wrong["entries"]) != footprint(result["entries"]) or wrong["outcome"] != result["outcome"] \
                    or wrong.get("plan") != result.get("plan"):
                effects[mistake].append(request["id"])
    return effects


def build(seed):
    """(books, requests, effects) for one close day; draws again until every planted point holds and every modelled
    misreading changes some request."""
    rng = random.Random(seed)
    for _ in range(200):
        builder = Builder(rng)
        builder.partners()
        builder.history()
        try:
            requests = queue(builder)
        except Unsuitable:
            continue
        books = builder.books
        books["bank"].sort(key=lambda line: (line["date"], line["id"]))
        results, _ = run(books, requests)
        outcomes = {request["trap"]: result["outcome"] for request, (_, result) in zip(requests, results)}
        expected = {"duplicate": "rejected", "fifo-closed-period": "posted", "tolerance": "blocked", "reverse-charge": "posted", "approval": "held"}
        if any(outcomes.get(trap, outcome) != outcome for trap, outcome in expected.items()):
            continue
        effects = mistake_effects(books, requests)
        if sum(1 for touched in effects.values() if touched) >= 5:
            return books, requests, effects
    raise RuntimeError(f"no close day for {seed}")


def prompt(item_id, requests):
    lines = [f"## Close queue {item_id.upper()}", "",
             f"Today's queue holds {len(requests)} requests. Handle them in this order, under MANUAL.md, and end with the one JSON reply it describes.", ""]
    for request in requests:
        lines.append(f"- {request['id']} ({COLLEAGUES[request['kind']]}): {request['text']}")
    return "\n".join(lines) + "\n"
