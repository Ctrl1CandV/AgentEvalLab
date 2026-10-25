#!/usr/bin/env python3
"""Grades AR replies: ARC tasks, pass@2. The reply is one JSON object

    {"test": [{"attempt_1": <grid>, "attempt_2": <grid>}, ...]}

with one entry per test input, in order. A test output is matched when either of its first two attempts equals the
expected grid exactly (dimensions included); later attempts and extra entries are ignored. One critical check per test
output (`test-<n>`); the task is resolved when every test output is matched. Format: a reply that is exactly that one
object is strict; one whose last JSON object (fenced or not) is it is recovered and graded on its content, with the
format check failed; otherwise every check fails. Raw values: `testShare` and `wellFormed`.

Usage: grader.py --request REQUEST --result RESULT | --self-calibrate
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS_PATH = os.path.join(HERE, "keys.json")
TASK_ID = "ar-abstraction"
TASK_VERSION = "0.1.0"
GRADER_VERSION = "1.1.0"  # 1.1.0 (2026-10-25): the format deduction is 10% and applies to the headline (score model only; checks unchanged)
ATTEMPTS = 2


def is_grid(value):
    """A rectangular grid of 1 to 30 rows and columns of integers 0 to 9."""
    if not isinstance(value, list) or not 1 <= len(value) <= 30:
        return False
    width = len(value[0]) if isinstance(value[0], list) else -1
    return 1 <= width <= 30 and all(isinstance(row, list) and len(row) == width and
                                    all(isinstance(cell, int) and not isinstance(cell, bool) and 0 <= cell <= 9 for cell in row) for row in value)


def objects_in(text):
    """Every top-level JSON object in a text, in order."""
    decoder, found, index = json.JSONDecoder(), [], 0
    while True:
        start = text.find("{", index)
        if start < 0:
            return found
        try:
            value, end = decoder.raw_decode(text, start)
            if isinstance(value, dict):
                found.append(value)
            index = end
        except json.JSONDecodeError:
            index = start + 1


def parse_answer(text):
    """(mode, answer): strict when the reply is exactly the answer object, recovered when its last JSON object is,
    unparsed otherwise."""
    stripped = text.strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, dict) and isinstance(value.get("test"), list):
            return "strict", value
    except json.JSONDecodeError:
        pass
    candidates = [value for value in objects_in(re.sub(r"```(?:json)?", "", text)) if isinstance(value.get("test"), list)]
    return ("recovered", candidates[-1]) if candidates else ("unparsed", None)


def grade_answer(mode, answer, key):
    """{test index: matched}, and whether every given attempt was a well-formed grid."""
    entries = answer.get("test") if mode != "unparsed" else None
    matched, well_formed = {}, mode != "unparsed"
    for index, expected in enumerate(key, 1):
        entry = entries[index - 1] if isinstance(entries, list) and len(entries) >= index else None
        attempts = [entry.get(f"attempt_{number}") for number in range(1, ATTEMPTS + 1)] if isinstance(entry, dict) else []
        given = [attempt for attempt in attempts if attempt is not None]
        well_formed = well_formed and bool(given) and all(is_grid(attempt) for attempt in given)
        matched[index] = any(attempt == expected for attempt in given)
    return matched, well_formed


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def checks_of(mode, matched, active):
    checks = [{"id": f"test-{index}", "requirementId": f"REQ-TEST-{index}", "status": "pass" if ok else "fail", "evidenceRefs": []}
              for index, ok in matched.items() if f"REQ-TEST-{index}" in active]
    if "REQ-FORMAT" in active:
        checks.append({"id": "answer-format", "requirementId": "REQ-FORMAT", "status": "pass" if mode == "strict" else "fail", "evidenceRefs": []})
    return checks


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    with open(KEYS_PATH, encoding="utf-8") as handle:
        keys = json.load(handle)
    context = request["context"]
    item_id = context.get("itemId")
    if item_id not in keys:
        raise ValueError("unknown item")
    try:
        with open(os.path.join(request["evidenceRoot"], request["answerRef"]), encoding="utf-8") as handle:
            mode, answer = parse_answer(handle.read())
    except (OSError, UnicodeDecodeError, TypeError):
        mode, answer = "unparsed", None
    matched, well_formed = grade_answer(mode, answer, keys[item_id])
    checks = checks_of(mode, matched, set(context["activeRequirementIds"]))
    write_json(os.path.join(request["evidenceRoot"], "tests.json"), {"itemId": item_id, "parse": mode, "matched": matched, "wellFormed": well_formed})
    for check in checks:
        check["evidenceRefs"] = ["tests.json"]
    write_json(result_path, {"schemaVersion": 2, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None,
                             "metrics": [{"id": "testShare", "value": sum(matched.values()) / len(matched)},
                                         {"id": "wellFormed", "value": 1 if well_formed else 0}]})


def self_calibrate():
    """The official outputs resolve every task, in either attempt; wrong, missing and malformed answers fail as the
    format rules say. No model is involved."""
    with open(KEYS_PATH, encoding="utf-8") as handle:
        keys = json.load(handle)
    rows = []

    def expect(name, item_id, text, matched, mode):
        got_mode, answer = parse_answer(text)
        got, _ = grade_answer(got_mode, answer, keys[item_id])
        ok = got_mode == mode and [got[index] for index in sorted(got)] == matched
        rows.append((name, ok))
        if not ok:
            print(f"{name} {item_id}: mode {got_mode}, matched {got}; EXPECTED {mode} {matched}")

    def wrong(grid):
        """The grid with its first cell changed."""
        changed = [list(row) for row in grid]
        changed[0][0] = (changed[0][0] + 1) % 10
        return changed

    for item_id, outputs in sorted(keys.items()):
        n = len(outputs)
        first = json.dumps({"test": [{"attempt_1": grid, "attempt_2": wrong(grid)} for grid in outputs]})
        second = json.dumps({"test": [{"attempt_1": wrong(grid), "attempt_2": grid} for grid in outputs]})
        expect("reference-in-attempt-1", item_id, first, [True] * n, "strict")
        expect("reference-in-attempt-2", item_id, second, [True] * n, "strict")
        expect("reference-in-attempt-3-ignored", item_id, json.dumps({"test": [{"attempt_1": wrong(grid), "attempt_2": wrong(grid), "attempt_3": grid}
                                                                                for grid in outputs]}), [False] * n, "strict")
        expect("wrong-grids", item_id, json.dumps({"test": [{"attempt_1": wrong(grid)} for grid in outputs]}), [False] * n, "strict")
        transposed = [[list(column) for column in zip(*grid)] for grid in outputs]
        expect("transposed", item_id, json.dumps({"test": [{"attempt_1": grid} for grid in transposed]}),
               [grid == expected for grid, expected in zip(transposed, outputs)], "strict")
        expect("recovered-from-prose-and-fence", item_id, f"Here is my answer.\n```json\n{first}\n```\n", [True] * n, "recovered")
        expect("null-reply", item_id, "", [False] * n, "unparsed")
        expect("no-object", item_id, "I could not solve it.", [False] * n, "unparsed")
        if n > 1:
            partial = json.dumps({"test": [{"attempt_1": outputs[0]}]})
            expect("only-the-first-test", item_id, partial, [True] + [False] * (n - 1), "strict")
    failed = [name for name, ok in rows if not ok]
    print(f"RESULT: {'PASS' if not failed else 'FAIL'} ({len(rows) - len(failed)}/{len(rows)}) over {len(keys)} tasks")
    return 0 if not failed else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--result")
    parser.add_argument("--self-calibrate", action="store_true")
    args = parser.parse_args()
    if args.self_calibrate:
        raise SystemExit(self_calibrate())
    if not args.request or not args.result:
        parser.error("--request and --result are required")
    grade_request(args.request, args.result)


if __name__ == "__main__":
    main()
