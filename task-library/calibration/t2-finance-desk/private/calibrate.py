"""Self-calibration of the T2 finance desk: hand-worked examples of each rule on small books, then, on every close day,
the oracle through ledger.py itself, an untouched desk, a reply alone, missing begin markers, single slips followed by
correct handling (attribution), and each modelled misreading. No model is involved."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal as D

import finance
import grader
import ledger

HERE = os.path.dirname(os.path.abspath(__file__))


def mini_books():
    """Small books for hand-worked examples: USD rates chosen by hand, three customers, two vendors."""
    rates = {"USD": {"2026-09-01": "0.900000", "2026-09-02": "0.912345", "2026-09-15": "0.920000", "2026-09-16": "0.920000",
                     "2026-09-29": "0.925000", "2026-09-30": "0.930000", "2026-10-01": "0.931000", "2026-10-02": "0.931000"},
             "GBP": {"2026-09-01": "1.170000"}, "CHF": {"2026-09-01": "1.060000"}}
    partners = {"C-1": {"kind": "customer", "name": "Alpha B.V.", "aliases": [], "country": "NL", "currency": "EUR", "terms": "2/10 net 30", "ibans": ["NL01"]},
                "C-2": {"kind": "customer", "name": "Bravo Inc.", "aliases": [], "country": "US", "currency": "USD", "terms": "net 30", "ibans": ["US02"]},
                "C-3": {"kind": "customer", "name": "Charlie B.V.", "aliases": ["CHARLIE"], "country": "NL", "currency": "EUR", "terms": "net 30", "ibans": ["NL03"]},
                "V-1": {"kind": "vendor", "name": "Delta SAS", "country": "FR", "currency": "EUR", "supply": "services", "vat_id": "FR1"},
                "V-2": {"kind": "vendor", "name": "Echo B.V.", "country": "NL", "currency": "EUR", "supply": "services", "vat_id": "NL2"}}
    return {"accounts": finance.ACCOUNTS, "rates": rates, "partners": partners, "documents": {}, "receipts": [], "contracts": {}, "inbox": {},
            "approvers": finance.APPROVERS, "bank": [], "entries": [],
            "periods": {"2026-09": {"AP": "closed", "AR": "open", "GL": "open"}, "2026-10": {"AP": "open", "AR": "open", "GL": "open"}}}


def add_invoice(books, number, partner, date, due, currency, gross, vat="0.00"):
    books["documents"][number] = {"type": "invoice", "id": number, "partner": partner, "date": date, "due": due, "currency": currency,
                                  "lines": [{"description": "Freight", "qty": 1, "unit_price": str(D(gross) - D(vat)), "vat_rate": "0.21" if vat != "0.00" else "0.00"}],
                                  "net": str(D(gross) - D(vat)), "vat": vat, "gross": gross}
    entry, _ = finance.opening(books, books["documents"][number])
    ledger.apply(books, "post", [entry])


def bank(books, identifier, date, eur, payer, iban, remittance, original=None):
    books["bank"].append({"id": identifier, "date": date, "eur": eur, "payer": payer, "iban": iban, "text": remittance, "original": original, "posted": False})


def lines_of(entries):
    return sorted((entry["date"], line["account"], line.get("debit", "-" + line.get("credit", "")), line.get("document"), line.get("amount"))
                  for entry in entries for line in entry["lines"])


def examples():
    rows = []
    # 1. A discount with its VAT part: 2% of 1,210.00 is 24.20, of which 24.20 x 210 / 1,210 = 4.20 is VAT.
    books = mini_books()
    add_invoice(books, "INV-1", "C-1", "2026-09-20", "2026-10-20", "EUR", "1210.00", "210.00")
    bank(books, "B-1", "2026-09-29", "1185.80", "Alpha B.V.", "NL01", "INV-1 less discount")
    rows.append(("discount-and-its-vat", lines_of(finance.receipt(books, "B-1")) == sorted([
        ("2026-09-29", "1100", "1185.80", None, None), ("2026-09-29", "1200", "-1185.80", "INV-1", "1185.80"),
        ("2026-09-29", "1200", "-24.20", "INV-1", "24.20"), ("2026-09-29", "2100", "4.20", None, None), ("2026-09-29", "4900", "20.00", None, None)])))
    # 2. A foreign receipt: 1,000.00 USD carried at 900.00 EUR is worth 920.00 at 0.92; the bank credits 918.00.
    books = mini_books()
    add_invoice(books, "INV-2", "C-2", "2026-09-01", "2026-10-01", "USD", "1000.00")
    bank(books, "B-2", "2026-09-15", "918.00", "Bravo Inc.", "US02", "INV-2", {"currency": "USD", "amount": "1000.00"})
    rows.append(("exchange-result-and-conversion-cost", lines_of(finance.receipt(books, "B-2")) == sorted([
        ("2026-09-15", "1100", "918.00", None, None), ("2026-09-15", "1200", "-900.00", "INV-2", "1000.00"),
        ("2026-09-15", "7900", "-20.00", None, None), ("2026-09-15", "6900", "2.00", None, None)])))
    # 3. Settlement rounding: 100.00 USD at 0.912345 is 91.23 EUR; 50.00 clears 45.62 (45.61725), the second 50.00 the
    # 45.61 left.
    books = mini_books()
    add_invoice(books, "INV-3", "C-2", "2026-09-02", "2026-10-02", "USD", "100.00")
    bank(books, "B-3", "2026-09-15", "46.00", "Bravo Inc.", "US02", "INV-3", {"currency": "USD", "amount": "50.00"})
    bank(books, "B-4", "2026-09-16", "46.00", "Bravo Inc.", "US02", "INV-3", {"currency": "USD", "amount": "50.00"})
    first = finance.receipt(books, "B-3")
    ledger.apply(books, "post", [first[0]])
    second = finance.receipt(books, "B-4")
    rows.append(("partial-then-settling-clearing", lines_of(first) == sorted([("2026-09-15", "1100", "46.00", None, None), ("2026-09-15", "1200", "-45.62", "INV-3", "50.00"),
                                                                           ("2026-09-15", "7900", "-0.38", None, None)])
                 and lines_of(second) == sorted([("2026-09-16", "1100", "46.00", None, None), ("2026-09-16", "1200", "-45.61", "INV-3", "50.00"),
                                                 ("2026-09-16", "7900", "-0.39", None, None)])))
    # 4. Oldest first, then a write-off of the 3.00 left: 297.00 against 100.00 and 200.00.
    books = mini_books()
    add_invoice(books, "INV-4", "C-3", "2026-08-11", "2026-09-10", "EUR", "100.00")
    add_invoice(books, "INV-5", "C-3", "2026-08-21", "2026-09-20", "EUR", "200.00")
    bank(books, "B-5", "2026-09-29", "297.00", "Charlie B.V.", "NL03", "Payment")
    rows.append(("oldest-first-and-write-off", lines_of(finance.receipt(books, "B-5")) == sorted([
        ("2026-09-29", "1100", "297.00", None, None), ("2026-09-29", "1200", "-100.00", "INV-4", "100.00"), ("2026-09-29", "1200", "-197.00", "INV-5", "197.00"),
        ("2026-09-29", "1200", "-3.00", "INV-5", "3.00"), ("2026-09-29", "6900", "3.00", None, None)])))
    # 5. An exact match beats the oldest invoice, and an alias with an unknown account identifies the customer.
    books = mini_books()
    add_invoice(books, "INV-6", "C-3", "2026-08-06", "2026-09-05", "EUR", "150.00")
    add_invoice(books, "INV-7", "C-3", "2026-08-26", "2026-09-25", "EUR", "80.00")
    bank(books, "B-6", "2026-09-29", "80.00", "charlie", "XX99", "Ref 1")
    rows.append(("exact-match-by-alias", lines_of(finance.receipt(books, "B-6")) == sorted([
        ("2026-09-29", "1100", "80.00", None, None), ("2026-09-29", "1200", "-80.00", "INV-7", "80.00")])))
    # 6-7. Reverse-charged services: 21% of 1,000.00 self-assessed; dated in the closed September, posted on 1 October.
    for name, date, posted_on in (("reverse-charge", "2026-10-02", "2026-10-02"), ("closed-ap-period", "2026-09-29", "2026-10-01")):
        books = mini_books()
        books["inbox"]["VINV-1"] = {"type": "vendor-invoice", "id": "VINV-1", "vendor": "V-1", "number": "F-1", "date": date, "currency": "EUR", "category": "services",
                                    "po": None, "requested_by": "Joris Bakker", "status": "new", "net": "1000.00", "vat": "0.00", "gross": "1000.00",
                                    "lines": [{"po_line": None, "description": "Audit", "qty": 1, "unit_price": "1000.00", "vat_rate": "0.00"}]}
        outcome, entries = finance.vendor_outcome(books, "VINV-1", None)
        rows.append((name, outcome == "posted" and lines_of(entries) == sorted([
            (posted_on, "2000", "-1000.00", "VINV-1", "1000.00"), (posted_on, "6000", "1000.00", None, None),
            (posted_on, "1300", "210.00", None, None), (posted_on, "2100", "-210.00", None, None)])))
    # 8. Invoice numbers compare by letters and digits, uppercased, without leading zeros.
    rows.append(("duplicate-numbers", finance.normalized_number("2026/0045") == finance.normalized_number("2026-45") and
                 finance.normalized_number("inv 0045") == finance.normalized_number("INV-45") and
                 finance.normalized_number("2026-450") != finance.normalized_number("2026-45")))
    # 9. Revaluation: 500.00 USD carried at 450.00 is 465.00 at the month-end 0.93, reversed on 1 October; a receipt dated
    # in October does not count.
    books = mini_books()
    add_invoice(books, "INV-8", "C-2", "2026-09-01", "2026-10-01", "USD", "500.00")
    bank(books, "B-7", "2026-10-01", "465.50", "Bravo Inc.", "US02", "INV-8", {"currency": "USD", "amount": "500.00"})
    ledger.apply(books, "post", [finance.receipt(books, "B-7")[0]])
    rows.append(("revaluation-at-month-end", lines_of(finance.revaluation(books)) == sorted([
        ("2026-09-30", "1210", "15.00", "INV-8", None), ("2026-09-30", "7910", "-15.00", None, None),
        ("2026-10-01", "1210", "-15.00", "INV-8", None), ("2026-10-01", "7910", "15.00", None, None)])))
    # 10. Day count: 16 September to 15 October is 30 days, 15 of them in September: half of 300.00.
    books = mini_books()
    books["contracts"]["CTR-1"] = {"id": "CTR-1", "partner": "C-1", "invoice": "INV-9", "start": "2026-09-16", "end": "2026-10-15", "net_eur": "300.00"}
    ledger.apply(books, "post", [{"date": "2026-09-16", "memo": "x", "lines": [{"account": "1100", "debit": "300.00"},
                                                                             {"account": "2400", "credit": "300.00", "partner": "C-1", "document": "CTR-1"}]}])
    rows.append(("deferred-day-count", lines_of(finance.deferred(books)) == sorted([("2026-09-30", "2400", "150.00", "CTR-1", None), ("2026-09-30", "4000", "-150.00", None, None)])))
    # 11. The payment plan, on three days with one payment a day, worked out by hand. V-1 grants 2% within 10 days and
    # charges nothing late; V-2 grants nothing and charges 40.00 once late plus 0.1% a day. Payables:
    #   A (V-1) 1,000.00 of 26 September: 20.00 discount on 5 and 6 October (window to the 6th), using 980.00;
    #   B (V-2)   800.00 due 25 September: 40.00 + 10.40 on the 8th against 48.00 / 48.80 / 49.60 on the 5th / 6th / 7th,
    #             so worth 2.40 / 1.60 / 0.80;
    #   C (V-2)   500.00 due 7 October: 40.50 on the 8th (fee and one day), nothing up to the 7th, so worth 40.50;
    #   E (V-1)   900.00 due 19 September: no charge grows, so worth nothing;
    #   F (V-2)   disputed.
    # The cash is 1,000.00 on the 5th and 1,000.00 more on the 7th.
    books = mini_books()
    books["partners"]["V-1"].update(terms="2/10 net 30", discount_days=10, discount_rate="0.02", late_rate="0", late_fee="0.00")
    books["partners"]["V-2"].update(terms="net 30", discount_days=None, discount_rate=None, late_rate="0.001", late_fee="40.00")
    books["payment_plan"] = {"days": ["2026-10-05", "2026-10-06", "2026-10-07"], "later": "2026-10-08", "opening": {"EUR": "1000.00"},
                             "inflows": {"EUR": {"2026-10-07": "1000.00"}}, "max_per_day": 1, "schedule": {}}
    payables = [("VINV-A", "V-1", "2026-09-26", "2026-10-26", "1000.00"), ("VINV-B", "V-2", "2026-08-26", "2026-09-25", "800.00"),
                ("VINV-C", "V-2", "2026-09-07", "2026-10-07", "500.00"), ("VINV-E", "V-1", "2026-08-20", "2026-09-19", "900.00"),
                ("VINV-F", "V-2", "2026-08-10", "2026-09-09", "300.00")]
    for identifier, vendor, issued, due, gross in payables:
        books["documents"][identifier] = {"type": "vendor-invoice", "id": identifier, "vendor": vendor, "number": identifier, "date": issued,
                                          "due": due, "currency": "EUR", "category": "services", "po": None, "requested_by": "Marta Kovacs",
                                          "status": "posted", "net": gross, "vat": "0.00", "gross": gross,
                                          "lines": [{"po_line": None, "description": "Freight", "qty": 1, "unit_price": gross, "vat_rate": "0.00"}]}
        ledger.apply(books, "post", [{"date": issued, "memo": f"Vendor invoice {identifier}", "lines": [
            {"account": "2000", "credit": gross, "partner": vendor, "document": identifier, "currency": "EUR", "amount": gross},
            {"account": "6000", "debit": gross}]}])
    books["documents"]["VINV-F"]["disputed"] = True
    table = finance.plan_table(books)
    worth = {key: [str(options[when][1]) for when in sorted(options)] for key, (_, _, options) in table.items()}
    rows.append(("plan-worth", worth == {"VINV-A": ["20.00", "20.00", "0.00"], "VINV-B": ["2.40", "1.60", "0.80"],
                                         "VINV-C": ["40.50", "40.50", "40.50"], "VINV-E": ["0.00", "0.00", "0.00"]}))
    rows.append(("plan-cash-used", [str(options[when][0]) for when, options in [(when, table["VINV-A"][2]) for when in ("2026-10-05", "2026-10-07")]]
                 == ["980.00", "1000.00"]))
    problem = finance.PlanProblem(books)
    # By due date: E on the 5th (100.00 left), B on the 7th once the inflow is in, and no room for C: worth 0.80.
    rows.append(("plan-naive", problem.schedule(finance.naive_plan(problem)) == {"VINV-E": "2026-10-05", "VINV-B": "2026-10-07"}))
    # By worth per unit of cash: C (8.1%) on the earliest of its equal days, the 5th; then A fits only on the 7th,
    # where it is worth nothing; B on the 7th: worth 41.30.
    rows.append(("plan-greedy", problem.schedule(finance.greedy_plan(problem)) == {"VINV-C": "2026-10-05", "VINV-B": "2026-10-07"}))
    # Best: A inside its window, C on its due date once the inflow is in: worth 60.50.
    best_value, best_slots = finance.best_plan(problem)
    best_schedule = problem.schedule(best_slots)
    rows.append(("plan-best", best_value == 6050 and best_schedule.get("VINV-C") == "2026-10-07" and best_schedule.get("VINV-A") in ("2026-10-05", "2026-10-06")))
    rows.append(("plan-scale", finance.plan_place(books, {"VINV-E": "2026-10-05", "VINV-B": "2026-10-07"}) == 0
                 and finance.plan_place(books, {"VINV-C": "2026-10-05", "VINV-B": "2026-10-07"}) == D("0.5")
                 and finance.plan_place(books, {"VINV-A": "2026-10-06", "VINV-C": "2026-10-07"}) == 1
                 and finance.plan_place(books, {"VINV-A": "2026-10-05"}) == D("0.5") * D(1920) / D(4050)))
    # The tool refuses a disputed payable, a day outside the plan, a second payment on a day and cash below zero.
    refused = []
    for plan in ({"VINV-F": "2026-10-05"}, {"VINV-A": "2026-10-09"}, {"VINV-A": "2026-10-05", "VINV-C": "2026-10-05"},
                 {"VINV-A": "2026-10-05", "VINV-C": "2026-10-06"}):
        try:
            ledger.apply(books, "set-plan", [plan])
            refused.append(False)
        except ledger.Refused:
            refused.append(True)
    ledger.apply(books, "set-plan", [{"VINV-C": "2026-10-07", "VINV-A": "2026-10-06"}])
    view = ledger.look(books, "plan", [])
    rows.append(("plan-tool", all(refused) and view["cash_at_end_of_day"] == {"2026-10-05": {"EUR": "1000.00"}, "2026-10-06": {"EUR": "20.00"},
                                                                            "2026-10-07": {"EUR": "520.00"}}
                 and [payment["uses"] for payment in view["payments"]] == ["980.00", "500.00"]))
    return rows


def workspace(item_id, commands, cli=False):
    directory = tempfile.mkdtemp(prefix="t2-finance-")
    public = os.path.join(directory, "public")
    os.makedirs(os.path.join(public, "data"))
    shutil.copy(os.path.join(HERE, "ledger.py"), public)
    books = copy.deepcopy(grader.DAYS[item_id]["books"])
    with open(os.path.join(public, "data", "books.json"), "w", encoding="utf-8") as handle:
        json.dump(books, handle, indent=1, sort_keys=True)
    open(os.path.join(public, "data", "audit.log"), "w").close()
    if cli:
        for command in commands:
            if command[0] in ("post", "set-plan"):
                path = os.path.join(directory, "entry.json")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(command[1], handle)
                args = [command[0], path]
            else:
                args = command
            run = subprocess.run([sys.executable, "ledger.py", *args], cwd=public, capture_output=True, text=True)
            assert run.returncode == 0, (command, run.stderr)
        return directory
    for command in commands:
        ledger.apply(books, command[0], command[1:])
    with open(os.path.join(public, "data", "books.json"), "w", encoding="utf-8") as handle:
        json.dump(books, handle, indent=1, sort_keys=True)
    with open(os.path.join(public, "data", "audit.log"), "w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(command) + "\n" for command in commands)
    return directory


def own_state_run(books, requests, slip=None, mistakes=()):
    """A desk that handles each request as the oracle would on the books it has itself produced (with `mistakes`), except
    that `slip` (request id, function) replaces one request's result. Returns (commands, reply)."""
    books = copy.deepcopy(books)
    commands, reply = [], {}
    for request in requests:
        result = finance.handle(books, request, mistakes)
        if slip and slip[0] == request["id"]:
            result = slip[1](books, request, result)
        commands += finance.commands_of(request, result)
        finance.apply_result(books, request, result)
        reply[request["id"]] = result["outcome"]
    return commands, reply


def scenarios():
    rows = []
    for item_id, day in grader.DAYS.items():
        books, requests = day["books"], day["requests"]
        names = set(grader.check_names(item_id)) | {"answer-format"}
        commands, reply = own_state_run(books, requests)
        rows.append((item_id, "oracle-through-ledger-py", commands, "cli", json.dumps(reply), names))
        rows.append((item_id, "oracle-after-prose", commands, None, "Done.\n\n```json\n" + json.dumps(reply) + "\n```", names))
        rows.append((item_id, "oracle-recovered-reply", commands, None, "Outcomes: " + json.dumps(reply) + " (end)", names - {"answer-format"}))
        rows.append((item_id, "untouched", [], None, None, {"answer-format"}))
        rows.append((item_id, "reply-only", [], None, json.dumps(reply), {"answer-format"}))
        rows.append((item_id, "oracle-without-begin", [command for command in commands if command[0] != "begin"], None, json.dumps(reply), names))
        # One slip, then correct handling on the desk's own books: only the slipped request loses checks.
        for request in requests:
            prefix = request["id"].lower()
            others = {name for name in names if not name.startswith(prefix + "-")}
            if request["kind"] == "receipt":
                def wrong(state, request_, result):
                    """Everything to a prepayment, as if no invoice were found."""
                    bank_line = next(item for item in state["bank"] if item["id"] == request_["bank"])
                    customer = finance.identify(state, bank_line)
                    lines = [{"account": "1100", "debit": bank_line["eur"]},
                             {"account": "2150", "credit": bank_line["eur"], "partner": customer, "document": request_["bank"]}] if customer else \
                        [{"account": "1100", "debit": bank_line["eur"]}, {"account": "6900", "credit": bank_line["eur"]}]
                    return {"entries": [{"date": bank_line["date"], "memo": "slip", "lines": lines}], "statuses": {}, "outcome": "done"}
                slipped, slipped_reply = own_state_run(books, requests, (request["id"], wrong))
                rows.append((item_id, f"misbooks-{request['id']}-only", slipped, None, json.dumps(slipped_reply),
                             lambda passed, others=others, prefix=prefix: others <= passed and f"{prefix}-amounts" not in passed))
                break
        for request in requests:
            if request["kind"] == "vendor" and request["trap"] == "duplicate":
                prefix = request["id"].lower()
                others = {name for name in names if not name.startswith(prefix + "-")}

                def posted_anyway(state, request_, result):
                    return finance.handle(state, request_) | {"statuses": {request_["inbox"]: "held"}, "outcome": "held"}
                slipped, slipped_reply = own_state_run(books, requests, (request["id"], posted_anyway))
                rows.append((item_id, f"holds-{request['id']}-only", slipped, None, json.dumps(slipped_reply),
                             lambda passed, others=others, prefix=prefix: others <= passed and f"{prefix}-outcome" not in passed))
        # A plan by due date keeps its outcome but loses its rungs; the greedy plan stops at the middle of the scale; a
        # plan recorded after the next request began loses only the plan's clean check.
        for request in requests:
            if request["kind"] == "payment-plan":
                prefix = request["id"].lower()
                others = {name for name in names if not name.startswith(prefix + "-")}

                def by_due_date(state, request_, result):
                    problem = finance.PlanProblem(state)
                    return {**result, "plan": problem.schedule(finance.naive_plan(problem))}
                slipped, slipped_reply = own_state_run(books, requests, (request["id"], by_due_date))
                rows.append((item_id, f"plans-by-due-date-in-{request['id']}-only", slipped, None, json.dumps(slipped_reply),
                             lambda passed, others=others, prefix=prefix: others <= passed and f"{prefix}-plan-25" not in passed
                             and f"{prefix}-outcome" in passed and f"{prefix}-clean" in passed))

                def greedy(state, request_, result):
                    problem = finance.PlanProblem(state)
                    return {**result, "plan": problem.schedule(finance.greedy_plan(problem))}
                slipped, slipped_reply = own_state_run(books, requests, (request["id"], greedy))
                rows.append((item_id, f"greedy-plan-in-{request['id']}", slipped, None, json.dumps(slipped_reply),
                             lambda passed, others=others, prefix=prefix: others <= passed and f"{prefix}-plan-50" in passed
                             and f"{prefix}-plan-65" not in passed))
                late = [command for command in commands if command[0] != "set-plan"]
                position = next(index for index, command in enumerate(late) if command[0] == "begin" and command[1] != request["id"])
                late.insert(position + 1, next(command for command in commands if command[0] == "set-plan"))
                rows.append((item_id, f"plan-recorded-during-the-next-request", late, None, json.dumps(reply),
                             names - {f"{prefix}-clean"}))
        for mistake, touched in day["effects"].items():
            if not touched:
                continue  # this day's requests do not turn on that rule
            wrong_commands, wrong_reply = own_state_run(books, requests, mistakes=(mistake,))
            rows.append((item_id, f"misreads-{mistake}", wrong_commands, None, json.dumps(wrong_reply), None))
    return rows


def self_calibrate():
    ok = True
    for name, passed in examples():
        ok &= passed
        print(f"example {name}: {'ok' if passed else 'FAIL'}")
    for item_id, day in grader.DAYS.items():
        print(f"{item_id}: misreadings change requests " + ", ".join(f"{name} {', '.join(touched) or '-'}" for name, touched in day["effects"].items()))
    rows = scenarios()
    for item_id, name, commands, mode, answer, expected in rows:
        directory = workspace(item_id, commands, cli=mode == "cli")
        try:
            results, integrity = grader.grade(item_id, os.path.join(directory, "public"), answer)
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        passed = {check for check, value in results.items() if value is True}
        content = grader.check_names(item_id)
        score = sum(1 for check in content if results.get(check) is True) / len(content)
        good = score < 1 if expected is None else expected(passed) if callable(expected) else passed == expected
        ok &= good
        print(f"{item_id} {name}: {integrity}, score {score:.3f}, fails {sorted(set(content) - passed)}"
              + ("" if good else f"  EXPECTED {'a loss' if expected is None else 'the slip alone' if callable(expected) else sorted(expected)}"))
    print(f"RESULT: {'PASS' if ok else 'FAIL'} ({len(rows)} scenarios and the hand-worked examples)")
    return 0 if ok else 1
