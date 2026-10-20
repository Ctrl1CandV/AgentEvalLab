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
import tickets  # noqa: E402

TASK_ID = "t2-service-desk"
TASK_VERSION = "0.1.0"
GRADER_VERSION = "1.0.1"
FENCED_BLOCK = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.S | re.I)
CLOSING_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```\s*$", re.S | re.I)


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


def check_names(ticket_id):
    """The ticket's checks: one per entity it should change, then no-other-changes and reply."""
    base, expected = entities(tickets.BASE_DB), entities(replay(tickets.TICKETS[ticket_id]["actions"]))
    return [name for name in expected if normalized(expected[name]) != normalized(base[name])] + ["no-other-changes", "reply"]


def grade(ticket_id, submission, answer_text):
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
    base, expected, actual = entities(tickets.BASE_DB), entities(replay(tickets.TICKETS[ticket_id]["actions"])), entities(delivered)
    for name in names[:-2]:
        results[name] = name in actual and normalized(actual[name]) == normalized(expected[name])
    ticket = tickets.TICKETS[ticket_id]
    reply_ok = (mode != "unparsed" and isinstance(answer, dict) and isinstance(answer.get("done"), list) and isinstance(answer.get("declined"), list)
                and sorted(answer["done"]) == sorted(ticket["done"]) and sorted(answer["declined"]) == sorted(ticket["declined"]))
    results["reply"] = reply_ok
    untouched = all(normalized(actual.get(name)) == normalized(entity) for name, entity in base.items() if name not in names) and set(actual) == set(base)
    # No other changes guards the actions, so it counts only once something the ticket asks for is right: an
    # untouched shop passes it.
    results["no-other-changes"] = untouched and (reply_ok or any(results[name] for name in names[:-2]))
    results["answer-format"] = mode == "strict"
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
    if ticket_id not in tickets.TICKETS:
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
              for name, passed in sorted(results.items()) if requirement(ticket_id, name) in active]
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
