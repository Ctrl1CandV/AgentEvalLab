#!/usr/bin/env python3
"""Grades a T2 finance close day. The delivered data/books.json must equal a replay of data/audit.log through the
item's ledger.py on the starting books (integrity); otherwise every check fails. Then each request is graded against
the oracle (finance.py) on the state when the request began, so that one mistake is deducted where it was made. Since
grader 1.2.0 two checks cover the whole day: every changing command belongs to one request of the day, handled in
order (coverage), and the books from the original start equal a correctly handled day (end state)."""
import argparse
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import finance  # noqa: E402
import ledger  # noqa: E402

TASK_ID = "t2-finance-desk"
TASK_VERSION = "0.3.0"
GRADER_VERSION = "1.2.0"
DAYS_PATH = os.path.join(HERE, "days.json")
FENCED_BLOCK = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.S | re.I)
CLOSING_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n((?:(?!```).)*?)\r?\n?```\s*$", re.S | re.I)


def load_days():
    try:
        with open(DAYS_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except OSError:
        return {}


DAYS = load_days()


def known_plans(days):
    """The build searched each day's payment plan; its best plan known is the top of the plan's scale."""
    for day in days.values():
        best = day.get("plan_best")
        if best:
            finance.KNOWN_BEST[best["signature"]] = (best["value"], best["slots"])


known_plans(DAYS)


def json_object(value):
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_answer(text):
    """The manual asks the reply to end with one JSON object (bare or in a closing fenced block), so prose before it is
    fine. Otherwise the shared recovery rule applies, at the format deduction."""
    if not isinstance(text, str):
        return "unparsed", None
    stripped = text.rstrip()
    fenced = CLOSING_FENCE.search(stripped)
    if fenced and json_object(fenced.group(1)) is not None:
        return "strict", json_object(fenced.group(1))
    decoder = json.JSONDecoder()
    for start in reversed([index for index, char in enumerate(stripped) if char == "{"]):
        try:
            value, end = decoder.raw_decode(stripped, start)
        except json.JSONDecodeError:
            continue
        if end == len(stripped) and isinstance(value, dict):
            return "strict", value
    if stripped.lstrip().startswith("{"):
        for missing in range(1, 4):
            repaired = json_object(stripped.strip() + "}" * missing)
            if repaired is not None:
                return "recovered", repaired
    blocks = [found for found in (json_object(block) for block in FENCED_BLOCK.findall(text)) if found is not None]
    if blocks:
        return ("recovered", blocks[0]) if len(blocks) == 1 else ("unparsed", None)
    objects, index = [], 0
    while (start := text.find("{", index)) >= 0:
        try:
            value, index = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(value, dict):
            objects.append(value)
    return ("recovered", objects[0]) if len(objects) == 1 else ("unparsed", None)


def check_names(item_id):
    return finance.check_names(DAYS[item_id]["requests"])


def grade(item_id, submission, answer_text, evidence=None):
    day = DAYS[item_id]
    names = check_names(item_id)
    results = {name: False for name in names}
    results["answer-format"] = False
    mode, answer = parse_answer(answer_text)
    try:
        with open(os.path.join(submission, "data", "books.json"), encoding="utf-8") as handle:
            delivered = json.load(handle)
        with open(os.path.join(submission, "data", "audit.log"), encoding="utf-8") as handle:
            commands = [json.loads(line) for line in handle if line.strip()]
        replayed = copy.deepcopy(day["books"])
        for command in commands:
            if not isinstance(command, list) or not command or not isinstance(command[0], str):
                raise ValueError("audit line")
            ledger.apply(replayed, command[0], command[1:])
        consistent = json.loads(json.dumps(replayed)) == delivered
    except (OSError, ValueError, ledger.Refused, KeyError, IndexError, TypeError, AttributeError):
        consistent = False
    if not consistent:
        return results, "inconsistent"
    results.update(finance.grade(day["books"], day["requests"], commands, answer if mode != "unparsed" and isinstance(answer, dict) else {}, evidence))
    # The format deduction is for a reply that had to be recovered; a missing reply already fails every outcome.
    results["answer-format"] = mode != "recovered"
    return results, "consistent"


def requirement(item_id, name):
    return "REQ-FORMAT" if name == "answer-format" else f"REQ-{item_id.upper()}-{name.upper()}"


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=1)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    item_id = request["context"].get("itemId")
    if item_id not in DAYS:
        raise ValueError("unknown item")
    evidence_root = request["evidenceRoot"]
    try:
        with open(os.path.join(evidence_root, request["answerRef"]), encoding="utf-8") as handle:
            answer_text = handle.read()
    except (OSError, TypeError):
        answer_text = None
    day = {}
    results, integrity = grade(item_id, os.path.join(request["submission"]["directory"], "public"), answer_text, day)
    write_json(os.path.join(evidence_root, "checks.json"), {"itemId": item_id, "integrity": integrity, "results": results, "day": day})
    active = set(request["context"]["activeRequirementIds"])
    checks = [{"id": f"{item_id}-{name}" if name != "answer-format" else "answer-format", "requirementId": requirement(item_id, name),
               "status": "pass" if passed else "fail", "evidenceRefs": ["checks.json"]}
              for name, passed in sorted(results.items()) if requirement(item_id, name) in active]
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
