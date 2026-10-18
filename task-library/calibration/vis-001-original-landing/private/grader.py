#!/usr/bin/env python3
"""Grades vis-001 submissions with the browser-free structure, copy, form and palette-contrast checks.

Visual quality is not graded here: a separate judging step renders the submission and compares it with anchor
designs (PLAN-005 WP6, private/judge/SKILL.md).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_frontend  # noqa: E402

TASK_ID = "vis-001-original-landing"
TASK_VERSION = "0.3.0"
GRADER_VERSION = "1.0.0"
CHECKS = [("semantic structure and roles", "roles", "REQ-ROLES"), ("at least three features", "features", "REQ-FEATURES"),
          ("all fixed copy present", "copy", "REQ-COPY"), ("form fields and label associations", "form", "REQ-FORM"),
          ("form states (empty/error/success)", "states", "REQ-STATES"), ("contrast (WCAG 2.2)", "contrast", "REQ-CONTRAST")]


def grade(directory):
    """{check id: (passed, detail)}; a submission without index.html fails every check."""
    if not os.path.isfile(os.path.join(directory, "index.html")):
        return {check: (False, "index.html missing") for _, check, _ in CHECKS}
    try:
        results = verify_frontend.check(directory)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return {check: (False, f"unreadable submission: {type(error).__name__}") for _, check, _ in CHECKS}
    return {check: results[name] for name, check, _ in CHECKS}


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    results = grade(request["submission"]["directory"])
    write_json(os.path.join(request["evidenceRoot"], "checks.json"), {check: {"passed": passed, "detail": detail} for check, (passed, detail) in results.items()})
    active = set(request["context"]["activeRequirementIds"])
    checks = [{"id": check, "requirementId": requirement, "status": "pass" if results[check][0] else "fail", "evidenceRefs": ["checks.json"]}
              for _, check, requirement in CHECKS if requirement in active]
    write_json(result_path, {"schemaVersion": 1, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None})


def self_calibrate():
    code = verify_frontend.self_calibrate()
    rows = [("verify-frontend-self-calibration", code == 0),
            ("reference-passes-every-check", all(passed for passed, _ in grade(verify_frontend.REF).values())),
            ("missing-index-fails-every-check", not any(passed for passed, _ in grade(os.path.dirname(verify_frontend.REF) + "/judge").values()))]
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
