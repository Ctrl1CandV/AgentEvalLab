#!/usr/bin/env python3
"""Task grader adapter. Automated evidence is scored; human formula review stays unscored."""
import argparse
import json
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify  # noqa: E402

TASK_ID = "rsn-002-derivation-check"
TASK_VERSION = "0.5.1"
GRADER_VERSION = "1.2.1"
CHECK_REQUIREMENTS = {
    "sample-values": "REQ-NUMERIC",
    "wrong-step-location": "REQ-LOCALIZATION",
    "dimension-certificate": "REQ-DIMENSIONS",
    "counterexample-certificate": "REQ-COUNTEREXAMPLE",
    "limit-certificate": "REQ-LIMIT",
}
HUMAN_UNSCORED = ["formula-equivalence-review", "explanation-quality-review"]


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
    mode, answer = load_answer(answer_path)
    checks = grader_checks(answer, request["evidenceRoot"]) + [format_check(mode, request["evidenceRoot"])]
    write_json(result_path, make_result(request, checks))


def self_calibrate():
    code = verify.self_calibrate()
    reference_text = json.dumps({"errorStepId": "S1"})
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
