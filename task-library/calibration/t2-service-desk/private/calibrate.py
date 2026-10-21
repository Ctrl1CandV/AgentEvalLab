"""Self-calibration of the T2 grader: the expected actions run through desk.py pass every check of their ticket, and
known wrong handlings pass exactly the checks they should. No model is involved."""
import copy
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal

import grader
import makegood
import oracle
import tickets

HERE = os.path.dirname(os.path.abspath(__file__))


def workspace(commands, edit=None):
    """A copy of the starting public files after running commands through desk.py; edit(db) then changes db.json directly."""
    directory = tempfile.mkdtemp(prefix="t2-calibration-")
    public = os.path.join(directory, "public")
    os.makedirs(os.path.join(public, "data"))
    shutil.copy(os.path.join(HERE, "desk.py"), public)
    with open(os.path.join(public, "data", "db.json"), "w", encoding="utf-8") as handle:
        json.dump(tickets.BASE_DB, handle, indent=1, sort_keys=True)
    open(os.path.join(public, "data", "audit.log"), "w").close()
    for command in commands:
        run = subprocess.run([sys.executable, "desk.py", *command], cwd=public, capture_output=True, text=True)
        assert run.returncode == 0, (command, run.stderr)
    if edit:
        path = os.path.join(public, "data", "db.json")
        with open(path, encoding="utf-8") as handle:
            db = json.load(handle)
        edit(db)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(db, handle)
    return directory


def reply(ticket, done=None, declined=None):
    return json.dumps({"done": ticket["done"] if done is None else done, "declined": ticket["declined"] if declined is None else declined})


def scenarios():
    rows = []
    for ticket_id, ticket in tickets.TICKETS.items():
        names = set(grader.check_names(ticket_id)) | {"answer-format"}
        rows.append((ticket_id, "oracle", ticket["actions"], None, reply(ticket), names))
        rows.append((ticket_id, "untouched", [], None, None, set()))
        # POLICY.md asks for a reply that ends with the object, so prose before it, and a closing fence, are fine.
        rows.append((ticket_id, "oracle-after-prose", ticket["actions"], None, "Done.\n\n" + reply(ticket), names))
        rows.append((ticket_id, "oracle-fenced", ticket["actions"], None, "Done.\n\n```json\n" + reply(ticket) + "\n```\n", names))
        rows.append((ticket_id, "oracle-then-prose", ticket["actions"], None, reply(ticket) + "\n\nAll handled.", names - {"answer-format"}))
        # Without a reply, a ticket that only declines is the same as doing nothing.
        rows.append((ticket_id, "oracle-without-reply", ticket["actions"], None, "All handled.",
                     {name for name in names if name.startswith(("order-", "customer-"))} | ({"no-other-changes"} if ticket["actions"] else set())))
        if ticket["actions"]:
            expected = grader.replay(ticket["actions"])
            rows.append((ticket_id, "direct-edit", [], lambda db, expected=expected: db.update(copy.deepcopy(expected)), reply(ticket), set()))
    # Wrong handlings, one per trap; each passes exactly the checks it should.
    wrong = [
        ("t02", "credit-refunded-last", [["refund", "O-5004", "EL-102", "1", "135.15", "0.00"], ["refund", "O-5004", "HM-401", "1", "29.70", "25.55"]],
         [1, 2], [3, 4], {"customer-C-1002", "no-other-changes", "reply"}),
        ("t03", "gift-card-refunded-to-card", [["refund", "O-5006", "EL-200", "1", "99.00", "0.00"], ["compensate", "O-5005", "7.00"]],
         [1, 3], [2, 4], {"order-O-5005", "no-other-changes", "reply"}),
        ("t04", "acted-for-unverified-address", [["refund", "O-5006", "EL-200", "1", "0.00", "99.00"], ["compensate", "O-5005", "7.00"]],
         [1, 2], [], set()),
        ("t05", "exchange-credit-at-list-price", [["exchange", "O-5007", "HM-401", "HM-400"], ["add-credit", "C-1004", "20.00"],
                                                   ["adjust-price", "O-5009", "EL-103", "10.00"]],
         [1, 3], [2, 4], {"order-O-5007", "order-O-5009", "no-other-changes", "reply"}),
        ("t06", "compensation-at-list-prices", [["refund", "O-5010", "CL-500", "1", "89.30", "18.70"], ["compensate", "O-5010", "24.30"]],
         [1, 4], [2, 3], {"no-other-changes", "reply"}),
        ("t07", "book-returned-outside-gold-window", [["refund", "O-5011", "EL-200", "1", "99.00", "0.00"], ["refund", "O-5011", "BK-300", "1", "28.00", "0.00"],
                                                      ["compensate", "O-5011", "25.80"]],
         [1, 2, 4], [3], {"customer-C-1006", "no-other-changes"}),
        ("t08", "guessed-the-headphones", [["refund", "O-5012", "EL-101", "1", "39.00", "0.00"], ["set-address", "O-5013", "3 Harbour Lane, Bristol"]],
         [1, 3], [2], {"order-O-5013"}),
        ("t09", "address-of-cancelled-order", [["cancel-line", "O-5001", "HM-400"], ["cancel-line", "O-5001", "BK-300"],
                                               ["set-address", "O-5001", "22 Canal Street, Leeds"], ["refund", "O-5002", "EL-100", "1", "129.00", "0.00"]],
         [1, 2, 3, 4], [], {"order-O-5002", "no-other-changes"}),
        ("t12", "price-drop-from-list-price", [["adjust-price", "O-5015", "EL-103", "10.00"], ["exchange", "O-5015", "CL-501", "CL-500"],
                                               ["add-credit", "C-1006", "42.00"]],
         [1, 2], [3], {"no-other-changes", "reply"}),
    ]
    for ticket_id, name, commands, done, declined, expected in wrong:
        rows.append((ticket_id, name, commands, None, reply(tickets.TICKETS[ticket_id], done=done, declined=declined), expected | {"answer-format"}))
    return rows + makegood_scenarios()


def makegood_scenarios():
    """Optimisation tickets: the optimum passes everything; compliant but costlier resolutions pass the compliance
    checks and the cost rungs their cost reaches; each broken rule fails the order it touches and every cost rung."""
    rows = []
    base = tickets.BASE_DB
    for ticket_id, ticket in tickets.MAKEGOOD.items():
        names = set(grader.check_names(ticket_id)) | {"answer-format"}
        costs = {name for name, _ in grader.COST_LADDER}
        compliance = names - costs
        done, declined = grader.expected_reply(ticket_id)
        answer = json.dumps({"done": done, "declined": declined})
        best, entries = makegood.solve(base, ticket)
        rows.append((ticket_id, "optimum", makegood.commands(entries), None, answer, names))
        rows.append((ticket_id, "untouched", [], None, None, set()))
        rows.append((ticket_id, "optimum-without-reply", makegood.commands(entries), None, "All handled.", names - {"reply", "answer-format"}))

        def ladder(resolution):
            cost = makegood.resolution_cost(base, resolution)
            return {name for name, factor in grader.COST_LADDER if cost <= best * factor + Decimal("0.005")}
        shortcut = makegood.greedy(base, ticket)
        rows.append((ticket_id, "ignores-carrier-rates", makegood.commands(shortcut), None, answer, compliance | ladder(shortcut)))
        refunds = makegood.money_only(base, ticket)
        rows.append((ticket_id, "refunds-everything", makegood.commands(refunds), None, answer, compliance | ladder(refunds)))
        orders = grader.makegood_orders(ticket_id)
        first = entries[0]
        # One unit fewer than reported on the first entry's order.
        short = [dict(entry) for entry in entries]
        if short[0]["qty"] > 1:
            short[0]["qty"] -= 1
        else:
            short = short[1:]
        rows.append((ticket_id, "one-unit-short", makegood.commands(short), None, answer, compliance - {f"resolved-{first['order']}"}))
        declined_reports = [report for report in ticket["reports"] if not makegood.accepted(base, ticket, report)]
        if declined_reports:
            report = declined_reports[0]
            extra = makegood.commands([{"order": report["order"], "sku": report["sku"], "qty": report["qty"], "option": "refund", "sent": None}])
            rows.append((ticket_id, "makes-good-a-declined-report", makegood.commands(entries) + extra, None, answer, compliance - {"no-other-changes"}))
        money = [entry for entry in entries if entry["option"] in ("refund", "credit")]
        if ticket["constraints"]["no_credit"] and money:
            swapped = [dict(entry, option="credit") if entry is money[0] else entry for entry in entries]
            rows.append((ticket_id, "credit-despite-refusal", makegood.commands(swapped), None, answer, compliance - {f"resolved-{money[0]['order']}"}))
        blocked = ticket["constraints"]["no_shipping_to"]
        at_blocked = [entry for entry in money if base["orders"][entry["order"]]["address"].lower() == blocked.lower()] if blocked else []
        used = sum(entry["qty"] for entry in entries if at_blocked and entry["sent"] == at_blocked[0]["sku"])
        if at_blocked and base["products"][at_blocked[0]["sku"]].get("stock", 0) - used >= at_blocked[0]["qty"]:
            sent = [dict(entry, option="replace", sent=entry["sku"]) if entry is at_blocked[0] else entry for entry in entries]
            rows.append((ticket_id, "sent-to-blocked-address", makegood.commands(sent), None, answer, compliance - {f"resolved-{at_blocked[0]['order']}"}))
        assert orders
    return rows


def data_checks():
    """The starting data is consistent, and oracle.py derives every ticket's commands and lists as written by hand."""
    failures = []
    for order_id, order in tickets.BASE_DB["orders"].items():
        paid = sum(oracle.unit_paid(order, line) * line["qty"] for line in order["lines"]) + Decimal(order["shipping"])
        if paid != Decimal(order["payments"]["card"]) + Decimal(order["payments"]["credit"]):
            failures.append(f"{order_id}: payments do not add up to {paid}")
    for ticket_id, ticket in tickets.TICKETS.items():
        if oracle.handle(ticket_id) != (ticket["actions"], ticket["done"], ticket["declined"]):
            failures.append(f"{ticket_id}: oracle disagrees: {oracle.handle(ticket_id)}")
    for ticket_id, ticket in tickets.MAKEGOOD.items():
        best = makegood.optimum(tickets.BASE_DB, ticket)
        brute = brute_force(ticket)
        if brute is not None and brute != best:
            failures.append(f"{ticket_id}: the min-cost flow gives {best}, enumeration {brute}")
    return failures


def brute_force(ticket, limit=8):
    """The optimum by enumerating every unit's option, for tickets of at most `limit` units; None for larger ones."""
    base = tickets.BASE_DB
    units = []
    for report in ticket["reports"]:
        if makegood.accepted(base, ticket, report):
            order = base["orders"][report["order"]]
            place = (order["country"], order["address"].strip().lower())
            units += [(place, makegood.options(base, ticket, report))] * report["qty"]
    if len(units) > limit:
        return None
    best = None
    for choice in itertools.product(*[sorted(allowed, key=str) for _, allowed in units]):
        stock, cost, places = {}, Decimal("0"), set()
        for (place, allowed), option in zip(units, choice):
            sent, unit_cost = allowed[option]
            cost += unit_cost
            if sent is not None:
                stock[sent] = stock.get(sent, 0) + 1
                places.add(place)
        if any(count > base["products"][sku].get("stock", 0) for sku, count in stock.items()):
            continue
        cost += sum((Decimal(base["rates"][country]) for country, _ in places), Decimal("0"))
        best = cost if best is None or cost < best else best
    return best


def self_calibrate():
    failures = data_checks()
    for failure in failures:
        print(f"DATA: {failure}")
    ok = not failures
    for ticket_id, name, commands, edit, answer, expected in scenarios():
        directory = workspace(commands, edit)
        try:
            results, integrity = grader.grade(ticket_id, os.path.join(directory, "public"), answer)
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        passed = {check for check, value in results.items() if value is True}
        good = passed == expected
        ok &= good
        print(f"{ticket_id} {name}: {integrity}, passes {sorted(passed)}" + ("" if good else f"  EXPECTED {sorted(expected)}"))
    rows = len(scenarios())
    print(f"RESULT: {'PASS' if ok else 'FAIL'} ({rows} scenarios, data and oracle checks {'passed' if not failures else 'failed'})")
    return 0 if ok else 1
