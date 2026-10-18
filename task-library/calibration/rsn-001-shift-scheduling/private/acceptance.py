#!/usr/bin/env python3
"""Versioned task-package adapter for rsn-001; accepts any valid witness."""
import argparse
import hashlib
import json
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import verify  # noqa: E402

TASK_ID = "rsn-001-shift-scheduling"
TASK_VERSION = "0.5.1"
GRADER_VERSION = "1.2.1"
CHECKS = [("A", "REQ-A"), ("B", "REQ-B"), ("C", "REQ-C")]


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


def load_answer(path):
    """Read and parse the final answer file; returns (mode, answer) as parse_answer does."""
    try:
        with open(path, encoding="utf-8") as handle:
            return parse_answer(handle.read())
    except (OSError, UnicodeDecodeError):
        return "unparsed", None


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


def format_check(mode, evidence_root=None):
    """Non-critical check that the answer followed the instructed format exactly. A recovered answer is still graded
    on its content and fails only this check; the harness applies the manifest's format penalty to the trial score."""
    passed = mode == "strict"
    refs = []
    if evidence_root:
        with open(os.path.join(evidence_root, "answer-format.json"), "w", encoding="utf-8") as handle:
            json.dump({"checkId": "answer-format", "passed": passed, "parse": mode}, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        refs.append("answer-format.json")
    return {"id": "answer-format", "requirementId": "REQ-FORMAT", "status": "pass" if passed else "fail", "evidenceRefs": refs}


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
    mode, answer = load_answer(answer_path)
    checks = grade(answer, request["evidenceRoot"]) + [format_check(mode, request["evidenceRoot"])]
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
    reference_text = json.dumps(ref)
    reference_object = json.loads(reference_text)
    format_rows = [
        ("parse-strict-object", parse_answer(reference_text) == ("strict", reference_object)),
        ("parse-recovers-one-json-fence", parse_answer("```json\n" + reference_text + "\n```\n") == ("recovered", reference_object)),
        ("parse-recovers-one-unlabelled-fence", parse_answer("```\n" + reference_text + "\n```") == ("recovered", reference_object)),
        ("parse-recovers-prose-around-one-fence", parse_answer("Answer:\n```json\n" + reference_text + "\n```\nDone.") == ("recovered", reference_object)),
        ("parse-recovers-prose-around-one-object", parse_answer("I solved it as follows.\n\n" + reference_text + "\n") == ("recovered", reference_object)),
        ("parse-rejects-two-fenced-objects", parse_answer("```json\n{\"draft\": 1}\n```\n```json\n" + reference_text + "\n```")[0] == "unparsed"),
        ("parse-rejects-two-bare-objects", parse_answer("Draft: {\"draft\": 1}\nFinal: " + reference_text)[0] == "unparsed"),
        ("parse-rejects-no-object", parse_answer("I could not solve it.")[0] == "unparsed"),
        ("format-check-accepts-strict", format_check("strict")["status"] == "pass"),
        ("format-check-fails-recovered", format_check("recovered")["status"] == "fail"),
        ("format-check-rejects-unparsed", format_check("unparsed")["status"] == "fail"),
    ]
    rows.extend(format_rows)
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
