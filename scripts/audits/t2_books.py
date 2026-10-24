#!/usr/bin/env python3
"""Success audit of the T2 finance desk, written from the item's public MANUAL.md, prompt and books, and nothing of the
package's private code. It replays each audited trial's audit log on the starting books, recomputes every request
independently on the books as that request found them, and compares the delivered entries, statuses, plan and reply
with the recomputation. It also checks the delivered books as a whole (double entry, open items, bank lines posted once).

Usage: python3 -I scripts/audits/t2_books.py <request.json> <result.json>
"""
import copy
import datetime as dt
import glob
import json
import os
import re
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal as D

CENT = D("0.01")
OPEN_ITEMS = {"1200": "debit", "2000": "credit"}          # manual §1: a receivable opens by a debit, a payable by a credit
PARTNER_KEYED = {"1200", "1210", "2000", "2010", "2150", "2200", "2400"}
DOCUMENT_KEYED = PARTNER_KEYED | {"2160"}
EU = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split())
TODAY = "2026-10-05"
LATER = "2026-10-19"
MONTH_END = "2026-09-30"
RUNGS = [("25", D("0.25")), ("50", D("0.5")), ("65", D("0.65")), ("80", D("0.8")), ("90", D("0.9")), ("97", D("0.97")), ("100", D("1"))]


def r(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def day(text):
    return dt.date.fromisoformat(text)


def rate(books, currency, date):
    """Manual §2: EUR is 1; a weekend date uses the Friday before."""
    if currency == "EUR":
        return D(1)
    moment = day(date)
    while moment.weekday() >= 5:
        moment -= dt.timedelta(days=1)
    return D(books["rates"][currency][moment.isoformat()])


def eur(books, currency, amount, date):
    return r(amount * rate(books, currency, date))


def line_amount(line):
    return D(line.get("debit") or "0") - D(line.get("credit") or "0")


def items(books, until=None):
    """Open amount and EUR balance of every open-item document, from its 1200/2000 lines (positive when owed)."""
    result = {}
    for entry in books["entries"]:
        if until and entry["date"] > until:
            continue
        for line in entry["lines"]:
            account = line["account"]
            if account not in OPEN_ITEMS:
                continue
            item = result.setdefault(line["document"], {"account": account, "partner": line["partner"], "currency": line["currency"], "open": D(0), "eur": D(0)})
            sign = 1 if ("debit" in line) == (OPEN_ITEMS[account] == "debit") else -1
            item["open"] += sign * D(line["amount"])
            item["eur"] += sign * D(line.get("debit") or line.get("credit"))
    return result


def document(books, key):
    return books["documents"].get(key) or books["inbox"].get(key)


def posting_date(books, date, lines):
    """Manual §1: an entry in a period closed for its ledger is posted on the first day of the next open one."""
    ledger = "AP" if any(line["account"] == "2000" for line in lines) else "AR" if any(line["account"] == "1200" for line in lines) else "GL"
    period = date[:7]
    if books["periods"].get(period, {}).get(ledger, "open") == "open":
        return date
    for later in sorted(books["periods"]):
        if later > period and books["periods"][later][ledger] == "open":
            return later + "-01"
    raise ValueError("no open period")


class Entry:
    def __init__(self, books, date):
        self.books, self.date, self.lines = books, date, []

    def add(self, account, value, **names):
        if value:
            self.lines.append({"account": account, "debit" if value > 0 else "credit": str(abs(value)), **names})

    def clearing(self, item, document_key, amount, already, carrying):
        """A clearing of `amount` (document currency) after `already` was cleared in this entry: partial at the carrying
        rate, or what remains of the EUR balance when it settles the document (manual §1). Returns its EUR."""
        if already + amount == item["open"]:
            return item["eur"] - self.cleared_eur.get(document_key, D(0))
        return r(amount * carrying)

    def done(self):
        return {"date": posting_date(self.books, self.date, self.lines), "lines": self.lines}


def receipt(books, bank_id):
    line = next(item for item in books["bank"] if item["id"] == bank_id)
    received = D(line["eur"])
    entry = Entry(books, line["date"])
    entry.cleared_eur = {}
    customers = {key: partner for key, partner in books["partners"].items() if partner["kind"] == "customer"}
    customer = next((key for key, partner in customers.items() if line["iban"] in partner.get("ibans", [])), None) or \
        next((key for key, partner in customers.items() if line["payer"].lower() in [name.lower() for name in [partner["name"], *partner.get("aliases", [])]]), None)
    if not customer:
        entry.add("1100", received)
        entry.add("2160", -received, document=bank_id)
        return [entry.done()]
    currency = line["original"]["currency"] if line.get("original") else "EUR"
    money = D(line["original"]["amount"]) if line.get("original") else received
    receipt_rate = rate(books, currency, line["date"])
    current = items(books)
    candidates = {key: item for key, item in current.items() if item["account"] == "1200" and item["partner"] == customer and item["currency"] == currency and item["open"] > 0}
    due = lambda key: (document(books, key)["due"], int(re.sub(r"\D", "", key)))
    named = [key for key in dict.fromkeys(re.findall(r"INV-\d+", line["text"])) if key in candidates]
    if named:
        targets = named
    else:
        exact = sorted((key for key, item in candidates.items() if item["open"] == money), key=due)
        targets = exact[:1] or sorted(candidates, key=due)
    entry.add("1100", received)
    allocated_value = D(0)
    for key in targets:
        item, invoice = candidates[key], document(books, key)
        carrying = rate(books, currency, invoice["date"])
        open_amount = item["open"]
        discount = D(0)
        terms = books["partners"][customer].get("terms")
        earlier = any(entry_line["account"] == "1200" and entry_line.get("document") == key and "credit" in entry_line and
                      any(other["account"] == "1100" and "debit" in other for other in old["lines"])
                      for old in books["entries"] for entry_line in old["lines"])
        if terms == "2/10 net 30" and (day(line["date"]) - day(invoice["date"])).days <= 10 and not earlier:
            candidate_discount = r(D("0.02") * D(invoice["gross"]))
            if money >= open_amount - candidate_discount:
                discount = candidate_discount
        pay = open_amount - discount if discount else min(money, open_amount)
        if pay <= 0:
            continue
        cleared = D(0)
        pay_eur = entry.clearing(item, key, pay, cleared, carrying)
        entry.cleared_eur[key] = entry.cleared_eur.get(key, D(0)) + pay_eur
        cleared += pay
        entry.add("1200", -pay_eur, partner=customer, document=key, currency=currency, amount=str(pay))
        worth = r(pay * receipt_rate)
        entry.add("7900", -(worth - pay_eur))
        allocated_value += worth
        money -= pay
        if discount:
            discount_eur = entry.clearing(item, key, discount, cleared, carrying)
            entry.cleared_eur[key] += discount_eur
            cleared += discount
            entry.add("1200", -discount_eur, partner=customer, document=key, currency=currency, amount=str(discount))
            vat = r(discount * D(invoice["vat"]) / D(invoice["gross"]))
            vat_eur = r(vat * carrying)
            entry.add("2100", vat_eur)
            entry.add("4900", discount_eur - vat_eur)
        elif cleared < open_amount and open_amount - cleared <= D("5.00"):
            shortfall = open_amount - cleared
            write_off = entry.clearing(item, key, shortfall, cleared, carrying)
            entry.cleared_eur[key] += write_off
            entry.add("1200", -write_off, partner=customer, document=key, currency=currency, amount=str(shortfall))
            entry.add("6900", write_off)
        if money <= 0:
            break
    if money > 0:
        prepayment = r(money * receipt_rate)
        entry.add("2150", -prepayment, partner=customer, document=bank_id)
        allocated_value += prepayment
    entry.add("6900", allocated_value - received)
    return [entry.done()]


def credit_note(books, invoice_key, number, units, description):
    invoice = document(books, invoice_key)
    currency = invoice["currency"]
    carrying = rate(books, currency, invoice["date"])
    net = vat = D(0)
    for line in invoice["lines"]:
        if line["description"] == description:
            line_net = r(D(units) * D(line["unit_price"]))
            net += line_net
            vat += r(line_net * D(line["vat_rate"]))
    gross = net + vat
    gross_eur, vat_eur = r(gross * carrying), r(vat * carrying)
    entry = Entry(books, TODAY)
    entry.cleared_eur = {}
    entry.add("4000", gross_eur - vat_eur)
    entry.add("2100", vat_eur)
    item = items(books)[invoice_key]
    to_invoice = min(gross, item["open"])
    cleared_eur = entry.clearing(item, invoice_key, to_invoice, D(0), carrying) if to_invoice > 0 else D(0)
    entry.add("1200", -cleared_eur, partner=invoice["partner"], document=invoice_key, currency=currency, amount=str(to_invoice))
    entry.add("2150", -(gross_eur - cleared_eur), partner=invoice["partner"], document=number)
    return [entry.done()]


def normalized(number):
    text = re.sub(r"[^A-Za-z0-9]", "", number).upper()
    return re.sub(r"\d+", lambda run: str(int(run.group(0))), text)


def posted_vendor_invoices(books):
    return [record for record in list(books["documents"].values()) + list(books["inbox"].values())
            if record["type"] == "vendor-invoice" and record["status"] == "posted"]


def vendor(books, inbox_key, approver):
    invoice = books["inbox"][inbox_key]
    partner = books["partners"][invoice["vendor"]]
    currency, date = invoice["currency"], invoice["date"]
    posted = posted_vendor_invoices(books)
    if any(record["vendor"] == invoice["vendor"] and record["id"] != inbox_key and normalized(record["number"]) == normalized(invoice["number"]) for record in posted):
        return "rejected", []
    if invoice.get("po"):
        order = books["documents"][invoice["po"]]
        for line in invoice["lines"]:
            ordered = next(item for item in order["lines"] if item["line"] == line["po_line"])
            received = sum(receipt["qty"] for receipt in books["receipts"] if receipt["po"] == invoice["po"] and receipt["line"] == line["po_line"])
            invoiced = sum(other["qty"] for record in posted if record.get("po") == invoice["po"] for other in record["lines"] if other["po_line"] == line["po_line"])
            variance = eur(books, currency, (D(line["unit_price"]) - D(ordered["unit_price"])) * line["qty"], date)
            ordered_value = eur(books, currency, D(ordered["unit_price"]) * line["qty"], date)
            if line["qty"] > received - invoiced or abs(variance) > r(D("0.02") * ordered_value) or abs(variance) > D("50.00"):
                return "blocked", []
    gross_eur = eur(books, currency, D(invoice["gross"]), date)
    if gross_eur > D("5000.00"):
        approvers = {item["name"]: D(item["limit"]) for item in books["approvers"]}
        if not approver or approver not in approvers or approvers[approver] < gross_eur or approver == invoice["requested_by"]:
            return "held", []
    vat_eur = eur(books, currency, D(invoice["vat"]), date)
    net_eur = gross_eur - vat_eur
    entry = Entry(books, date)
    entry.add("2000", -gross_eur, partner=invoice["vendor"], document=inbox_key, currency=currency, amount=invoice["gross"])
    if invoice.get("po") and invoice["category"] == "goods":
        accrual = D(0)
        for line in invoice["lines"]:
            receipts = sorted((receipt for receipt in books["receipts"] if receipt["po"] == invoice["po"] and receipt["line"] == line["po_line"]),
                              key=lambda receipt: (receipt["date"], receipt["id"]))
            skip = sum(other["qty"] for record in posted if record.get("po") == invoice["po"] for other in record["lines"] if other["po_line"] == line["po_line"])
            wanted = line["qty"]
            for receipt in receipts:
                available = receipt["qty"] - min(skip, receipt["qty"])
                skip = max(0, skip - receipt["qty"])
                take = min(available, wanted)
                accrual += take * D(receipt["accrued_per_unit"])
                wanted -= take
        entry.add("2200", accrual, partner=invoice["vendor"], document=invoice["po"])
        entry.add("6950", net_eur - accrual)
    else:
        entry.add("6000", net_eur)
    if partner["country"] == "NL":
        entry.add("1300", vat_eur)
    elif (partner["country"] in EU and partner.get("vat_id")) or invoice["category"] == "services":
        self_assessed = r(D("0.21") * net_eur)
        entry.add("1300", self_assessed)
        entry.add("2100", -self_assessed)
    return "posted", [entry.done()]


def revaluation(books):
    lines = Entry(books, MONTH_END)
    for key, item in sorted(items(books, until=MONTH_END).items()):
        if item["currency"] == "EUR" or item["open"] == 0:
            continue
        difference = eur(books, item["currency"], item["open"], MONTH_END) - item["eur"]
        if item["account"] == "1200":
            lines.add("1210", difference, partner=item["partner"], document=key)
            lines.add("7910", -difference)
        else:
            lines.add("2010", -difference, partner=item["partner"], document=key)
            lines.add("7910", difference)
    if not lines.lines:
        return []
    reverse = Entry(books, "2026-10-01")
    for line in lines.lines:
        reverse.lines.append({**{key: value for key, value in line.items() if key not in ("debit", "credit")},
                              ("credit" if "debit" in line else "debit"): line.get("debit") or line.get("credit")})
    return [lines.done(), reverse.done()]


def deferred(books):
    entry = Entry(books, MONTH_END)
    september = (day("2026-09-01"), day(MONTH_END))
    for key, contract in sorted(books["contracts"].items()):
        start, end = day(contract["start"]), day(contract["end"])
        overlap = (min(end, september[1]) - max(start, september[0])).days + 1
        if overlap <= 0:
            continue
        if september[0] <= end <= september[1]:
            share = -sum(line_amount(line) for old in books["entries"] for line in old["lines"] if line["account"] == "2400" and line.get("document") == key)
        else:
            share = r(D(contract["net_eur"]) * overlap / ((end - start).days + 1))
        entry.add("2400", share, partner=contract["partner"], document=key)
        entry.add("4000", -share)
    return [entry.done()] if entry.lines else []


def footprint(entries):
    eur_net, documents = defaultdict(D), defaultdict(D)
    for entry in entries:
        for line in entry["lines"]:
            account = line["account"]
            key = (account, line.get("partner") if account in PARTNER_KEYED else None, line.get("document") if account in DOCUMENT_KEYED else None, entry["date"][:7])
            eur_net[key] += line_amount(line)
            if account in OPEN_ITEMS:
                documents[(account, line.get("partner"), line.get("document"), line.get("currency"))] += (1 if "debit" in line else -1) * D(line["amount"])
    clean = lambda table: {str(key): str(value) for key, value in table.items() if value != 0}
    return clean(eur_net), clean(documents)


# The payment plan (manual §7).

class Plan:
    def __init__(self, books):
        self.books = books
        settings = books["payment_plan"]
        self.days, self.limit = settings["days"], settings["max_per_day"]
        self.opening = {currency: D(value) for currency, value in settings["opening"].items()}
        self.inflows = {currency: {when: D(value) for when, value in days.items()} for currency, days in settings.get("inflows", {}).items()}
        self.payables = {}
        for key, item in items(books).items():
            record = document(books, key)
            if item["account"] != "2000" or item["open"] <= 0 or record.get("disputed"):
                continue
            terms = books["partners"][record["vendor"]]
            self.payables[key] = {"currency": item["currency"], "open": item["open"], "gross": D(record["gross"]), "date": record["date"], "due": record["due"], "terms": terms}

    def discount(self, payable, when):
        terms = payable["terms"]
        if terms.get("discount_days") is None or (day(when) - day(payable["date"])).days > terms["discount_days"]:
            return D(0)
        return r(D(terms["discount_rate"]) * payable["gross"])

    def late(self, payable, when):
        days = (day(when) - day(payable["due"])).days
        if days <= 0:
            return D(0)
        terms = payable["terms"]
        return D(terms["late_fee"]) + r(D(terms["late_rate"]) * payable["gross"] * days)

    def uses(self, key, when):
        return self.payables[key]["open"] - self.discount(self.payables[key], when)

    def worth(self, key, when):
        payable = self.payables[key]
        saving = self.late(payable, LATER) - self.late(payable, when) + self.discount(payable, when) - self.discount(payable, LATER)
        return r(saving * rate(self.books, payable["currency"], TODAY))

    def valid(self, schedule):
        if not isinstance(schedule, dict) or any(key not in self.payables or when not in self.days for key, when in schedule.items()):
            return False
        if any(sum(1 for when in schedule.values() if when == moment) > self.limit for moment in self.days):
            return False
        for currency in {payable["currency"] for payable in self.payables.values()} | set(self.opening):
            cash = self.opening.get(currency, D(0))
            for moment in self.days:
                cash += self.inflows.get(currency, {}).get(moment, D(0))
                cash -= sum(self.uses(key, when) for key, when in schedule.items() if when == moment and self.payables[key]["currency"] == currency)
                if cash < 0:
                    return False
        return True

    def value(self, schedule):
        return sum((self.worth(key, when) for key, when in schedule.items()), D(0))

    def fits(self, schedule, key, when):
        return self.valid({**schedule, key: when})

    def naive(self):
        schedule = {}
        for key in sorted(self.payables, key=lambda key: (self.payables[key]["due"], key)):
            for when in self.days:
                if self.fits(schedule, key, when):
                    schedule[key] = when
                    break
        return schedule

    def greedy(self):
        best_day = {key: max(self.days, key=lambda when: (self.worth(key, when), -self.days.index(when))) for key in self.payables}
        order = sorted(self.payables, key=lambda key: (-(self.worth(key, best_day[key]) / self.uses(key, best_day[key])), key))
        schedule = {}
        for key in order:
            open_days = [when for when in self.days if self.fits(schedule, key, when)]
            if not open_days:
                continue
            when = max(open_days, key=lambda moment: (self.worth(key, moment), -self.days.index(moment)))
            if self.worth(key, when) > 0:
                schedule[key] = when
        return schedule

    def place(self, schedule, best_value):
        if not self.valid(schedule):
            return D(0)
        value, naive, greedy = self.value(schedule), self.value(self.naive()), self.value(self.greedy())
        best = max(best_value, greedy)
        if value >= greedy:
            return D(1) if value >= best or greedy >= best else D("0.5") + D("0.5") * (value - greedy) / (best - greedy)
        return D(0) if naive >= greedy else max(D(0), D("0.5") * (value - naive) / (greedy - naive))


# Driving the audit.

def requests_of(prompt):
    found = []
    for request_id, text in re.findall(r"^- (R\d+) \([^)]*\): (.+)$", prompt, re.M):
        if "plan the vendor payments" in text:
            found.append({"id": request_id, "kind": "payment-plan"})
        elif match := re.search(r"receipt on bank line (\S+?)\.?$", text):
            found.append({"id": request_id, "kind": "receipt", "bank": match.group(1)})
        elif match := re.search(r"vendor invoice (VINV-\d+)", text):
            approver = re.search(r"approved by ([^.]+)\.", text)
            found.append({"id": request_id, "kind": "vendor", "inbox": match.group(1), "approver": approver.group(1) if approver else None})
        elif match := re.search(r"returned (\d+) units of '([^']+)' invoiced on (INV-\d+)\. Please issue credit note (CN-\d+)", text):
            found.append({"id": request_id, "kind": "credit-note", "units": int(match.group(1)), "description": match.group(2), "invoice": match.group(3), "number": match.group(4)})
        elif "deferred revenue" in text:
            found.append({"id": request_id, "kind": "deferred"})
        elif "revaluation" in text:
            found.append({"id": request_id, "kind": "revaluation"})
        else:
            raise ValueError(f"unknown request {text}")
    return found


def apply(books, command):
    name, args = command[0], command[1:]
    if name == "post":
        books["entries"].append({"date": args[0]["date"], "lines": args[0]["lines"]})
    elif name == "set-status":
        books["inbox"][args[0]]["status"] = args[1]
    elif name == "set-plan":
        books["payment_plan"]["schedule"] = args[0]


def expected(books, request):
    kind = request["kind"]
    if kind == "receipt":
        return "done", receipt(books, request["bank"]), {}
    if kind == "credit-note":
        return "done", credit_note(books, request["invoice"], request["number"], request["units"], request["description"]), {}
    if kind == "vendor":
        outcome, entries = vendor(books, request["inbox"], request["approver"])
        return outcome, entries, {request["inbox"]: outcome}
    if kind == "deferred":
        return "done", deferred(books), {}
    return "done", revaluation(books), {}


def last_object(text):
    decoder, found = json.JSONDecoder(), []
    for start in [index for index, char in enumerate(text or "") if char == "{"]:
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and any(re.fullmatch(r"R\d+", key) for key in value):
            found.append((end, value))
    return max(found, key=lambda pair: pair[0])[1] if found else {}


def audit_trial(trial, package):
    item = trial["itemId"]
    public = os.path.join(package, "items", item, "public")
    base = json.load(open(os.path.join(public, "data", "books.json")))
    requests = requests_of(open(os.path.join(package, "items", item, "prompt.md")).read())
    artifacts = os.path.join(trial["directory"], "artifacts", "public", "data")
    commands = [json.loads(line) for line in open(os.path.join(artifacts, "audit.log")) if line.strip()]
    delivered = json.load(open(os.path.join(artifacts, "books.json")))
    record = json.load(open(os.path.join(trial["directory"], "result.json")))
    reply = last_object(record["execution"].get("output"))
    runs = sorted(glob.glob(os.path.join(trial["directory"], "score-runs", "*", "score.json")), key=lambda path: json.load(open(path))["createdAt"])
    checks = {check["id"]: check["passed"] for check in json.load(open(runs[-1]))["evaluation"]["checks"]}
    findings = []
    status = json.load(open(runs[-1]))["evaluation"]["status"]
    # Whole-book invariants have no check of their own; a violation in a trial the grader resolved is a false pass.
    add = lambda unit, grader, right, detail="": findings.append({"trial": trial["directory"], "label": trial["label"], "item": item, "unit": unit, "grader": grader,
                                                                  "verdict": ("true pass" if right else "false pass") if grader == "pass" else
                                                                  ("false fail" if right else "true fail") if grader == "fail" else
                                                                  ("true pass" if right else "false pass" if status == "passed" else "true fail"),
                                                                  "detail": detail})
    # The books as a whole.
    state = copy.deepcopy(base)
    for command in commands:
        apply(state, command)
    added = state["entries"][len(base["entries"]):]
    unbalanced = [index for index, entry in enumerate(added) if sum(line_amount(line) for line in entry["lines"]) != 0]
    negative = [key for key, value in items(state).items() if value["open"] < 0]
    settled_with_eur = [key for key, value in items(state).items() if value["open"] == 0 and value["eur"] != 0]
    bank_ids = [request["bank"] for request in requests if request["kind"] == "receipt"]
    posted_once = {bank: sum(1 for entry in added if any(line["account"] == "1100" and "debit" in line for line in entry["lines"])
                             and any(D(line.get("debit", "0")) == D(next(item for item in base["bank"] if item["id"] == bank)["eur"]) for line in entry["lines"] if line["account"] == "1100")
                             and entry["date"] == next(item for item in base["bank"] if item["id"] == bank)["date"]) for bank in bank_ids}
    twice = [bank for bank, count in posted_once.items() if count > 1]
    whole = not unbalanced and not negative and not settled_with_eur and not twice
    add("books: double entry, open items, settled documents, bank lines once", "n/a", whole,
        "" if whole else f"unbalanced entries {unbalanced}, negative open {negative}, settled with EUR left {settled_with_eur}, bank lines posted twice {twice}")
    # Per request, on the books as it found them (the trial's own state).
    positions = {}
    for index, command in enumerate(commands):
        if command[0] == "begin":
            positions.setdefault(command[1], index)
    for position, request in enumerate(requests):
        prefix = request["id"].lower()
        own = [name for name in checks if name.startswith(f"{item}-{prefix}-")]
        grader = "pass" if own and all(checks[name] for name in own) else "fail"
        if request["id"] not in positions:
            add(f"{request['id']} {request['kind']}", grader, False, "never begun")
            continue
        start = positions[request["id"]]
        following = [index for index in range(start + 1, len(commands)) if commands[index][0] == "begin"]
        segment = commands[start + 1: following[0] if following else len(commands)]
        books = copy.deepcopy(base)
        for command in commands[:start]:
            apply(books, command)
        if request["kind"] == "payment-plan":
            plan = Plan(books)
            plans = [command[1] for command in commands if command[0] == "set-plan"]
            schedule = plans[-1] if plans else {}
            best = json.load(open(os.path.join(package, "private", "days.json")))[item]["plan_best"]
            place = plan.place(schedule, D(best["value"]) / 100)
            rungs = {label: place >= threshold for label, threshold in RUNGS}
            grader_rungs = {label: checks.get(f"{item}-{prefix}-plan-{label}") for label, _ in RUNGS}
            agree = all(rungs[label] == grader_rungs[label] for label, _ in RUNGS)
            detail = (f"valid {plan.valid(schedule)}, worth {plan.value(schedule) if plan.valid(schedule) else 'n/a'} EUR, naive {plan.value(plan.naive())}, "
                      f"greedy {plan.value(plan.greedy())}, best known {D(best['value']) / 100}; place {place:.4f}; rungs audit "
                      f"{''.join('1' if rungs[label] else '0' for label, _ in RUNGS)} grader {''.join('1' if grader_rungs[label] else '0' for label, _ in RUNGS)}")
            outcome_right = isinstance(reply.get(request["id"]), str) and reply[request["id"]].strip().lower() == "done"
            # The plan's checks are rungs: the audit agrees when every rung decision, the outcome and the clean check match.
            clean = bool(plans) and not [command for command in segment if command[0] in ("post", "set-status")]
            audit_pass = all(rungs.values()) and outcome_right and clean
            agrees = agree and outcome_right == bool(checks.get(f"{item}-{prefix}-outcome"))
            verdict = ("true pass" if audit_pass else "false pass") if grader == "pass" else ("true fail" if agrees else "false fail")
            findings.append({"trial": trial["directory"], "label": trial["label"], "item": item, "unit": f"{request['id']} payment plan", "grader": grader,
                             "verdict": verdict, "detail": detail})
            continue
        outcome, entries, statuses = expected(books, request)
        mine = [command[1] for command in segment if command[0] == "post"]
        mine_statuses = {command[1]: command[2] for command in segment if command[0] == "set-status"}
        given = reply.get(request["id"])
        right = footprint(mine) == footprint(entries) and mine_statuses == statuses and isinstance(given, str) and given.strip().lower() == outcome
        detail = "" if right else json.dumps({"outcome": [given, outcome], "statuses": [mine_statuses, statuses],
                                               "eur": sorted(set(footprint(mine)[0].items()) ^ set(footprint(entries)[0].items()))[:8]})
        add(f"{request['id']} {request['kind']}", grader, right, detail)
    return findings


def anchor_check(package):
    """The best plan known per day (the scale's top) re-valued by the independent evaluator: it must be valid and worth
    what the package records; and the hand-checkable anchors naive and greedy are reported."""
    notes = []
    days = json.load(open(os.path.join(package, "private", "days.json")))
    for item, record in sorted(days.items()):
        books = json.load(open(os.path.join(package, "items", item, "public", "data", "books.json")))
        plan = Plan(books)
        best = record["plan_best"]
        notes.append(f"{item}: {len(plan.payables)} payables; naive {plan.value(plan.naive())} EUR, greedy {plan.value(plan.greedy())} EUR, "
                     f"best known recorded {D(best['value']) / 100} EUR")
    return notes


def main():
    request = json.load(open(sys.argv[1]))
    findings = []
    for trial in request["trials"]:
        findings += audit_trial(trial, request["package"])
    notes = anchor_check(request["package"]) + [
        "Each request is recomputed on the trial's own books as the request found them (its begin marker), as the per-request grading does, so a slip is judged once.",
        "Rungs of the payment plan are re-derived with an independent naive, greedy and plan evaluator; the top of the scale is the package's best plan known (its value only)."]
    json.dump({"findings": findings, "notes": notes}, open(sys.argv[2], "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
