#!/usr/bin/env python3
"""Versioned task-package adapter for rsn-001; accepts any valid witness."""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import verify  # noqa: E402

TASK_ID = "rsn-001-shift-scheduling"
TASK_VERSION = "0.2.1"
GRADER_VERSION = "1.0.1"
CHECKS = [("A", "REQ-A"), ("B", "REQ-B"), ("C", "REQ-C")]


def load_answer(path):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def grade(answer, evidence_root=None):
    checks = []
    for instance_id, requirement_id in CHECKS:
        passed, reason = verify.grade(instance_id, answer.get(instance_id, {}) if answer else {})
        evidence = {"instanceId": instance_id, "passed": passed, "reasonCode": "VALID_RESPONSE" if passed else "INVALID_OR_UNSUPPORTED_RESPONSE"}
        refs = []
        if evidence_root:
            name = f"{instance_id}.json"
            with open(os.path.join(evidence_root, name), "w", encoding="utf-8") as handle:
                json.dump(evidence, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
            refs.append(name)
        checks.append({"id": f"instance-{instance_id}", "requirementId": requirement_id, "status": "pass" if passed else "fail", "evidenceRefs": refs})
    return checks


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def grader_result(request, checks):
    return {"schemaVersion": 1, "requestId": request["requestId"], "taskId": TASK_ID,
            "taskVersion": TASK_VERSION, "graderVersion": GRADER_VERSION, "gradingStatus": "completed",
            "checks": checks, "dimensions": [], "unscoredCheckIds": [], "reason": None, "error": None}


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    answer_path = os.path.join(request["evidenceRoot"], request["answerRef"] or "")
    checks = grade(load_answer(answer_path), request["evidenceRoot"])
    write_json(result_path, grader_result(request, checks))


def self_calibrate():
    oracle = verify._load("private/oracle.json")
    negatives = verify._load("private/negatives.json")
    ref = oracle["reference_answers"]
    alternative = {
        "A": {"feasible": False, "conflict_set": ["availability", "per_person_max", "coverage"]},
        "B": {"gap": "daily_need", "branches": {"1": {"feasible": True}, "2": {"feasible": False}}},
        "C": {"feasible": True, "schedule": {"0": ["Carol"], "1": ["Alice"], "2": ["Bob"], "3": ["Carol"], "4": ["Alice"]}},
    }
    rows = []
    rows.append(("oracle", all(c["status"] == "pass" for c in grade(ref))))
    rows.append(("alternative-legal-answer", all(c["status"] == "pass" for c in grade(alternative))))
    valid_clarification = dict(ref, B={"gap": "daily_need", "clarify": True, "clarificationTarget": "daily_need",
                                      "question": "How many people need to be scheduled each day?"})
    irrelevant_clarification = dict(ref, B={"gap": "daily_need", "clarify": True, "clarificationTarget": "favorite_color",
                                            "question": "What is your favorite color?"})
    rows.append(("clarification-target-accepted", next(c["status"] for c in grade(valid_clarification) if c["id"] == "instance-B") == "pass"))
    rows.append(("unrelated-clarification-target-rejected", next(c["status"] for c in grade(irrelevant_clarification) if c["id"] == "instance-B") == "fail"))
    for instance_id, cases in negatives.items():
        for item in cases:
            answer = {instance_id: item["answer"]}
            got = next(c["status"] for c in grade(answer) if c["id"] == f"instance-{instance_id}")
            rows.append((f"negative-{instance_id}-{item['name']}", got == "fail"))
    rows.append(("malformed-json-value", all(c["status"] == "fail" for c in grade(None))))
    rows.append(("deterministic-repeat", grade(ref) == grade(ref)))
    for name, passed in rows:
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    print(f"RESULT: {'PASS' if all(ok for _, ok in rows) else 'FAIL'} ({sum(ok for _, ok in rows)}/{len(rows)})")
    return 0 if all(ok for _, ok in rows) else 1


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
