#!/usr/bin/env python3
"""Grades E2 submissions: runs the candidate's program on each hidden fixture of the item, inside the sandbox
launcher when the request provides one, and compares its JSON output with the expected output.

Fixtures are grouped into checks; a check passes when every fixture in it passes. The score is the fraction of
checks passed, so a partly correct implementation gets partial credit.
"""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TASK_ID = "e2-spec-implementation"
TASK_VERSION = "0.4.0"
GRADER_VERSION = "1.4.0"
# Per item: the file the candidate delivers, the module holding its hidden fixtures, and how a fixture becomes the
# program's input. Sheet output is compared cell by cell with numeric tolerance; the others must match exactly.
ITEMS = {
    "sheet": {"entry": "sheet.py", "fixtures": os.path.join(HERE, "sheet", "fixtures.py"), "input": lambda cells: {"cells": cells}, "cells": True},
    "ledger": {"entry": "ledger.py", "fixtures": os.path.join(HERE, "ledger", "fixtures.py"), "input": lambda data: data, "cells": False},
    "recur": {"entry": "recur.py", "fixtures": os.path.join(HERE, "recur", "fixtures.py"), "input": lambda data: data, "cells": False},
    "query": {"entry": "query.py", "fixtures": os.path.join(HERE, "query", "fixtures.py"), "input": lambda data: data, "cells": False},
}
FIXTURE_TIMEOUT_SECONDS = 10
MAX_OUTPUT_BYTES = 1_000_000


def load_fixtures(item_id):
    spec = importlib.util.spec_from_file_location(f"{item_id}_fixtures", ITEMS[item_id]["fixtures"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FIXTURES


# Checks that test number formatting itself. Only they compare numbers strictly, so a formatting slip costs these
# checks and not every check that happens to output a number.
STRICT_CHECKS = {"rounding", "number-format"}


def same(actual, expected, strict=False):
    """Booleans must match exactly. Numbers match within 1e-9 in general. In strict checks an integral expected value
    must be a JSON integer and other numbers must match within 1e-12, as the output rule (9 decimal places) requires."""
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    if strict and type(expected) is int:
        return type(actual) is int and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(actual - expected) < (1e-12 if strict else 1e-9)
    return actual == expected


def identical(actual, expected):
    """Exact JSON equality: types must match, so 1 is not true and "1" is not 1."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(identical(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(identical(a, e) for a, e in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def run_fixture(program, data, launcher):
    """Run the candidate on one input in a fresh directory; returns (output dict or None, reason)."""
    directory = tempfile.mkdtemp(prefix="e2-fixture-")
    try:
        shutil.copy(program, os.path.join(directory, os.path.basename(program)))
        with open(os.path.join(directory, "input.json"), "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        command = ["python3", os.path.basename(program), "input.json"]
        if launcher:
            command = [sys.executable, launcher, "--rw", directory, "--", *command]
        try:
            run = subprocess.run(command, cwd=directory, stdin=subprocess.DEVNULL, capture_output=True, timeout=FIXTURE_TIMEOUT_SECONDS,
                                 env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8"})
        except subprocess.TimeoutExpired:
            return None, "timeout"
        if run.returncode != 0:
            return None, f"exit {run.returncode}"
        if len(run.stdout) > MAX_OUTPUT_BYTES:
            return None, "output too large"
        try:
            output = json.loads(run.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "output is not JSON"
        return (output, "ok") if isinstance(output, dict) else (None, "output is not an object")
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def grade(item_id, submission, launcher):
    """{check: {"passed": bool, "fixtures": {fixture: reason}}}; a missing program fails every check."""
    program = os.path.join(submission, ITEMS[item_id]["entry"])
    results = {}
    item = ITEMS[item_id]
    for check, fixture, data, expected in load_fixtures(item_id):
        entry = results.setdefault(check, {"passed": True, "fixtures": {}})
        if not os.path.isfile(program):
            reason = f"{item['entry']} missing"
        else:
            output, reason = run_fixture(program, item["input"](data), launcher)
            if output is not None and item["cells"]:
                wrong = sorted(name for name, value in expected.items() if name not in output or not same(output[name], value, check in STRICT_CHECKS))
                reason = "ok" if not wrong and set(output) == set(expected) else f"wrong cells {wrong[:8]}" if wrong else "unexpected keys"
            elif output is not None:
                wrong = sorted(name for name in set(expected) | set(output) if name not in output or name not in expected
                               or not identical(output[name], expected[name]))
                reason = "ok" if not wrong else f"wrong keys {wrong[:8]}"
        entry["fixtures"][fixture] = reason
        entry["passed"] = entry["passed"] and reason == "ok"
    results["readme"] = {"passed": os.path.isfile(os.path.join(submission, "README.md")), "fixtures": {}}
    return results


def check_id(item_id, check):
    return "readme" if check == "readme" else f"{item_id}-{check}"


def requirement_id(item_id, check):
    return "REQ-README" if check == "readme" else f"REQ-{item_id.upper()}-{check.upper()}"


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=1)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    item_id = request["context"].get("itemId")
    if item_id not in ITEMS:
        raise ValueError("unknown item")
    launcher = (request.get("sandbox") or {}).get("launcher")
    results = grade(item_id, request["submission"]["directory"], launcher)
    write_json(os.path.join(request["evidenceRoot"], "fixtures.json"), results)
    active = set(request["context"]["activeRequirementIds"])
    checks = [{"id": check_id(item_id, check), "requirementId": requirement_id(item_id, check), "status": "pass" if result["passed"] else "fail",
               "evidenceRefs": ["fixtures.json"]} for check, result in sorted(results.items()) if requirement_id(item_id, check) in active]
    write_json(result_path, {"schemaVersion": 1, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None})


def self_calibrate():
    """The reference passes every check of every item; every mutant fails the check it targets. No model is involved."""
    sys.path.insert(0, HERE)
    import mutants  # noqa: E402
    rows = []
    for item_id in ITEMS:
        reference = os.path.join(HERE, item_id, "reference.py")
        with tempfile.TemporaryDirectory(prefix="e2-calibration-") as submission:
            shutil.copy(reference, os.path.join(submission, ITEMS[item_id]["entry"]))
            with open(os.path.join(submission, "README.md"), "w", encoding="utf-8") as handle:
                handle.write("Reference.\n")
            results = grade(item_id, submission, None)
            rows.append((f"{item_id}-reference-passes-all", all(result["passed"] for result in results.values())))
            for name, target, source in mutants.mutants(item_id, reference):
                with open(os.path.join(submission, ITEMS[item_id]["entry"]), "w", encoding="utf-8") as handle:
                    handle.write(source)
                results = grade(item_id, submission, None)
                failed = sorted(check for check, result in results.items() if not result["passed"])
                passed_share = sum(result["passed"] for result in results.values()) / len(results)
                print(f"{item_id} mutant {name}: fails {failed} ({passed_share:.0%} of checks pass)")
                rows.append((f"{item_id}-mutant-{name}-fails-{target}", target in failed))
        with tempfile.TemporaryDirectory(prefix="e2-calibration-") as empty:
            rows.append((f"{item_id}-missing-program-fails-all", not any(result["passed"] for check, result in grade(item_id, empty, None).items())))
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
