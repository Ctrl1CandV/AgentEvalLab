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
import shift
import shift_desk
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
        # No reply is no format failure: it fails `reply` (and every record check here), so nothing scores.
        rows.append((ticket_id, "untouched", [], None, None, {"answer-format"}))
        # POLICY.md asks for a reply that ends with the object, so prose before it, and a closing fence, are fine.
        rows.append((ticket_id, "oracle-after-prose", ticket["actions"], None, "Done.\n\n" + reply(ticket), names))
        rows.append((ticket_id, "oracle-fenced", ticket["actions"], None, "Done.\n\n```json\n" + reply(ticket) + "\n```\n", names))
        # Commands shown in an earlier fenced block do not hide the closing JSON block (grader 1.1.1).
        rows.append((ticket_id, "oracle-fenced-after-a-fence", ticket["actions"], None,
                     "Commands:\n\n```\npython3 desk.py ...\n```\n\nDone.\n\n```json\n" + reply(ticket) + "\n```", names))
        rows.append((ticket_id, "oracle-then-prose", ticket["actions"], None, reply(ticket) + "\n\nAll handled.", names - {"answer-format"}))
        # Without a reply, a ticket that only declines is the same as doing nothing.
        rows.append((ticket_id, "oracle-without-reply", ticket["actions"], None, "All handled.",
                     {name for name in names if name.startswith(("order-", "customer-"))} | ({"no-other-changes"} if ticket["actions"] else set()) | {"answer-format"}))
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
        rows.append((ticket_id, "untouched", [], None, None, {"answer-format"}))
        rows.append((ticket_id, "optimum-without-reply", makegood.commands(entries), None, "All handled.", names - {"reply"}))
        rows.append((ticket_id, "optimum-fenced-after-a-fence", makegood.commands(entries), None,
                     "Commands:\n\n```\nmake-good ...\n```\n\n```json\n" + answer + "\n```", names))

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


def shift_workspace(shift_id, commands, cli=False):
    """A shift's starting public files after its commands: through desk.py itself when cli, else applied in process and
    written as desk.py writes them."""
    directory = tempfile.mkdtemp(prefix="t2-shift-")
    public = os.path.join(directory, "public")
    os.makedirs(os.path.join(public, "data"))
    shutil.copy(os.path.join(HERE, "shift_desk.py"), os.path.join(public, "desk.py"))
    db = copy.deepcopy(grader.SHIFTS[shift_id]["db"])
    with open(os.path.join(public, "data", "db.json"), "w", encoding="utf-8") as handle:
        json.dump(db, handle, indent=1, sort_keys=True)
    open(os.path.join(public, "data", "audit.log"), "w").close()
    if cli:
        for command in commands:
            run = subprocess.run([sys.executable, "desk.py", *command], cwd=public, capture_output=True, text=True)
            assert run.returncode == 0, (command, run.stderr)
        return directory
    for command in commands:
        shift_desk.apply(db, command[0], command[1:])
    with open(os.path.join(public, "data", "db.json"), "w", encoding="utf-8") as handle:
        json.dump(db, handle, indent=1, sort_keys=True)
    with open(os.path.join(public, "data", "audit.log"), "w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(command) + "\n" for command in commands)
    return directory


def own_state_run(base, tickets_, slip=None):
    """A desk that handles every ticket as the oracle would on the state it has itself produced, except that `slip`
    (ticket id, function) rewrites that ticket's commands and reply. Returns (commands, reply)."""
    db = copy.deepcopy(base)
    commands, answer = [], {}
    for ticket in tickets_:
        result = shift.handle(db, ticket)
        mine, done, declined = result["commands"], result["done"], result["declined"]
        if slip and slip[0] == ticket["id"]:
            mine, done, declined = slip[1](db, ticket, result)
        for command in mine:
            shift_desk.apply(db, command[0], command[1:])
        commands += mine
        answer[ticket["id"]] = {"done": done, "declined": declined}
    return commands, answer


def shift_scenarios():
    """Shifts: the oracle passes everything; an untouched shop and a reply alone pass what they should; a desk that
    slips once, then handles every later ticket correctly on the state it produced, loses only the slipped ticket's
    checks (attribution); and a desk that misreads one rule throughout loses checks."""
    rows = []
    for shift_id, record in grader.SHIFTS.items():
        base, tickets_ = record["db"], record["tickets"]
        names = set(grader.check_names(shift_id)) | {"answer-format"}
        results, _ = shift.run(base, tickets_)
        commands = [command for _, result in results for command in result["commands"]]
        answer = {ticket["id"]: {"done": result["done"], "declined": result["declined"]} for ticket, (_, result) in zip(tickets_, results)}
        rows.append((shift_id, "oracle-through-desk-py", commands, "cli", json.dumps(answer), names))
        rows.append((shift_id, "untouched", [], None, None, {"answer-format"}))
        # The oracle's reply alone, on a shop where nothing was done: a ticket's reply passes when it is also right for
        # that untouched shop (a review or the goodwill limit may then not apply), and so does the no-other-changes
        # check of a ticket that only declines. Nothing that needs carrying out passes.
        work = {name.rsplit("-", 1)[0] for name in names if name.endswith(("-actions", "-makegood"))}
        still = {ticket["id"].lower() for ticket in tickets_ if (lambda untouched: (untouched["done"], untouched["declined"]) ==
                                                                 (answer[ticket["id"]]["done"], answer[ticket["id"]]["declined"]))(shift.handle(base, ticket))}
        rows.append((shift_id, "reply-only", [], None, json.dumps(answer),
                     {f"{prefix}-reply" for prefix in still} | {f"{prefix}-clean" for prefix in still if prefix not in work} | {"answer-format"}))
        # Without begin markers the ticket boundaries are inferred from the orders the commands touch.
        rows.append((shift_id, "oracle-without-begin", [command for command in commands if command[0] != "begin"], None, json.dumps(answer), names))
        rows.append((shift_id, "oracle-recovered-reply", commands, None, "Shift done: " + json.dumps(answer) + " (end)", names - {"answer-format"}))
        # One slip, then correct handling on the desk's own state: only the slipped ticket loses checks.
        for ticket, (state, result) in zip(tickets_, results):
            prefix = ticket["id"].lower()
            if result["accepted"]:
                def refund_all(db, ticket_, result_):
                    entries = [{"order": report["order"], "sku": report["sku"], "qty": report["qty"], "option": "refund", "sent": None}
                               for report in result_["accepted"]]
                    kept = [command for command in result_["commands"] if command[0] != "make-good"]
                    return kept + makegood.commands(entries), result_["done"], result_["declined"]
                slipped, slipped_answer = own_state_run(base, tickets_, (ticket["id"], refund_all))
                refunds = sum((makegood.unit_paid(state["orders"][report["order"]], shift.find_line(state["orders"][report["order"]], report["sku"])) * report["qty"]
                               for report in result["accepted"]), Decimal("0"))
                lost = set() if refunds <= result["cost"] + Decimal("0.005") else {f"{prefix}-cost-0"}
                lost |= set() if refunds <= result["cost"] * Decimal("1.05") + Decimal("0.005") else {f"{prefix}-cost-5"}
                rows.append((shift_id, f"refunds-everything-in-{ticket['id']}-only", slipped, None, json.dumps(slipped_answer), names - lost))

                def drop_first(db, ticket_, result_):
                    report = result_["accepted"][0]
                    number = ticket_["requests"].index(report) + 1
                    redone = shift.handle(db, {**ticket_, "requests": [request if request is not report else {**request, "kind": "skipped"}
                                                                       for request in ticket_["requests"]]})
                    done = [value for value in result_["done"] if value != number]
                    return redone["commands"], done, sorted(result_["declined"] + [number])
                slipped, slipped_answer = own_state_run(base, tickets_, (ticket["id"], drop_first))
                # Every other ticket passes everything; the slipped ticket at least loses its reply.
                others = {name for name in names if not name.startswith(prefix + "-")}
                rows.append((shift_id, f"declines-an-accepted-report-in-{ticket['id']}-only", slipped, None, json.dumps(slipped_answer),
                             lambda passed, others=others, prefix=prefix: others <= passed and f"{prefix}-reply" not in passed))
                break
        for mistake in shift.MISTAKES:
            wrong, _ = shift.run(base, tickets_, (mistake,))
            wrong_commands = [command for _, result in wrong for command in result["commands"]]
            wrong_answer = {ticket["id"]: {"done": result["done"], "declined": result["declined"]} for ticket, (_, result) in zip(tickets_, wrong)}
            rows.append((shift_id, f"misreads-{mistake}", wrong_commands, None, json.dumps(wrong_answer), None))
    return rows


def shift_brute_force(state, ticket, result, limit=8):
    """The least make-good cost of a ticket by enumeration, with stock and today's shipments; None for large tickets."""
    units = []
    for report in result["accepted"]:
        order = state["orders"][report["order"]]
        place = (order["country"], order["address"].strip().lower())
        units += [(place, shift.options(state, ticket, report, result["credit_ok"]))] * report["qty"]
    if len(units) > limit:
        return None
    free = shift.shipped_today(state)
    best = None
    for choice in itertools.product(*[sorted(allowed, key=str) for _, allowed in units]):
        stock, cost, places = {}, Decimal("0"), set()
        for (place, allowed), option in zip(units, choice):
            sent, unit_cost = allowed[option]
            cost += unit_cost
            if sent is not None:
                stock[sent] = stock.get(sent, 0) + 1
                places.add(place)
        if any(count > state["products"][sku].get("stock", 0) for sku, count in stock.items()):
            continue
        cost += sum((Decimal(state["rates"][country]) for country, address in places if (country, address) not in free), Decimal("0"))
        best = cost if best is None or cost < best else best
    return best if best is not None else Decimal("0")


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
    for shift_id, record in grader.SHIFTS.items():
        for order_id, order in record["db"]["orders"].items():
            paid = sum(oracle.unit_paid(order, line) * line["qty"] for line in order["lines"]) + Decimal(order["shipping"])
            if paid != Decimal(order["payments"]["card"]) + Decimal(order["payments"]["credit"]):
                failures.append(f"{shift_id} {order_id}: payments do not add up to {paid}")
        results, _ = shift.run(record["db"], record["tickets"])
        for ticket, (state, result) in zip(record["tickets"], results):
            brute = shift_brute_force(state, ticket, result) if result["accepted"] else None
            if brute is not None and brute != result["cost"]:
                failures.append(f"{shift_id} {ticket['id']}: the min-cost flow gives {result['cost']}, enumeration {brute}")
        effects = shift.mistake_effects(record["db"], record["tickets"])
        if effects != record["effects"] or not all(effects.values()):
            failures.append(f"{shift_id}: misreading effects {effects} differ from the recorded {record['effects']} or miss one")
        print(f"{shift_id}: misreadings change tickets " + ", ".join(f"{name} {', '.join(touched)}" for name, touched in effects.items()))
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
    shift_rows = shift_scenarios()
    for shift_id, name, commands, mode, answer, expected in shift_rows:
        directory = shift_workspace(shift_id, commands, cli=mode == "cli")
        try:
            results, integrity = grader.grade(shift_id, os.path.join(directory, "public"), answer)
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        passed = {check for check, value in results.items() if value is True}
        content = [check for check in grader.check_names(shift_id)]
        score = sum(1 for check in content if results.get(check) is True) / len(content)
        # A misreading throughout the shift must cost something; the other scenarios pass exactly the expected checks.
        good = score < 1 if expected is None else expected(passed) if callable(expected) else passed == expected
        ok &= good
        print(f"{shift_id} {name}: {integrity}, score {score:.3f}, fails {sorted(set(content) - passed)}"
              + ("" if good else f"  EXPECTED {'a loss' if expected is None else 'the slip alone' if callable(expected) else sorted(expected)}"))
    rows = len(scenarios()) + len(shift_rows)
    print(f"RESULT: {'PASS' if ok else 'FAIL'} ({rows} scenarios, data and oracle checks {'passed' if not failures else 'failed'})")
    return 0 if ok else 1
