#!/usr/bin/env python3
"""Private acceptance checker for the CSV import validator."""
import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)


def _find_python_launcher():
    # LibreOffice embeds Python with sys.executable set to its runtime directory;
    # its supported launcher sits beside that directory.
    if os.path.isfile(sys.executable):
        return sys.executable
    adjacent = os.path.join(os.path.dirname(sys.executable), "python.exe")
    if os.path.isfile(adjacent):
        return adjacent
    for name in ("python3.13", "python"):
        candidate = shutil.which(name)
        if candidate:
            return candidate
    return sys.executable


PY = _find_python_launcher()
SANDBOX_LAUNCHER = None  # set from the grader request by run_harness_protocol
ORACLE = json.load(open(os.path.join(HERE, "oracle.json"), encoding="utf-8"))
DEFAULT_SCHEMA = os.path.join(PKG, "public", "schema.json")
TASK_ID = "eng-001-import-validator"
TASK_VERSION = "0.3.2"
GRADER_ID = "eng001-acceptance"
GRADER_VERSION = "1.2.0"
MAX_CANDIDATE_OUTPUT = 200_000
CANDIDATE_TIMEOUT_SECONDS = 5
ROW_ERROR_CODES = {"missing_required", "type_mismatch", "constraint", "unique_violation"}
FATAL_ERROR_CODES = {"usage", "schema_error", "empty_input", "header_mismatch", "duplicate_header", "parse_error", "db_error"}
SQLITE_TYPES = {"int": "INTEGER", "float": "REAL", "str": "TEXT", "bool": "INTEGER", "date": "TEXT"}


def _abs(rel):
    return rel if os.path.isabs(rel) else os.path.join(PKG, rel)


def _minimal_candidate_env():
    """Keep system paths needed to start Python, but do not inherit API/config secrets."""
    names = ("PATH", "Path", "PATHEXT", "SystemRoot", "WINDIR", "TEMP", "TMP",
             "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA")
    env = {name: os.environ[name] for name in names if os.environ.get(name)}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _sandboxed(cmd, cwd):
    """Prefix candidate commands with the harness sandbox launcher when the request supplies one."""
    if not SANDBOX_LAUNCHER:
        return cmd
    return [sys.executable, SANDBOX_LAUNCHER, "--rw", str(cwd), "--", *cmd]


def _run_bounded(cmd, cwd, timeout_seconds=CANDIDATE_TIMEOUT_SECONDS,
                 max_output=MAX_CANDIDATE_OUTPUT):
    """Run an untrusted candidate with a deadline and a combined stdout/stderr cap."""
    try:
        proc = subprocess.Popen(_sandboxed(cmd, cwd), cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=_minimal_candidate_env(), shell=False,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return {"returncode": None, "stdout": b"", "stderr": b"", "status": "spawn_error"}

    stdout, stderr = bytearray(), bytearray()
    byte_count = [0]
    lock = threading.Lock()
    output_limit = threading.Event()

    def drain(stream, destination):
        while True:
            chunk = stream.read(4096)
            if not chunk:
                return
            with lock:
                remaining = max(0, max_output - len(stdout) - len(stderr))
                if remaining:
                    destination.extend(chunk[:remaining])
                byte_count[0] += len(chunk)
                if byte_count[0] > max_output:
                    output_limit.set()

    readers = [threading.Thread(target=drain, args=(proc.stdout, stdout), daemon=True),
               threading.Thread(target=drain, args=(proc.stderr, stderr), daemon=True)]
    for reader in readers:
        reader.start()

    status = "completed"
    deadline = time.monotonic() + timeout_seconds
    while proc.poll() is None:
        if output_limit.is_set():
            status = "output_limit"
            proc.kill()
            break
        if time.monotonic() >= deadline:
            status = "timeout"
            proc.kill()
            break
        time.sleep(0.02)
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    for reader in readers:
        reader.join(timeout=1)
    for stream in (proc.stdout, proc.stderr):
        if stream:
            stream.close()
    if output_limit.is_set() and status == "completed":
        status = "output_limit"
    return {"returncode": proc.returncode, "stdout": bytes(stdout),
            "stderr": bytes(stderr), "status": status}


def run_impl(impl, case, tmpdir, preserve_db=False):
    candidate_dir = os.path.join(tmpdir, "candidate")
    os.makedirs(candidate_dir, exist_ok=True)
    candidate_script = os.path.join(candidate_dir, "import_validator.py")
    candidate_source = _abs(impl)
    if not os.path.isfile(candidate_source) or os.path.islink(candidate_source):
        return {"returncode": None, "stdout": b"", "stderr": b"", "status": "missing_candidate",
                "db_path": None}
    shutil.copyfile(candidate_source, candidate_script)

    # Stage one generic copy of each input beside the candidate. Never pass a
    # private fixture or package path in argv, cwd, or the candidate directory.
    schema_path = os.path.join(candidate_dir, "schema.json")
    input_path = os.path.join(candidate_dir, "input.csv")
    shutil.copyfile(_abs(case.get("schema", "public/schema.json")), schema_path)
    shutil.copyfile(_abs(case["input"]), input_path)
    cmd = [PY, candidate_script, "--schema", schema_path, "--input", input_path]
    db_path = None
    if case.get("db"):
        db_path = os.path.join(candidate_dir, case["db"])
        if not preserve_db and os.path.exists(db_path):
            os.remove(db_path)
        cmd += ["--db", db_path]
    cmd += ["--dry-run" if case["mode"] == "dry-run" else "--apply"]
    if case.get("encoding"):
        cmd += ["--encoding", case["encoding"]]
    result = _run_bounded(cmd, candidate_dir)
    result["db_path"] = db_path
    return result


def parse_candidate_output(stdout):
    """Accept only the documented JSONL protocol; ignore no lines or fields."""
    try:
        text = stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    lines = text.splitlines()
    if not lines or any(not line.strip() for line in lines):
        return None
    def object_without_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        parsed = [json.loads(line, object_pairs_hook=object_without_duplicate_keys) for line in lines]
    except (json.JSONDecodeError, ValueError):
        return None
    errors, summary, top = [], None, None
    for index, value in enumerate(parsed):
        if not isinstance(value, dict):
            return None
        if set(value) == {"record", "line", "field", "code", "value"}:
            if (isinstance(value["record"], bool) or not isinstance(value["record"], int) or value["record"] < 0 or
                    isinstance(value["line"], bool) or not isinstance(value["line"], int) or value["line"] < 1 or
                    not isinstance(value["field"], str) or not isinstance(value["code"], str) or value["code"] not in ROW_ERROR_CODES or
                    (value["value"] is not None and not isinstance(value["value"], str)) or summary is not None or top is not None):
                return None
            errors.append(value)
        elif set(value) == {"summary"}:
            if summary is not None or top is not None or index != len(parsed) - 1:
                return None
            data = value["summary"]
            if (not isinstance(data, dict) or set(data) != {"ok", "records", "errors", "by_code"} or
                    not isinstance(data["ok"], bool) or
                    any(isinstance(data[name], bool) or not isinstance(data[name], int) or data[name] < 0
                        for name in ("records", "errors")) or not isinstance(data["by_code"], dict) or
                    any(not isinstance(code, str) or code not in ROW_ERROR_CODES or
                        isinstance(count, bool) or not isinstance(count, int) or count < 0
                        for code, count in data["by_code"].items())):
                return None
            # The instruction gives by_code as {<code>: <int>} without saying whether codes that did not occur are
            # listed, so a zero count is read as an absent code.
            summary = dict(data, by_code={code: count for code, count in data["by_code"].items() if count})
        elif set(value) == {"error"}:
            if len(parsed) != 1:
                return None
            data = value["error"]
            if (not isinstance(data, dict) or set(data) != {"code", "message"} or
                    not isinstance(data["code"], str) or data["code"] not in FATAL_ERROR_CODES or
                    not isinstance(data["message"], str)):
                return None
            top = data
        else:
            return None
    if top is None and summary is None:
        return None
    return {"errors": errors, "summary": summary, "top": top}


def _read_csv_rows(case):
    path = _abs(case["input"])
    encoding = case.get("encoding", "utf-8")
    with open(path, encoding=encoding, newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        indexes = {name: index for index, name in enumerate(header)}
        rows = []
        for row in reader:
            rows.append((reader.line_num, row))
    return indexes, rows


def _expected_error_rows(case, expected_triples):
    schema_path = _abs(case.get("schema", "public/schema.json"))
    json.load(open(schema_path, encoding="utf-8"))  # Ensure the schema fixture is readable.
    indexes, rows = _read_csv_rows(case)
    expected = []
    for record, field, code in expected_triples:
        if record < 0 or record >= len(rows) or field not in indexes:
            return None
        physical_line, cells = rows[record]
        if indexes[field] >= len(cells):
            return None
        expected.append({"record": record, "line": physical_line, "field": field,
                         "code": code, "value": cells[indexes[field]]})
    return sorted(expected, key=lambda error: (error["record"], error["field"]))


def _coerce_expected(column, raw):
    value = raw.strip()
    if value == "":
        return None
    kind = column["type"]
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "bool":
        return 1 if value.lower() in ("true", "1") else 0
    if kind == "date":
        return value
    return raw


def _expected_typed_rows(input_path, schema):
    with open(input_path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [tuple(_coerce_expected(column, row[column["name"]] or "") for column in schema["columns"])
                for row in reader]
    primary_index = next(index for index, column in enumerate(schema["columns"])
                         if column["name"] == schema["primary_key"])
    return sorted(rows, key=lambda row: row[primary_index])


def db_state(db_path, schema, expected_rows=None):
    """Check declared SQLite schema, uniqueness, and every row without returning row data."""
    if not db_path or not os.path.exists(db_path):
        return {"exists": False, "valid": False}
    if not os.path.isfile(db_path) or os.path.islink(db_path):
        return {"exists": True, "valid": False}
    try:
        uri = "file:" + db_path.replace("\\", "/") + "?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        con.row_factory = sqlite3.Row
        try:
            cur = con.cursor()
            info = cur.execute("PRAGMA table_info(records)").fetchall()
            if len(info) != len(schema["columns"]):
                return {"exists": True, "valid": False}
            primary = schema["primary_key"]
            expected_columns = [(column["name"], SQLITE_TYPES[column["type"]], 1 if column["name"] == primary else 0)
                                for column in schema["columns"]]
            actual_columns = [(row["name"], str(row["type"]).upper(), int(row["pk"])) for row in info]
            if actual_columns != expected_columns:
                return {"exists": True, "valid": False}

            expected_unique = sorted([[column["name"]] for column in schema["columns"]
                                      if column.get("unique") and column["name"] != primary])
            actual_unique = []
            for index in cur.execute("PRAGMA index_list(records)").fetchall():
                if index["unique"] and index["origin"] != "pk":
                    index_name = index["name"].replace("'", "''")
                    columns = [row["name"] for row in cur.execute(
                        "PRAGMA index_info('" + index_name + "')").fetchall()]
                    actual_unique.append(columns)
            if sorted(actual_unique) != expected_unique:
                return {"exists": True, "valid": False}

            names = [column["name"] for column in schema["columns"]]
            quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in names)
            primary_quoted = '"' + primary.replace('"', '""') + '"'
            actual_rows = cur.execute("SELECT " + quoted + " FROM records ORDER BY " + primary_quoted).fetchall()
            actual_rows = [tuple(row) for row in actual_rows]
            rows_match = expected_rows is None or actual_rows == expected_rows
            return {"exists": True, "valid": rows_match}
        finally:
            con.close()
    except (sqlite3.Error, OSError, ValueError):
        return {"exists": True, "valid": False}


def check_case(impl, cid, case):
    tmp = tempfile.mkdtemp(prefix="eng001_")
    try:
        run = run_impl(impl, case, tmp)
        if run["status"] != "completed":
            reason = {"timeout": "candidate_timeout", "output_limit": "candidate_output_limit",
                      "missing_candidate": "candidate_missing"}
            return False, reason.get(run["status"], "candidate_start_error")
        output = parse_candidate_output(run["stdout"])
        if output is None:
            return False, "output_protocol_invalid"
        exp = case["expect"]
        if run["returncode"] != exp["exit"]:
            return False, "exit_code_mismatch"
        if "top_code" in exp:
            if output["top"] is None or output["top"]["code"] != exp["top_code"]:
                return False, "fatal_error_mismatch"
        else:
            if output["top"] is not None or output["summary"] is None:
                return False, "summary_missing_or_unexpected"
            expected_errors = _expected_error_rows(case, exp["errors"])
            if expected_errors is None or output["errors"] != expected_errors:
                return False, "record_errors_mismatch"
            summary = output["summary"]
            expected_by_code = dict(Counter(error["code"] for error in expected_errors))
            expected_records = len(_read_csv_rows(case)[1])
            if (summary["records"] != expected_records or summary["errors"] != len(expected_errors) or
                    summary["ok"] != (not expected_errors) or summary["by_code"] != expected_by_code):
                return False, "summary_values_mismatch"
            if "errors_line" in exp and [error["line"] for error in expected_errors] != exp["errors_line"]:
                return False, "oracle_line_expectation_mismatch"

        if "db" in exp:
            want_db = exp["db"]
            exists = bool(run["db_path"] and os.path.exists(run["db_path"]))
            if exists != want_db["exists"]:
                return False, "database_presence_mismatch"
            if exists:
                schema = json.load(open(_abs(case.get("schema", "public/schema.json")), encoding="utf-8"))
                expected_rows = _expected_typed_rows(_abs(case["input"]), schema) if not output["errors"] else []
                if not db_state(run["db_path"], schema, expected_rows)["valid"]:
                    return False, "database_schema_or_rows_mismatch"
        return True, "ok"
    except (OSError, ValueError, KeyError, StopIteration, csv.Error, json.JSONDecodeError):
        return False, "grader_fixture_or_candidate_error"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_idempotency(impl):
    spec = ORACLE["idempotency"]
    tmp = tempfile.mkdtemp(prefix="eng001_idem_")
    try:
        db_path = os.path.join(tmp, "candidate", spec["db"])
        case = {"input": spec["input"], "mode": "apply", "db": os.path.basename(db_path)}
        schema = json.load(open(DEFAULT_SCHEMA, encoding="utf-8"))
        expected_rows = _expected_typed_rows(_abs(spec["input"]), schema)
        expected_record_count = len(_read_csv_rows({"input": spec["input"]})[1])
        for _ in range(2):
            run = run_impl(impl, case, tmp, preserve_db=True)
            if run["status"] != "completed":
                reason = {"timeout": "candidate_timeout", "output_limit": "candidate_output_limit",
                          "missing_candidate": "candidate_missing"}
                return False, reason.get(run["status"], "candidate_start_error")
            output = parse_candidate_output(run["stdout"])
            if (run["returncode"] != spec["apply_twice_expect"]["exit"] or output is None or
                    output["top"] is not None or output["errors"] or output["summary"] is None or
                    output["summary"]["records"] != expected_record_count or
                    output["summary"]["errors"] != 0 or output["summary"]["by_code"] != {} or
                    not output["summary"]["ok"]):
                return False, "idempotency_output_mismatch"
            state = db_state(db_path, schema, expected_rows)
            if not state["exists"] or not state["valid"]:
                return False, "idempotency_database_mismatch"
        return True, "ok"
    except (OSError, ValueError, KeyError, StopIteration, csv.Error, json.JSONDecodeError):
        return False, "grader_fixture_or_candidate_error"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_suite(impl):
    res = {}
    for cid, case in ORACLE["cases"].items():
        res[cid] = check_case(impl, cid, case)
    res["idempotency"] = check_idempotency(impl)
    return res


def _grader_result(request_id, status="error", error_code="GRADER_INTERNAL_ERROR",
                   phase="grading", checks=None):
    return {
        "schemaVersion": 1,
        "requestId": request_id,
        "taskId": TASK_ID,
        "taskVersion": TASK_VERSION,
        "graderVersion": GRADER_VERSION,
        "gradingStatus": status,
        "checks": checks or [],
        "dimensions": [],
        "unscoredCheckIds": [],
        "reason": None,
        "error": None if status == "completed" else {"code": error_code, "phase": phase},
    }


def _is_inside(path, parent):
    try:
        return os.path.commonpath([os.path.normcase(path), os.path.normcase(parent)]) == os.path.normcase(parent)
    except ValueError:
        return False


def _validate_grader_request(request):
    required = {"schemaVersion", "requestId", "trialId", "task", "submission", "answerRef",
                "traceRef", "context", "evidenceRoot", "sandbox"}
    if not isinstance(request, dict) or set(request) != required or request["schemaVersion"] != 1:
        return None
    request_id = request["requestId"]
    task = request["task"]
    submission = request["submission"]
    context = request["context"]
    if (not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", request_id) or
            not isinstance(request["trialId"], str) or not isinstance(task, dict) or
            set(task) != {"id", "version", "manifestSha256"} or task["id"] != TASK_ID or
            task["version"] != TASK_VERSION or not isinstance(task["manifestSha256"], str) or
            not re.fullmatch(r"[a-f0-9]{64}", task["manifestSha256"]) or
            not isinstance(submission, dict) or
            set(submission) != {"snapshotId", "directory", "manifestSha256"} or
            not isinstance(submission["snapshotId"], str) or
            not isinstance(submission["directory"], str) or not os.path.isabs(submission["directory"]) or
            not isinstance(submission["manifestSha256"], str) or
            not re.fullmatch(r"[a-f0-9]{64}", submission["manifestSha256"]) or
            request["answerRef"] is not None or request["traceRef"] is not None or
            not isinstance(context, dict) or set(context) != {"stageId", "cycleId", "activeRequirementIds"} or
            context["stageId"] is not None or context["cycleId"] is not None or
            context["activeRequirementIds"] != ["REQ-IMPLEMENTATION"] or
            not isinstance(request["evidenceRoot"], str) or not os.path.isabs(request["evidenceRoot"])):
        return None

    sandbox = request["sandbox"]
    if sandbox is not None and (not isinstance(sandbox, dict) or set(sandbox) != {"launcher"} or
                                not isinstance(sandbox["launcher"], str) or not os.path.isabs(sandbox["launcher"]) or
                                not os.path.isfile(sandbox["launcher"])):
        return None

    try:
        submission_root = os.path.realpath(submission["directory"])
        evidence_root = os.path.realpath(request["evidenceRoot"])
        if not os.path.isdir(submission_root) or not os.path.isdir(evidence_root):
            return None
        if _is_inside(evidence_root, submission_root) or _is_inside(submission_root, evidence_root):
            return None
    except OSError:
        return None

    # A missing deliverable is graded (every check fails), not refused: grader 1.2.0.
    entry_point = os.path.join(submission_root, "import_validator.py")
    return submission_root, entry_point, evidence_root, sandbox["launcher"] if sandbox else None


def grade_entry_point(entry_point):
    """Every check's outcome; without a delivered import_validator.py every check fails."""
    if os.path.islink(entry_point) or not os.path.isfile(entry_point):
        return {case_id: (False, "missing_deliverable") for case_id in [*ORACLE["cases"], "idempotency"]}
    return run_suite(entry_point)


def _write_json_file(path, value):
    temporary = path + ".tmp"
    with open(temporary, "x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def run_harness_protocol(request_path, result_path):
    """Adapter used by the TypeScript harness; answer material never enters the request."""
    global SANDBOX_LAUNCHER
    request = None
    request_id = "invalid-request"
    try:
        with open(request_path, encoding="utf-8") as handle:
            request = json.load(handle)
        if isinstance(request, dict) and isinstance(request.get("requestId"), str):
            request_id = request["requestId"]
        validated = _validate_grader_request(request)
        if validated is None:
            result = _grader_result(request_id, error_code="GRADER_REQUEST_INVALID", phase="request")
        else:
            _submission_root, entry_point, evidence_root, SANDBOX_LAUNCHER = validated
            outcomes = grade_entry_point(entry_point)
            checks = []
            for case_id, (passed, reason_code) in outcomes.items():
                check_id = "case_" + case_id
                evidence_ref = "checks/" + check_id + ".json"
                evidence_path = os.path.join(evidence_root, "checks", check_id + ".json")
                os.makedirs(os.path.dirname(evidence_path), exist_ok=True)
                _write_json_file(evidence_path, {
                    "schemaVersion": 1,
                    "checkId": check_id,
                    "status": "pass" if passed else "fail",
                    "reasonCode": "ok" if passed else reason_code,
                })
                checks.append({
                    "id": check_id,
                    "requirementId": "REQ-IMPLEMENTATION",
                    "status": "pass" if passed else "fail",
                    "evidenceRefs": [evidence_ref],
                })
            result = _grader_result(request_id, status="completed", checks=checks)
    except Exception:
        result = _grader_result(request_id, error_code="GRADER_EXECUTION_ERROR", phase="grading")

    try:
        _write_json_file(result_path, result)
        return 0
    except OSError:
        return 1


def _print_suite(impl, res):
    npass = sum(1 for _, (ok, _d) in res.items() if ok)
    print(f"-- {os.path.basename(impl)}: {npass}/{len(res)} checks passed")
    for cid, (ok, detail) in res.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {cid}: {detail}")


def self_calibrate():
    ref_a = "private/ref_impl_a.py"
    ref_b = "private/ref_impl_b.py"
    bad = ["private/bad_impl_naive_split.py", "private/bad_impl_always_exit0.py",
           "private/bad_impl_dryrun_writes.py", "private/bad_impl_insert_only.py",
           "private/bad_impl_empty.py"]
    allok = True
    print("Import-validator self-calibration")

    ra = run_suite(ref_a)
    _print_suite(ref_a, ra)
    a_all = all(ok for ok, _ in ra.values())
    print("Reference A passed:", a_all)
    allok &= a_all

    rb = run_suite(ref_b)
    _print_suite(ref_b, rb)
    b_all = all(ok for ok, _ in rb.values())
    print("Reference B passed:", b_all)
    allok &= b_all

    for b in bad:
        res = run_suite(b)
        npass = sum(1 for ok, _ in res.values() if ok)
        rejected = npass < len(res)
        print(f"{os.path.basename(b)}: {npass}/{len(res)} checks; {'REJECTED' if rejected else 'NOT REJECTED'}")
        allok &= rejected

    # A copy of reference A that also lists codes with a zero count must pass every check.
    zero_dir = tempfile.mkdtemp(prefix="eng001-zero-counts-")
    try:
        zero_impl = os.path.join(zero_dir, "ref_impl_zero_counts.py")
        source = open(ref_a, encoding="utf-8").read()
        listed = "    by_code = {}\n"
        if source.count(listed) != 1:
            raise SystemExit("reference A no longer builds by_code as expected")
        with open(zero_impl, "w", encoding="utf-8") as handle:
            handle.write(source.replace(listed, "    by_code = {code: 0 for code in ('missing_required', 'type_mismatch', 'constraint', 'unique_violation')}\n"))
        rz = run_suite(zero_impl)
        z_all = all(ok for ok, _ in rz.values())
        print("Reference A with zero-count codes passed:", z_all)
        allok &= z_all
    finally:
        shutil.rmtree(zero_dir, ignore_errors=True)

    # The null agent (grader 1.2.0): no import_validator.py is graded, and fails every check.
    missing = grade_entry_point(os.path.join(tempfile.gettempdir(), "eng001-no-delivery", "import_validator.py"))
    null_failed = len(missing) == len(ra) and not any(ok for ok, _ in missing.values())
    print(f"No delivery: {sum(1 for ok, _ in missing.values() if ok)}/{len(missing)} checks; {'REJECTED' if null_failed else 'NOT REJECTED'}")
    allok &= null_failed

    ra2 = run_suite(ref_a)
    repeatable = {k: v[0] for k, v in ra.items()} == {k: v[0] for k, v in ra2.items()}
    print("Reference results are repeatable:", repeatable)
    allok &= repeatable

    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--impl")
    p.add_argument("--self-calibrate", action="store_true")
    p.add_argument("--request")
    p.add_argument("--result")
    a = p.parse_args()
    if a.request or a.result:
        if not a.request or not a.result or a.impl or a.self_calibrate:
            p.error("--request and --result must be provided together and without calibration options")
        sys.exit(run_harness_protocol(a.request, a.result))
    if a.self_calibrate:
        sys.exit(self_calibrate())
    if a.impl:
        res = run_suite(a.impl)
        _print_suite(a.impl, res)
        sys.exit(0 if all(ok for ok, _ in res.values()) else 1)
    p.error("Provide --impl, --self-calibrate, or both --request and --result.")


if __name__ == "__main__":
    main()
