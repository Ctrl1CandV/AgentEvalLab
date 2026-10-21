#!/usr/bin/env python3
"""Grades E4 submissions. Each item's checks run the candidate's deliverables on hidden inputs, inside the sandbox
launcher when the request provides one, in a fresh copy of the submission. Expected results come from the item's
oracle. The score is the fraction of checks passed.
"""
import argparse
import importlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
TASK_ID = "e4-terminal-tasks"
TASK_VERSION = "0.5.0"
GRADER_VERSION = "1.4.0"
CHECKS = {
    "perf": ["workspace-output", "quirks", "empty", "speed"],
    "migrate": ["schema", "names", "emails", "dates", "totals", "statuses", "orphans", "idempotent", "atomic", "workspace-db"],
    "bisect": ["culprit", "regression-fixed", "rounding-kept", "later-features", "coupons"],
    "build": ["flags", "build", "tests", "eof-word", "ties", "options", "clean"],
    "stockroom": ["strict-env", "timezone", "stock-cache", "duplicates", "money", "export-speed", "regression"],
    "pipeline": ["line-ends", "store-ids", "eu-format", "rebuild", "combined", "regression"],
    "recover": ["search-commit", "search-tree", "stash-commit", "stash-file"],
    "speedup": ["small", "large", "quirks", "speed-8", "speed-3", "speed-1.5", "speed-1.1", "speed-0.75"],
    "codec": ["words", "short-tokens", "numbers", "timestamps", "spaces", "long-literals", "eviction", "multi-day", "bytes", "edges", "restore"],
    "compress": ["roundtrip", "roundtrip-quirks", "ratio-50", "ratio-80", "ratio-90", "ratio-97"],
}
SPEED_LIMIT_SECONDS = 2.0
COMMAND_TIMEOUT_SECONDS = 60


class Runner:
    """Runs commands in a directory, through the sandbox launcher when one is given."""

    def __init__(self, launcher):
        self.launcher = launcher

    def run(self, directory, command, stdin=None, timeout=COMMAND_TIMEOUT_SECONDS):
        if self.launcher:
            command = [sys.executable, self.launcher, "--rw", directory, "--", *command]
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8", "HOME": directory}
        try:
            return subprocess.run(command, cwd=directory, input=stdin, capture_output=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return None


def workdir(submission):
    """A fresh copy of the submission, file modes included."""
    directory = tempfile.mkdtemp(prefix="e4-check-")
    shutil.copytree(submission, directory, dirs_exist_ok=True)
    return directory


# perf ------------------------------------------------------------------------------------------------------------

def grade_perf(submission, runner):
    from perf import data, oracle
    inputs = {"workspace": data.events(*data.WORKSPACE), "quirks-a": data.events(*data.HIDDEN["quirks-a"]),
              "quirks-b": data.events(*data.HIDDEN["quirks-b"]), "ties": data.TIES, "empty": data.EMPTY, "large": data.events(*data.HIDDEN["large"])}
    results = {}
    if not os.path.isfile(os.path.join(submission, "report.py")):
        return {check: False for check in CHECKS["perf"]}
    directory = workdir(submission)
    try:
        outputs = {}
        for name, text in inputs.items():
            path = os.path.join(directory, f"hidden-{name}.csv")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            expected = oracle.report(oracle.load(path))
            start = time.monotonic()
            run = runner.run(directory, ["python3", "report.py", os.path.basename(path)])
            elapsed = time.monotonic() - start
            finished = run is not None and run.returncode == 0
            outputs[name] = (finished and run.stdout.decode("utf-8", "replace") == expected, elapsed, finished and bool(run.stdout))
        # The output checks guard the speed-up, so they count only for a fast program: the slow original is correct.
        fast = outputs["large"][2] and outputs["large"][1] < SPEED_LIMIT_SECONDS
        results["speed"] = fast
        results["workspace-output"] = fast and outputs["workspace"][0]
        results["quirks"] = fast and all(outputs[name][0] for name in ("quirks-a", "quirks-b", "ties", "large"))
        results["empty"] = fast and outputs["empty"][0]
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    return results


# migrate ---------------------------------------------------------------------------------------------------------

def table_rows(path, query):
    connection = sqlite3.connect(path)
    try:
        return sorted(connection.execute(query).fetchall(), key=repr)
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def schema_of(path):
    connection = sqlite3.connect(path)
    try:
        tables = sorted(row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"))
        columns = {table: sorted((row[1], row[2].upper(), row[3], row[5]) for row in connection.execute(f"PRAGMA table_info({table})")) for table in tables}
        indexes = sorted((row[0], tuple(info[2] for info in connection.execute(f"PRAGMA index_info({row[0]})")))
                         for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"))
        return tables, columns, indexes
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def dump(path):
    connection = sqlite3.connect(path)
    try:
        return "\n".join(connection.iterdump())
    finally:
        connection.close()


ASPECTS = {
    "names": ["SELECT id, first_name, last_name FROM customers"],
    "emails": ["SELECT id, email FROM customers"],
    "dates": ["SELECT id, joined FROM customers", "SELECT id, placed FROM orders"],
    "totals": ["SELECT id, total_cents, currency FROM orders"],
    "statuses": ["SELECT id, status FROM orders"],
    "orphans": ["SELECT id FROM orders", "SELECT order_id, reason FROM migration_log"],
}


def migrated_pair(directory, runner, name, build):
    """(candidate database after its migrate.py, expected database after the oracle, candidate exit status)."""
    from migrate import oracle
    candidate, expected = os.path.join(directory, f"{name}.db"), os.path.join(directory, f"{name}-expected.db")
    build(candidate)
    build(expected)
    oracle.migrate(expected)
    run = runner.run(directory, ["python3", "migrate.py", os.path.basename(candidate)])
    return candidate, expected, (None if run is None else run.returncode)


def grade_migrate(submission, runner):
    from migrate import data, oracle
    results = {check: False for check in CHECKS["migrate"]}
    if not os.path.isfile(os.path.join(submission, "migrate.py")):
        return results
    directory = workdir(submission)
    try:
        pairs = [migrated_pair(directory, runner, "hidden", lambda path: data.generated(path, *data.HIDDEN)),
                 migrated_pair(directory, runner, "small", lambda path: data.write(path, data.SMALL_CUSTOMERS, data.SMALL_ORDERS))]
        ran = all(status == 0 for _, _, status in pairs)
        results["schema"] = ran and all(schema_of(candidate) == schema_of(expected) for candidate, expected, _ in pairs) and all(
            table_rows(candidate, "SELECT version FROM schema_version") == [(2,)] for candidate, _, _ in pairs)
        for aspect, queries in ASPECTS.items():
            results[aspect] = ran and all(table_rows(candidate, query) == table_rows(expected, query) for candidate, expected, _ in pairs for query in queries)
        if ran:
            before = dump(pairs[0][0])
            again = runner.run(directory, ["python3", "migrate.py", os.path.basename(pairs[0][0])])
            results["idempotent"] = again is not None and again.returncode == 0 and dump(pairs[0][0]) == before
        atomic = True
        for kind in ("total", "status", "date"):
            path = os.path.join(directory, f"bad-{kind}.db")
            data.generated(path, *data.HIDDEN, bad=kind)
            before = dump(path)
            run = runner.run(directory, ["python3", "migrate.py", os.path.basename(path)])
            atomic = atomic and run is not None and run.returncode != 0 and dump(path) == before
        # A script that always fails would leave every database unchanged; atomicity counts only for one that migrates.
        results["atomic"] = ran and atomic
        delivered = os.path.join(submission, "shop.db")
        expected = os.path.join(directory, "workspace-expected.db")
        data.generated(expected, *data.WORKSPACE)
        oracle.migrate(expected)
        results["workspace-db"] = os.path.isfile(delivered) and schema_of(delivered) == schema_of(expected) and all(
            table_rows(delivered, f"SELECT * FROM {table}") == table_rows(expected, f"SELECT * FROM {table}")
            for table in ("customers", "orders", "migration_log", "schema_version"))
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    return results


# bisect ----------------------------------------------------------------------------------------------------------

def grade_bisect(submission, runner):
    with open(os.path.join(HERE, "bisect_item", "culprit.txt"), encoding="utf-8") as handle:
        culprit = handle.read().strip()
    results = {check: False for check in CHECKS["bisect"]}
    path = os.path.join(submission, "culprit.txt")
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as handle:
            results["culprit"] = handle.read().strip().lower() == culprit
    fixed = os.path.join(submission, "fixed", "pricing.py")
    if os.path.isfile(fixed):
        directory = tempfile.mkdtemp(prefix="e4-check-")
        try:
            shutil.copy(fixed, os.path.join(directory, "pricing.py"))
            shutil.copy(os.path.join(HERE, "bisect_item", "checks.py"), os.path.join(directory, "checks.py"))
            run = runner.run(directory, ["python3", "checks.py"])
            if run is not None and run.returncode == 0:
                try:
                    verdicts = json.loads(run.stdout.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    verdicts = {}
                # The other checks guard the fix, so they count only once the regression is fixed: the current file passes them.
                fixed_regression = verdicts.get("regression-fixed") is True
                for check in CHECKS["bisect"][1:]:
                    results[check] = fixed_regression and verdicts.get(check) is True
        finally:
            shutil.rmtree(directory, ignore_errors=True)
    return results


# build -----------------------------------------------------------------------------------------------------------

HIDDEN_RUNS = {
    "eof-word": [([], b"Zeta alpha zeta", b"2 zeta\n1 alpha\n")],
    "ties": [([], b"b a c b a c d\n", b"2 a\n2 b\n2 c\n1 d\n"), (["-n", "2"], b"pear apple fig apple pear fig kiwi\n", b"2 apple\n2 fig\n")],
    "options": [(["-n", "1", "input.txt"], None, b"2 don't\n"), (["-n", "3"], b"It's IT, its; it's.\n", b"2 it's\n1 it\n1 its\n")],
}
OPTION_FILE = b"Don't stop, don't STOP believing\n"


def grade_build(submission, runner):
    results = {check: False for check in CHECKS["build"]}
    makefile = os.path.join(submission, "Makefile")
    if not os.path.isfile(makefile):
        return results
    with open(makefile, encoding="utf-8", errors="replace") as handle:
        flags = [line for line in handle if line.startswith("CFLAGS")]
    results["flags"] = len(flags) == 1 and all(flag in flags[0].split() for flag in ("-std=c11", "-Wall", "-Wextra", "-Werror", "-O2"))
    directory = workdir(submission)
    try:
        # The candidate's tests must be the shipped ones.
        shipped = os.path.join(PACKAGE, "items", "build", "public", "tests", "cases")
        cases_kept = sorted(os.listdir(shipped)) == sorted(os.listdir(os.path.join(directory, "tests", "cases"))) if os.path.isdir(os.path.join(directory, "tests", "cases")) else False
        if cases_kept:
            for name in os.listdir(shipped):
                with open(os.path.join(shipped, name), "rb") as one, open(os.path.join(directory, "tests", "cases", name), "rb") as two:
                    cases_kept = cases_kept and one.read() == two.read()
        runner.run(directory, ["make", "clean"])
        built = runner.run(directory, ["make"])
        binary = os.path.join(directory, "bin", "wordfreq")
        results["build"] = built is not None and built.returncode == 0 and os.path.isfile(binary) and os.access(binary, os.X_OK)
        # The flags check guards the repair: an untouched Makefile keeps its flags but does not build.
        results["flags"] = results["flags"] and results["build"]
        if results["build"]:
            tested = runner.run(directory, ["make", "test"])
            results["tests"] = cases_kept and tested is not None and tested.returncode == 0
            with open(os.path.join(directory, "input.txt"), "wb") as handle:
                handle.write(OPTION_FILE)
            for check, runs in HIDDEN_RUNS.items():
                ok = True
                for args, stdin, expected in runs:
                    run = runner.run(directory, ["bin/wordfreq", *args], stdin=stdin if stdin is not None else b"")
                    ok = ok and run is not None and run.returncode == 0 and run.stdout == expected
                results[check] = ok
            os.remove(os.path.join(directory, "input.txt"))
            cleaned = runner.run(directory, ["make", "clean"])
            results["clean"] = cleaned is not None and cleaned.returncode == 0 and not os.path.exists(os.path.join(directory, "bin")) and not os.path.exists(
                os.path.join(directory, "obj"))
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    return results


# stockroom ---------------------------------------------------------------------------------------------------------

def hidden_checks(item_id, submission, runner, required, timeout=600):
    """Runs an item's hidden check script on a copy of the delivered workspace; it prints {check: true/false}. The item's
    other modules (the codec's encoder and cases) go beside it."""
    if not os.path.exists(os.path.join(submission, required)):
        return {check: False for check in CHECKS[item_id]}
    directory = workdir(submission)
    try:
        item_directory = os.path.join(HERE, f"{item_id}_item")
        for name in sorted(os.listdir(item_directory)):
            if name.endswith(".py") and name != "checks.py":
                shutil.copy(os.path.join(item_directory, name), os.path.join(directory, name))
        shutil.copy(os.path.join(item_directory, "checks.py"), os.path.join(directory, "hidden_checks.py"))
        run = runner.run(directory, ["python3", "hidden_checks.py", directory], timeout=timeout)
        try:
            verdicts = json.loads(run.stdout.decode("utf-8").strip().splitlines()[-1]) if run is not None and run.returncode == 0 else {}
        except (UnicodeDecodeError, json.JSONDecodeError, IndexError):
            verdicts = {}
        return {check: verdicts.get(check) is True for check in CHECKS[item_id]}
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def grade_stockroom(submission, runner):
    return hidden_checks("stockroom", submission, runner, "stockroom")


def grade_pipeline(submission, runner):
    return hidden_checks("pipeline", submission, runner, "Makefile")


def grade_codec(submission, runner):
    return hidden_checks("codec", submission, runner, ".")


def grade_speedup(submission, runner):
    return hidden_checks("speedup", submission, runner, "analyze.py")


def grade_compress(submission, runner):
    # Twelve candidate runs of up to 60 seconds each, after about a minute of anchors.
    return hidden_checks("compress", submission, runner, "packlog.py", timeout=850)


# recover -----------------------------------------------------------------------------------------------------------

def read_text(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def grade_recover(submission, runner):
    with open(os.path.join(HERE, "recover_item", "answers.json"), encoding="utf-8") as handle:
        answers = json.load(handle)
    recovered = os.path.join(submission, "recovered")
    tree = os.path.join(recovered, "search")
    found = sorted(os.path.relpath(os.path.join(current, name), tree).replace(os.sep, "/")
                   for current, _, names in os.walk(tree) for name in names) if os.path.isdir(tree) else []
    return {
        "search-commit": (read_text(os.path.join(recovered, "search.txt")) or "").strip().lower() == answers["search"],
        "search-tree": found == sorted(answers["files"]) and all(read_text(os.path.join(tree, path)) == text for path, text in answers["files"].items()),
        "stash-commit": (read_text(os.path.join(recovered, "stash.txt")) or "").strip().lower() == answers["stash"],
        "stash-file": read_text(os.path.join(recovered, "RELEASE.md")) == answers["release"],
    }


GRADERS = {"perf": grade_perf, "migrate": grade_migrate, "bisect": grade_bisect, "build": grade_build, "stockroom": grade_stockroom,
           "pipeline": grade_pipeline, "recover": grade_recover, "codec": grade_codec, "speedup": grade_speedup, "compress": grade_compress}


def grade(item_id, submission, launcher):
    """submission: the delivered workspace; the task's files and deliverables are in its public/ directory."""
    results = GRADERS[item_id](os.path.join(submission, "public"), Runner(launcher))
    return {check: bool(results.get(check)) for check in CHECKS[item_id]}


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=1)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    item_id = request["context"].get("itemId")
    if item_id not in GRADERS:
        raise ValueError("unknown item")
    launcher = (request.get("sandbox") or {}).get("launcher")
    results = grade(item_id, request["submission"]["directory"], launcher)
    write_json(os.path.join(request["evidenceRoot"], "checks.json"), results)
    active = set(request["context"]["activeRequirementIds"])
    checks = [{"id": f"{item_id}-{check}", "requirementId": f"REQ-{item_id.upper()}-{check.upper()}", "status": "pass" if passed else "fail",
               "evidenceRefs": ["checks.json"]} for check, passed in results.items() if f"REQ-{item_id.upper()}-{check.upper()}" in active]
    write_json(result_path, {"schemaVersion": 1, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--result")
    parser.add_argument("--self-calibrate", action="store_true")
    parser.add_argument("--launcher", help="sandbox launcher for self-calibration")
    parser.add_argument("--items", help="self-calibrate only these items (comma-separated)")
    args = parser.parse_args()
    if args.self_calibrate:
        raise SystemExit(importlib.import_module("calibrate").self_calibrate(args.launcher, args.items.split(",") if args.items else None))
    if not args.request or not args.result:
        parser.error("--request and --result are required")
    grade_request(args.request, args.result)


if __name__ == "__main__":
    main()
