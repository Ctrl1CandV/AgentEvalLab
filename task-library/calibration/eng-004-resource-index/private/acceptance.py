#!/usr/bin/env python3
"""Independent, offline acceptance for eng-004; candidate source is run as a CLI."""
import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
HIDDEN = os.path.join(HERE, "hidden_catalog.json")
NODE = shutil.which("node") or "node"
TASK_ID = "eng-004-resource-index"
TASK_VERSION = "0.1.1"
GRADER_VERSION = "1.0.1"
CHECKS = [
    ("search-filter", "REQ-SEARCH"),
    ("default-pagination", "REQ-SEARCH"),
    ("unicode-codepoint-order", "REQ-SEARCH"),
    ("pagination-boundaries", "REQ-SEARCH"),
    ("invalid-pagination", "REQ-INPUT"),
    ("index-compatibility", "REQ-REGRESSION"),
    ("csv-rfc4180", "REQ-CSV"),
]


def hidden_catalog():
    with open(HIDDEN, encoding="utf-8") as handle:
        return json.load(handle)


def run_cli(submission, command, options=(), source=None):
    argv = [NODE, "--experimental-strip-types", "src/cli.ts", command, "--input", "-"]
    argv.extend(options)
    try:
        run = subprocess.run(
            argv,
            cwd=submission,
            input=json.dumps(source, ensure_ascii=False).encode("utf-8") if source is not None else b"{}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=12,
            check=False,
        )
        output = run.stdout
        error = run.stderr
        too_large = len(output) > 200_000 or len(error) > 32_000
        return {
            "exitCode": run.returncode,
            "stdout": output[:200_000],
            "stderr": error[:32_000],
            "tooLarge": too_large,
        }
    except subprocess.TimeoutExpired as exc:
        return {"exitCode": None, "stdout": b"", "stderr": b"", "tooLarge": False, "timeout": True}
    except OSError:
        return {"exitCode": None, "stdout": b"", "stderr": b"", "tooLarge": False, "launchError": True}


def parse_json_run(run):
    if run.get("exitCode") != 0 or run.get("tooLarge"):
        return None
    try:
        return json.loads(run["stdout"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def check_search_filter(submission):
    run = run_cli(submission, "search", ["--query", "  TOrCh  ", "--offset", "0", "--limit", "2"], hidden_catalog())
    value = parse_json_run(run)
    expected = [item for item in sorted(hidden_catalog()["resources"], key=lambda item: item["id"]) if "torch" in item["title"].lower() or any("torch" in tag.lower() for tag in item["tags"])][:2]
    passed = isinstance(value, dict) and value.get("items") == expected and \
        value.get("total") == 3 and value.get("offset") == 0 and value.get("limit") == 2 and value.get("nextOffset") == 2
    return passed, run, "Search must trim and case-fold the title query, sort before paging, and count before paging."


def check_defaults(submission):
    run = run_cli(submission, "search", ["--query", "torch"], hidden_catalog())
    value = parse_json_run(run)
    expected = [item for item in sorted(hidden_catalog()["resources"], key=lambda item: item["id"])
                if "torch" in item["title"].lower() or any("torch" in tag.lower() for tag in item["tags"])]
    passed = isinstance(value, dict) and value.get("items") == expected and value.get("total") == 3 and \
        value.get("offset") == 0 and value.get("limit") == 20 and value.get("nextOffset") is None
    facts = {key: value.get(key) for key in ("total", "offset", "limit", "nextOffset")} if isinstance(value, dict) else {"validJson": False}
    facts["itemIds"] = [item.get("id") for item in value.get("items", [])[:20] if isinstance(item, dict)] if isinstance(value, dict) else []
    return passed, facts, "Default offset and limit must be explicit in the result and return all matches."


def check_unicode_order(submission):
    source = {"resources": [
        {"id": "\U00010000", "title": "Unicode marker", "tags": [], "rank": 2},
        {"id": "\ue000", "title": "Unicode marker", "tags": [], "rank": 1},
    ]}
    value = parse_json_run(run_cli(submission, "search", ["--query", "marker"], source))
    expected_ids = ["\ue000", "\U00010000"]
    passed = isinstance(value, dict) and [item.get("id") for item in value.get("items", [])] == expected_ids and \
        value.get("total") == 2 and value.get("limit") == 20
    facts = {key: value.get(key) for key in ("total", "limit")} if isinstance(value, dict) else {"validJson": False}
    facts["itemIds"] = [item.get("id") for item in value.get("items", [])[:20] if isinstance(item, dict)] if isinstance(value, dict) else []
    return passed, facts, "Search IDs must use Unicode code-point ordering, which differs from UTF-16 code-unit order here."


def check_pagination(submission):
    source = hidden_catalog()
    second = parse_json_run(run_cli(submission, "search", ["--query", "torch", "--offset", "2", "--limit", "2"], source))
    beyond = parse_json_run(run_cli(submission, "search", ["--query", "torch", "--offset", "99", "--limit", "2"], source))
    empty = parse_json_run(run_cli(submission, "search", ["--query", "no-such-resource", "--offset", "0", "--limit", "2"], source))
    passed = isinstance(second, dict) and [item.get("id") for item in second.get("items", [])] == ["r-05"] and \
        second.get("total") == 3 and second.get("nextOffset") is None and \
        isinstance(beyond, dict) and beyond.get("items") == [] and beyond.get("total") == 3 and beyond.get("nextOffset") is None and \
        isinstance(empty, dict) and empty.get("items") == [] and empty.get("total") == 0 and empty.get("nextOffset") is None
    def page_summary(value):
        if not isinstance(value, dict): return {"validJson": False}
        return {"itemIds": [item.get("id") for item in value.get("items", [])[:20] if isinstance(item, dict)],
                "total": value.get("total"), "offset": value.get("offset"), "limit": value.get("limit"),
                "nextOffset": value.get("nextOffset")}
    evidence = {"secondPage": page_summary(second), "beyondEnd": page_summary(beyond), "emptySearch": page_summary(empty)}
    return passed, evidence, "Later, beyond-end, and empty-result pages must preserve total and nextOffset semantics."


def check_invalid(submission):
    source = hidden_catalog()
    invalid = [
        ["--query", "   "],
        ["--query", "torch", "--offset", "-1"],
        ["--query", "torch", "--offset", "0.5"],
        ["--query", "torch", "--limit", "0"],
        ["--query", "torch", "--query", "amber"],
        ["--query", "torch", "--unknown", "x"],
    ]
    runs = [run_cli(submission, "search", options, source) for options in invalid]
    passed = all(run.get("exitCode") not in (0, None) and not run.get("tooLarge") and not run.get("stdout") for run in runs)
    return passed, [{"exitCode": run.get("exitCode"), "stderrSha256": hashlib.sha256(run.get("stderr", b"")).hexdigest()} for run in runs], \
        "Invalid or duplicate pagination/query arguments must fail without a successful JSON response."


def check_index(submission):
    run = run_cli(submission, "index", source=hidden_catalog())
    value = parse_json_run(run)
    expected = sorted(hidden_catalog()["resources"], key=lambda item: item["id"])
    passed = isinstance(value, dict) and value.get("resources") == expected and \
        any(item["id"] == "r-04" and item["rank"] == 0 and item["tags"] == [] for item in value.get("resources", []))
    return passed, run, "Existing index output must remain sorted and preserve empty tags and rank zero."


def crlf_record_endings(text):
    """Require CRLF outside quoted CSV fields while allowing embedded field newlines."""
    if not text.endswith("\r\n"):
        return False
    quoted = False
    field_start = True
    after_quote = False
    index = 0
    while index < len(text):
        character = text[index]
        if quoted:
            if character == '"' and index + 1 < len(text) and text[index + 1] == '"':
                index += 2
                continue
            if character == '"':
                quoted = False
                after_quote = True
            index += 1
            continue
        if after_quote:
            if character == ",":
                after_quote = False
                field_start = True
                index += 1
                continue
            if character == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
                after_quote = False
                field_start = True
                index += 2
                continue
            return False
        if character == '"':
            if not field_start:
                return False
            quoted = True
            field_start = False
        elif character == ",":
            field_start = True
        elif character == "\r":
            if index + 1 >= len(text) or text[index + 1] != "\n":
                return False
            field_start = True
            index += 2
            continue
        elif character == "\n":
            return False
        else:
            field_start = False
        index += 1
    return not quoted and not after_quote


def check_csv(submission):
    run = run_cli(submission, "export", ["--format", "csv"], hidden_catalog())
    raw = run.get("stdout", b"")
    text = ""
    try:
        text = raw.decode("utf-8")
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except (UnicodeDecodeError, csv.Error):
        rows = []
    expected_resources = sorted(hidden_catalog()["resources"], key=lambda item: item["id"])
    expected = [["id", "title", "tags", "rank"]] + [
        [item["id"], item["title"], "|".join(item["tags"]), str(item["rank"])] for item in expected_resources
    ]
    valid_endings = crlf_record_endings(text)
    passed = run.get("exitCode") == 0 and not run.get("tooLarge") and valid_endings and rows == expected
    return passed, {"exitCode": run.get("exitCode"), "rowCount": len(rows), "stdoutSha256": hashlib.sha256(raw).hexdigest(), "crlfRecordEndings": valid_endings}, \
        "CSV must use valid quoting, retain embedded CR/LF and quotes, preserve empty values, and end with CRLF."


def run_checks(submission, evidence_root=None):
    functions = {
        "search-filter": check_search_filter,
        "default-pagination": check_defaults,
        "unicode-codepoint-order": check_unicode_order,
        "pagination-boundaries": check_pagination,
        "invalid-pagination": check_invalid,
        "index-compatibility": check_index,
        "csv-rfc4180": check_csv,
    }
    output = []
    for check_id, requirement_id in CHECKS:
        try:
            passed, facts, reason = functions[check_id](submission)
        except Exception as error:
            passed, facts, reason = False, {"checkerError": type(error).__name__}, "Trusted checker could not complete this check."
        if evidence_root:
            filename = f"{check_id}.json"
            with open(os.path.join(evidence_root, filename), "w", encoding="utf-8") as handle:
                json.dump({"checkId": check_id, "passed": passed, "facts": json_safe(facts), "reason": reason}, handle, ensure_ascii=False, sort_keys=True)
            evidence_refs = [filename]
        else:
            evidence_refs = []
        output.append({"id": check_id, "requirementId": requirement_id, "status": "pass" if passed else "fail", "evidenceRefs": evidence_refs})
    return output


def json_safe(value):
    if isinstance(value, bytes):
        return {"byteLength": len(value), "sha256": hashlib.sha256(value).hexdigest(),
                "preview": value[:256].decode("utf-8", errors="replace")}
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def grader_result(request, checks):
    return {
        "schemaVersion": 1,
        "requestId": request["requestId"],
        "taskId": TASK_ID,
        "taskVersion": TASK_VERSION,
        "graderVersion": GRADER_VERSION,
        "gradingStatus": "completed",
        "checks": checks,
        "dimensions": [],
        "unscoredCheckIds": [],
        "reason": None,
        "error": None,
    }


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    submission = request["submission"]["directory"]
    checks = run_checks(submission, request["evidenceRoot"])
    write_json(result_path, grader_result(request, checks))


def self_calibrate():
    global run_cli
    baseline = os.path.join(PKG, "baseline")
    variants = [os.path.join(HERE, "reference-variants", name) for name in ("ref-a", "ref-b")]
    mutants = [
        ("off-by-one-page", os.path.join(HERE, "mutants", "off-by-one-page")),
        ("bad-csv-quoting", os.path.join(HERE, "mutants", "bad-csv-quoting")),
        ("wrong-next-offset", os.path.join(HERE, "mutants", "wrong-next-offset")),
    ]
    total = 0
    all_ok = True
    csv_ending_cases = [
        ("crlf-records", "id,title\r\nx,ok\r\n", True),
        ("lf-record-with-final-crlf", "id,title\nx,ok\r\n", False),
        ("quoted-field-lf", 'id,title\r\nx,"first\nsecond"\r\n', True),
    ]
    for name, text, expected in csv_ending_cases:
        passed = crlf_record_endings(text) is expected
        all_ok &= passed
        print(f"csv_record_endings_{name}: {'PASS' if passed else 'FAIL'}")
    expected_resources = sorted(hidden_catalog()["resources"], key=lambda item: item["id"])
    expected_rows = [["id", "title", "tags", "rank"]] + [
        [item["id"], item["title"], "|".join(item["tags"]), str(item["rank"])] for item in expected_resources
    ]
    def sample_csv(terminator):
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator=terminator)
        writer.writerows(expected_rows)
        return output.getvalue().encode("utf-8")
    original_run_cli = run_cli
    try:
        run_cli = lambda *_args, **_kwargs: {"exitCode": 0, "stdout": sample_csv("\r\n"), "tooLarge": False}
        valid_csv = check_csv("")[0]
        lf_csv = sample_csv("\n")
        run_cli = lambda *_args, **_kwargs: {"exitCode": 0, "stdout": lf_csv[:-1] + b"\r\n", "tooLarge": False}
        mixed_csv = check_csv("")[0]
    finally:
        run_cli = original_run_cli
    all_ok &= valid_csv and not mixed_csv
    print(f"csv_valid_rfc4180_output: {'PASS' if valid_csv else 'FAIL'}")
    print(f"csv_lf_records_with_final_crlf_rejected: {'PASS' if not mixed_csv else 'FAIL'}")
    with tempfile.TemporaryDirectory(prefix="eng004-calibration-") as temp:
        refs = []
        for label, overlay in zip(("A", "B"), variants):
            target = os.path.join(temp, f"reference-{label}")
            shutil.copytree(baseline, target, ignore=shutil.ignore_patterns(".git"))
            copy_overlay(overlay, target)
            refs.append((label, target))
        for repeat in range(1, 4):
            for label, reference in refs:
                checks = run_checks(reference)
                passed = all(check["status"] == "pass" for check in checks)
                total += 1
                all_ok &= passed
                print(f"reference_{label}_repeat_{repeat}: {sum(check['status'] == 'pass' for check in checks)}/{len(checks)} {'PASS' if passed else 'FAIL'}")
        for name, overlay in mutants:
            target = os.path.join(temp, f"mutant-{name}")
            shutil.copytree(baseline, target, ignore=shutil.ignore_patterns(".git"))
            copy_overlay(os.path.join(HERE, "reference-variants", "ref-a"), target)
            copy_overlay(overlay, target)
            checks = run_checks(target)
            rejected = any(check["status"] == "fail" for check in checks)
            all_ok &= rejected
            print(f"mutant_{name}: {'REJECTED' if rejected else 'UNEXPECTED_PASS'}")
    print(f"RESULT: {'PASS' if all_ok and total == 6 else 'FAIL'} ({total} reference runs, {len(mutants)} targeted mutants, {len(csv_ending_cases)} CSV delimiter cases)")
    return 0 if all_ok and total == 6 else 1


def copy_overlay(source, target):
    for root, dirs, files in os.walk(source):
        rel = os.path.relpath(root, source)
        for directory in dirs:
            os.makedirs(os.path.join(target, rel, directory) if rel != "." else os.path.join(target, directory), exist_ok=True)
        for filename in files:
            source_file = os.path.join(root, filename)
            target_file = os.path.join(target, rel, filename) if rel != "." else os.path.join(target, filename)
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            shutil.copyfile(source_file, target_file)


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
