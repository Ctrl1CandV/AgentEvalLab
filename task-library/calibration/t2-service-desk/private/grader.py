#!/usr/bin/env python3
"""Grades T2 tickets. The delivered data/db.json must equal a replay of data/audit.log through the original desk.py
on the starting data (integrity); otherwise every check fails, since the data was changed some other way. Then each
order or customer that the ticket should change is compared with the expected state, everything else must be
unchanged, and the reply must list the done and declined requests.
"""
import argparse
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import desk  # noqa: E402
import makegood  # noqa: E402
import shift  # noqa: E402
import shift_desk  # noqa: E402
import tickets  # noqa: E402
from decimal import Decimal  # noqa: E402

TASK_ID = "t2-service-desk"
TASK_VERSION = "0.4.0"
GRADER_VERSION = "1.2.0"
FENCED_BLOCK = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.S | re.I)
# The last fenced block only: its body may not contain another fence, so an earlier block in the reply cannot start the
# match (grader 1.1.0 failed replies that showed commands in a fenced block before the closing JSON block).
CLOSING_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n((?:(?!```).)*?)\r?\n?```\s*$", re.S | re.I)


def json_object(value):
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def final_object(text):
    """The JSON object the reply ends with, bare or in a closing fenced block, or None."""
    text = text.rstrip()
    fenced = CLOSING_FENCE.search(text)
    if fenced and json_object(fenced.group(1)) is not None:
        return json_object(fenced.group(1))
    decoder = json.JSONDecoder()
    for start in reversed([index for index, char in enumerate(text) if char == "{"]):
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if end == len(text) and isinstance(value, dict):
            return value
    return None


def parse_answer(text):
    """POLICY.md asks the reply to end with one JSON object, so prose before it is fine. Otherwise the shared recovery
    rule applies, at the format deduction: a missing final brace, the only fenced object, or the only top-level object."""
    if not isinstance(text, str):
        return "unparsed", None
    answer = final_object(text)
    if answer is not None:
        return "strict", answer
    stripped = text.strip()
    if stripped.startswith("{"):
        for missing in range(1, 4):
            repaired = json_object(stripped + "}" * missing)
            if repaired is not None:
                return "recovered", repaired
    fenced = [found for found in (json_object(block) for block in FENCED_BLOCK.findall(text)) if found is not None]
    if fenced:
        return ("recovered", fenced[0]) if len(fenced) == 1 else ("unparsed", None)
    decoder, objects, index = json.JSONDecoder(), [], 0
    while (start := text.find("{", index)) >= 0:
        try:
            value, index = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(value, dict):
            objects.append(value)
    return ("recovered", objects[0]) if len(objects) == 1 else ("unparsed", None)


def replay(commands):
    db = copy.deepcopy(tickets.BASE_DB)
    for command in commands:
        desk.apply(db, command[0], command[1:])
    return db


def normalized(entity):
    """An order or customer for comparison: refunds in a fixed order."""
    if entity is None:
        return None
    entity = copy.deepcopy(entity)
    if "refunds" in entity:
        entity["refunds"] = sorted(entity["refunds"], key=lambda refund: json.dumps(refund, sort_keys=True))
    return entity


def entities(db):
    return {f"order-{key}": value for key, value in db["orders"].items()} | {f"customer-{key}": value for key, value in db["customers"].items()}


COST_LADDER = (("cost-5", Decimal("1.05")), ("cost-1", Decimal("1.01")), ("cost-0", Decimal("1")))


def makegood_orders(ticket_id):
    """Orders with an accepted report, in report order."""
    ticket = tickets.MAKEGOOD[ticket_id]
    orders = []
    for report in ticket["reports"]:
        if makegood.accepted(tickets.BASE_DB, ticket, report) and report["order"] not in orders:
            orders.append(report["order"])
    return orders


SHIFTS = shift.load()


def check_names(ticket_id):
    """A shift's checks are per ticket (shift.check_names). The ticket's checks: one per entity it should change, then no-other-changes and reply. An optimisation ticket
    has one check per order to make good, then no-other-changes, reply and the cost ladder."""
    if ticket_id in SHIFTS:
        return shift.check_names(SHIFTS[ticket_id]["tickets"], SHIFTS[ticket_id]["db"])
    if ticket_id in tickets.MAKEGOOD:
        return [f"resolved-{order}" for order in makegood_orders(ticket_id)] + ["no-other-changes", "reply"] + [name for name, _ in COST_LADDER]
    base, expected = entities(tickets.BASE_DB), entities(replay(tickets.TICKETS[ticket_id]["actions"]))
    return [name for name in expected if normalized(expected[name]) != normalized(base[name])] + ["no-other-changes", "reply"]


def expected_reply(ticket_id):
    if ticket_id in tickets.MAKEGOOD:
        ticket = tickets.MAKEGOOD[ticket_id]
        flags = [makegood.accepted(tickets.BASE_DB, ticket, report) for report in ticket["reports"]]
        return [number for number, ok in enumerate(flags, 1) if ok], [number for number, ok in enumerate(flags, 1) if not ok]
    ticket = tickets.TICKETS[ticket_id]
    return ticket["done"], ticket["declined"]


def grade_makegood(ticket_id, delivered, commands, results, reply_ok):
    """Each order's accepted reports made good unit for unit with allowed options; nothing else changed; then the
    resolution's cost against the optimum."""
    base = tickets.BASE_DB
    ticket = tickets.MAKEGOOD[ticket_id]
    reports = {(report["order"], report["sku"]): report for report in ticket["reports"] if makegood.accepted(base, ticket, report)}
    entries = [{"order": order_id, **entry} for order_id, order in delivered["orders"].items() for entry in order.get("make_good", [])]
    resolved = {(order, sku): 0 for order, sku in reports}
    allowed_entries = True
    for entry in entries:
        key = (entry["order"], entry["sku"])
        if key not in reports:
            allowed_entries = False
            continue
        allowed = makegood.options(base, ticket, reports[key])
        option = (entry["option"], entry["sent"] if entry["option"] == "substitute" else (entry["sku"] if entry["option"] == "replace" else None))
        if option not in allowed:
            resolved[key] = None
        elif resolved[key] is not None:
            resolved[key] += entry["qty"]
    for order in makegood_orders(ticket_id):
        results[f"resolved-{order}"] = all(count == reports[key]["qty"] for key, count in resolved.items() if key[0] == order)
    only_makegood = all(command[0] == "make-good" for command in commands) and allowed_entries and \
        all(count is None or count <= reports[key]["qty"] for key, count in resolved.items())
    compliant = only_makegood and all(results[f"resolved-{order}"] for order in makegood_orders(ticket_id))
    results["no-other-changes"] = only_makegood and (reply_ok or any(results[f"resolved-{order}"] for order in makegood_orders(ticket_id)))
    if compliant:
        cost, best = makegood.resolution_cost(base, entries), makegood.optimum(base, ticket)
        for name, factor in COST_LADDER:
            results[name] = cost <= best * factor + Decimal("0.005")
        results["cost"] = f"{cost:.4f}"
        results["optimum"] = f"{best:.4f}"


def grade_shift(shift_id, submission, answer_text):
    """A shift: the integrity gate replays the audit log through the shift's desk tool on its starting data; then each
    ticket is graded on the state when it began (shift.grade_shift)."""
    names = check_names(shift_id)
    results = {name: False for name in names}
    results["answer-format"] = False
    mode, answer = parse_answer(answer_text)
    base = SHIFTS[shift_id]["db"]
    try:
        with open(os.path.join(submission, "data", "db.json"), encoding="utf-8") as handle:
            delivered = json.load(handle)
        with open(os.path.join(submission, "data", "audit.log"), encoding="utf-8") as handle:
            commands = [json.loads(line) for line in handle if line.strip()]
        replayed = copy.deepcopy(base)
        consistent = all(isinstance(command, list) and command and all(isinstance(part, str) for part in command) for command in commands)
        if consistent:
            for command in commands:
                shift_desk.apply(replayed, command[0], command[1:])
            consistent = json.loads(json.dumps(replayed)) == delivered
    except (OSError, ValueError, shift_desk.Refused, KeyError, IndexError, TypeError):
        consistent = False
    if not consistent:
        return results, "inconsistent"
    checked, details = shift.grade_shift(base, SHIFTS[shift_id]["tickets"], commands, answer if mode != "unparsed" and isinstance(answer, dict) else {})
    results.update(checked)
    results["costs"] = details
    # The format deduction is for a reply that had to be recovered. A missing or unusable reply already fails the replies.
    results["answer-format"] = mode != "recovered"
    return results, "consistent"


def grade(ticket_id, submission, answer_text):
    if ticket_id in SHIFTS:
        return grade_shift(ticket_id, submission, answer_text)
    names = check_names(ticket_id)
    results = {name: False for name in names}
    results["answer-format"] = False
    mode, answer = parse_answer(answer_text)
    try:
        with open(os.path.join(submission, "data", "db.json"), encoding="utf-8") as handle:
            delivered = json.load(handle)
        with open(os.path.join(submission, "data", "audit.log"), encoding="utf-8") as handle:
            commands = [json.loads(line) for line in handle if line.strip()]
        consistent = all(isinstance(command, list) and command and all(isinstance(part, str) for part in command) for command in commands) and \
            json.loads(json.dumps(replay(commands))) == delivered
    except (OSError, ValueError, desk.Refused, KeyError, IndexError, TypeError):
        consistent = False
    if not consistent:
        return results, "inconsistent"
    done, declined = expected_reply(ticket_id)
    reply_ok = (mode != "unparsed" and isinstance(answer, dict) and isinstance(answer.get("done"), list) and isinstance(answer.get("declined"), list)
                and sorted(answer["done"]) == sorted(done) and sorted(answer["declined"]) == sorted(declined))
    results["reply"] = reply_ok
    # The format deduction is for a reply that had to be recovered. A missing or unusable reply already fails `reply`.
    results["answer-format"] = mode != "recovered"
    if ticket_id in tickets.MAKEGOOD:
        grade_makegood(ticket_id, delivered, commands, results, reply_ok)
        return results, "consistent"
    base, expected, actual = entities(tickets.BASE_DB), entities(replay(tickets.TICKETS[ticket_id]["actions"])), entities(delivered)
    for name in names[:-2]:
        results[name] = name in actual and normalized(actual[name]) == normalized(expected[name])
    untouched = all(normalized(actual.get(name)) == normalized(entity) for name, entity in base.items() if name not in names) and set(actual) == set(base)
    # No other changes guards the actions, so it counts only once something the ticket asks for is right: an
    # untouched shop passes it.
    results["no-other-changes"] = untouched and (reply_ok or any(results[name] for name in names[:-2]))
    results["answer-format"] = mode != "recovered"
    return results, "consistent"


def requirement(ticket_id, name):
    return "REQ-FORMAT" if name == "answer-format" else f"REQ-{ticket_id.upper()}-{name.upper()}"


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=1)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    ticket_id = request["context"].get("itemId")
    if ticket_id not in tickets.TICKETS and ticket_id not in tickets.MAKEGOOD and ticket_id not in SHIFTS:
        raise ValueError("unknown item")
    evidence_root = request["evidenceRoot"]
    try:
        with open(os.path.join(evidence_root, request["answerRef"]), encoding="utf-8") as handle:
            answer_text = handle.read()
    except (OSError, TypeError):
        answer_text = None
    results, integrity = grade(ticket_id, os.path.join(request["submission"]["directory"], "public"), answer_text)
    write_json(os.path.join(evidence_root, "checks.json"), {"itemId": ticket_id, "integrity": integrity, "results": results})
    active = set(request["context"]["activeRequirementIds"])
    checks = [{"id": f"{ticket_id}-{name}" if name != "answer-format" else "answer-format", "requirementId": requirement(ticket_id, name),
               "status": "pass" if passed else "fail", "evidenceRefs": ["checks.json"]}
              for name, passed in sorted(results.items()) if requirement(ticket_id, name) in active and isinstance(passed, bool)]
    write_json(result_path, {"schemaVersion": 1, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--result")
    parser.add_argument("--self-calibrate", action="store_true")
    args = parser.parse_args()
    if args.self_calibrate:
        import calibrate
        raise SystemExit(calibrate.self_calibrate())
    if not args.request or not args.result:
        parser.error("--request and --result are required")
    grade_request(args.request, args.result)


if __name__ == "__main__":
    main()
