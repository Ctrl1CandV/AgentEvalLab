#!/usr/bin/env python3
"""Grades R3 logic grid answers cell by cell against the private key of the item named in the grader request."""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logic_grid  # noqa: E402

TASK_ID = "r3-logic-grid"
TASK_VERSION = "0.1.0"
GRADER_VERSION = "1.0.0"
KEYS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")

FENCED_BLOCK = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.S | re.I)


def parse_answer(text):
    """Parse the final answer and say how it parsed.

    ("strict", object) when the text is one JSON object, as instructed. ("recovered", object) when exactly one JSON
    object can be found: the only fenced block that holds one, or else the only top-level object in surrounding prose.
    ("unparsed", None) when there is none or several, so the grader never chooses between candidate answers.
    """
    def json_object(value):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    if not isinstance(text, str):
        return "unparsed", None
    answer = json_object(text)
    if answer is not None:
        return "strict", answer
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


def cell_check_id(house, attribute):
    return f"cell-h{house}-a{attribute}"


def cell_requirement_id(house, attribute):
    return f"REQ-H{house}-A{attribute}"


def grade(item_id, mode, answer, keys, active_requirements):
    """Checks for the item's active requirements: one per cell, plus the answer-format check."""
    cells = logic_grid.grade_cells(answer if mode != "unparsed" else None, keys[item_id])
    checks = []
    for (house, attribute), passed in sorted(cells.items()):
        requirement = cell_requirement_id(house, attribute)
        if requirement in active_requirements:
            checks.append({"id": cell_check_id(house, attribute), "requirementId": requirement, "status": "pass" if passed else "fail", "evidenceRefs": []})
    if "REQ-FORMAT" in active_requirements:
        checks.append({"id": "answer-format", "requirementId": "REQ-FORMAT", "status": "pass" if mode == "strict" else "fail", "evidenceRefs": []})
    return checks, cells


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    with open(KEYS_PATH, encoding="utf-8") as handle:
        keys = json.load(handle)
    context = request["context"]
    item_id = context.get("itemId")
    if item_id not in keys:
        raise ValueError("unknown item")
    evidence_root = request["evidenceRoot"]
    try:
        with open(os.path.join(evidence_root, request["answerRef"]), encoding="utf-8") as handle:
            mode, answer = parse_answer(handle.read())
    except (OSError, UnicodeDecodeError, TypeError):
        mode, answer = "unparsed", None
    checks, cells = grade(item_id, mode, answer, keys, set(context["activeRequirementIds"]))
    write_json(os.path.join(evidence_root, "cells.json"), {"itemId": item_id, "parse": mode, "cellsCorrect": sum(cells.values()), "cells": len(cells),
                                                          "wrong": [cell_check_id(house, attribute) for (house, attribute), ok in sorted(cells.items()) if not ok]})
    for check in checks:
        check["evidenceRefs"] = ["cells.json"]
    write_json(result_path, {"schemaVersion": 1, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None})


def self_calibrate():
    """Verify every key and the grader on known answers; no model is involved."""
    with open(KEYS_PATH, encoding="utf-8") as handle:
        keys = json.load(handle)
    rows = []
    for item_id, key in sorted(keys.items()):
        puzzle = logic_grid.puzzle_from(key)
        found = puzzle.solutions(2)
        expected = {(name, value): int(house) - 1 for house, row in key["solution"].items() for name, value in row.items()}
        rows.append((f"{item_id}-unique-solution", len(found) == 1 and found[0] == expected))
        rows.append((f"{item_id}-clues-true", all(logic_grid.holds(clue, expected) for clue in key["clues"])))
        minimal = all(len(logic_grid.Puzzle(key["n"], [(name, values) for name, values in key["attributes"]],
                                            [other for other in key["clues"] if other is not clue]).solutions(2)) == 2 for clue in key["clues"])
        rows.append((f"{item_id}-clues-minimal", minimal))
        active = {cell_requirement_id(h, a) for h in range(1, key["n"] + 1) for a in range(1, len(key["attributes"]) + 1)} | {"REQ-FORMAT"}
        reference = json.dumps({"solution": key["solution"]})
        checks, _ = grade(item_id, *parse_answer(reference), keys, active)
        rows.append((f"{item_id}-key-passes", all(check["status"] == "pass" for check in checks)))
        mode, answer = parse_answer("```json\n" + reference + "\n```")
        checks, _ = grade(item_id, mode, answer, keys, active)
        rows.append((f"{item_id}-fenced-key-recovered", mode == "recovered" and all(c["status"] == "pass" for c in checks if c["id"] != "answer-format")
                     and next(c for c in checks if c["id"] == "answer-format")["status"] == "fail"))
        mode, answer = parse_answer("I reasoned through the clues.\n\n" + reference + "\n")
        checks, _ = grade(item_id, mode, answer, keys, active)
        rows.append((f"{item_id}-prose-key-recovered", mode == "recovered" and all(c["status"] == "pass" for c in checks if c["id"] != "answer-format")))
        swapped = json.loads(reference)
        first_attribute = key["attributes"][0][0]
        swapped["solution"]["1"][first_attribute], swapped["solution"]["2"][first_attribute] = swapped["solution"]["2"][first_attribute], swapped["solution"]["1"][first_attribute]
        checks, _ = grade(item_id, "strict", swapped, keys, active)
        rows.append((f"{item_id}-swap-fails-two-cells", sorted(c["id"] for c in checks if c["status"] == "fail") == ["cell-h1-a1", "cell-h2-a1"]))
        relabelled = {"solution": {house: {name.upper(): value.upper() for name, value in row.items()} for house, row in key["solution"].items()}}
        checks, _ = grade(item_id, "strict", relabelled, keys, active)
        rows.append((f"{item_id}-case-insensitive", all(check["status"] == "pass" for check in checks)))
        checks, _ = grade(item_id, "unparsed", None, keys, active)
        rows.append((f"{item_id}-unparsed-fails", all(check["status"] == "fail" for check in checks)))
    failed = [name for name, ok in rows if not ok]
    for name in failed:
        print(f"{name}: FAIL")
    print(f"RESULT: {'PASS' if not failed else 'FAIL'} ({len(rows) - len(failed)}/{len(rows)})")
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
