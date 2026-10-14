#!/usr/bin/env python3
"""Task grader adapter. Automated evidence is scored; human formula review stays unscored."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify  # noqa: E402

TASK_ID = "rsn-002-derivation-check"
TASK_VERSION = "0.4.0"
GRADER_VERSION = "1.1.0"
CHECK_REQUIREMENTS = {
    "sample-values": "REQ-NUMERIC",
    "wrong-step-location": "REQ-LOCALIZATION",
    "dimension-certificate": "REQ-DIMENSIONS",
    "counterexample-certificate": "REQ-COUNTEREXAMPLE",
    "limit-certificate": "REQ-LIMIT",
}
HUMAN_UNSCORED = ["formula-equivalence-review", "explanation-quality-review"]


def load_answer(path):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def grader_checks(answer, evidence_root):
    checks = []
    for check_id, passed, facts in verify.grade(answer):
        filename = check_id + ".json"
        with open(os.path.join(evidence_root, filename), "w", encoding="utf-8") as handle:
            json.dump({"checkId": check_id, "passed": passed, "facts": facts}, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        checks.append({"id": check_id, "requirementId": CHECK_REQUIREMENTS[check_id],
                       "status": "pass" if passed else "fail", "evidenceRefs": [filename]})
    return checks


def format_check(answer, evidence_root=None):
    """Non-critical check that the final answer parsed as one JSON object, so format failures are reported apart from wrong answers."""
    passed = isinstance(answer, dict)
    refs = []
    if evidence_root:
        with open(os.path.join(evidence_root, "answer-format.json"), "w", encoding="utf-8") as handle:
            json.dump({"checkId": "answer-format", "passed": passed}, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        refs.append("answer-format.json")
    return {"id": "answer-format", "requirementId": "REQ-FORMAT", "status": "pass" if passed else "fail", "evidenceRefs": refs}


def make_result(request, checks):
    return {"schemaVersion": 1, "requestId": request["requestId"], "taskId": TASK_ID,
            "taskVersion": TASK_VERSION, "graderVersion": GRADER_VERSION, "gradingStatus": "unscored",
            "checks": checks, "dimensions": [], "unscoredCheckIds": HUMAN_UNSCORED,
            "reason": {"code": "HUMAN_REVIEW_PENDING", "message": "Formula equivalence and explanation quality have not yet been independently scored."},
            "error": None}


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    answer_path = os.path.join(request["evidenceRoot"], request["answerRef"] or "")
    answer = load_answer(answer_path)
    checks = grader_checks(answer, request["evidenceRoot"]) + [format_check(answer, request["evidenceRoot"])]
    write_json(result_path, make_result(request, checks))


def self_calibrate():
    code = verify.self_calibrate()
    format_rows = [("format-check-accepts-object", format_check({"errorStepId": "S1"})["status"] == "pass"),
                   ("format-check-rejects-unparsed", format_check(None)["status"] == "fail")]
    for name, passed in format_rows:
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    if code == 0 and all(passed for _, passed in format_rows):
        print("grader-protocol: PASS (5 automated check IDs and 1 answer-format check returned; 2 human check IDs explicitly unscored)")
        return 0
    return code or 1


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
