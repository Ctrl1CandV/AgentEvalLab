#!/usr/bin/env python3
"""Grades ER deliveries as SWE-bench does, offline (TASK_LIBRARY §3.1, CODE §5).

The delivery is the change the model made to the repository (`patchRef`, read by the harness against the single
commit). The grader unpacks the repository archive afresh, applies the change, restores every file the gold tests touch
to its base version and applies the gold tests, so edits the model made to those files do not count, and runs the
task's test files with pytest in the sandbox, with the task's runtime bound read-only. Checks: `fail-to-pass` (every
FAIL_TO_PASS test passes) and `pass-to-pass` (no PASS_TO_PASS test fails), both critical. Raw values: `f2pShare`,
`p2pRegressions`, `patchApplied`.

Usage: grader.py --request REQUEST --result RESULT | --self-calibrate
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
TASK_ID = "er-live-repair"
TASK_VERSION = "0.1.0"
GRADER_VERSION = "1.0.0"
TEST_TIMEOUT = 600
RESULT = re.compile(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (.+?)\s*$", re.M)
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def node_of(rest):
    """The test id at the start of a `pytest -rA` summary line, whole: a parametrized id may contain spaces, and a
    failure's message follows " - " (cutting at the first space merged distinct tests, so one could mask another)."""
    first = rest.split(" ", 1)[0]
    if "[" not in first or first.endswith("]"):
        return first
    for match in re.finditer(r"\]", rest):
        if match.end() == len(rest) or rest.startswith(" - ", match.end()):
            return rest[:match.end()]
    return first


def parse_results(stdout):
    """{test id: status} from pytest's -rA summary; colour codes (a project's --color=yes) are removed first."""
    return {node_of(rest): status for status, rest in RESULT.findall(ANSI.sub("", stdout))}


def tasks():
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        return json.load(handle)


def manifest_item(item_id):
    with open(os.path.join(PACKAGE, "manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    return next(item for item in manifest["items"] if item["id"] == item_id)


def git_apply(directory, patch_text, reverse=False):
    if not patch_text.strip():
        return True
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8") as handle:
        handle.write(patch_text)
    try:
        command = ["git", "apply", "--binary", "--whitespace=nowarn", *(["--reverse"] if reverse else []), handle.name]
        return subprocess.run(command, cwd=directory, capture_output=True, timeout=120).returncode == 0
    finally:
        os.remove(handle.name)


def patch_files(patch):
    return sorted(set(re.findall(r"^diff --git a/(\S+) b/", patch, re.M)))


def prepared_repository(work, archive, change, test_patch):
    """The repository at the base, with the delivered change, the gold test files restored and the gold tests applied.
    Returns (directory, whether the change applied)."""
    repo = os.path.join(work, "repo")
    os.makedirs(repo)
    with tarfile.open(archive) as tar:
        tar.extractall(repo, filter="tar")
    applied = git_apply(repo, change)
    if not applied:
        # The change does not apply: the base is graded, so nothing it would have fixed counts.
        shutil.rmtree(repo)
        os.makedirs(repo)
        with tarfile.open(archive) as tar:
            tar.extractall(repo, filter="tar")
    with tarfile.open(archive) as tar:
        names = set(tar.getnames())
        for path in patch_files(test_patch):
            target = os.path.join(repo, path)
            member = next((name for name in (path, f"./{path}") if name in names), None)
            if member is not None:
                with tar.extractfile(member) as base, open(target, "wb") as out:
                    out.write(base.read())
            elif os.path.exists(target):
                os.remove(target)
    if not git_apply(repo, test_patch):
        raise RuntimeError("the gold tests do not apply to the restored files")
    return repo, applied


def run_tests(repo, files, sandbox, runtime):
    command = [sys.executable, "-m", "pytest", "-rA", "-p", "no:cacheprovider", "--no-header", "-q", *files]
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    # "{workspace}" stands for the directory that holds repo/, as in execute_command.
    runtime = {**runtime, "env": {name: value.replace("{workspace}", os.path.dirname(repo)) for name, value in runtime["env"].items()}}
    if sandbox:
        mounts = [part for mount in runtime["mounts"] for part in ("--mount", f"{mount['source']}:{mount['target']}")]
        settings = [part for name, value in runtime["env"].items() for part in ("--env", f"{name}={value}")]
        command = [sys.executable, sandbox["launcher"], "--rw", os.path.dirname(repo), *mounts, *settings, "--env", "PYTHONDONTWRITEBYTECODE=1", "--", *command]
    else:
        env.update(runtime["env"])
    try:
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=TEST_TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        return {}, "timeout"
    return parse_results(result.stdout), result.stdout[-4000:]


def grade(item_id, change, sandbox, runtime):
    task = tasks()[item_id]
    item = manifest_item(item_id)
    archive = os.path.join(PACKAGE, *item["repository"]["archive"].split("/"))
    with tempfile.TemporaryDirectory(prefix="er-grade-") as work:
        repo, applied = prepared_repository(work, archive, change, task["test_patch"])
        statuses, tail = run_tests(repo, task["test_files"], sandbox, runtime)
    ok = lambda node: statuses.get(node) in ("PASSED", "XFAIL")
    f2p = [ok(node) for node in task["FAIL_TO_PASS"]]
    regressions = [node for node in task["PASS_TO_PASS"] if not ok(node)]
    return ({"fail-to-pass": all(f2p), "pass-to-pass": not regressions},
            {"f2pShare": sum(f2p) / len(f2p), "p2pRegressions": len(regressions), "patchApplied": 1 if applied else 0},
            {"applied": applied, "failing": [node for node, good in zip(task["FAIL_TO_PASS"], f2p) if not good], "regressions": regressions[:50], "tail": tail})


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=1)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    item_id = request["context"].get("itemId")
    if item_id not in tasks():
        raise ValueError("unknown item")
    with open(os.path.join(request["evidenceRoot"], request["patchRef"]), encoding="utf-8", errors="surrogateescape") as handle:
        change = handle.read()
    checks, metrics, evidence = grade(item_id, change, request.get("sandbox"), request["runtime"])
    write_json(os.path.join(request["evidenceRoot"], "tests.json"), evidence)
    write_json(result_path, {"schemaVersion": 2, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed",
                             "checks": [{"id": check, "requirementId": {"fail-to-pass": "REQ-FAIL-TO-PASS", "pass-to-pass": "REQ-PASS-TO-PASS"}[check],
                                         "status": "pass" if ok else "fail", "evidenceRefs": ["tests.json"]} for check, ok in checks.items()],
                             "dimensions": [], "unscoredCheckIds": [], "reason": None, "error": None,
                             "metrics": [{"id": name, "value": value} for name, value in metrics.items()]})


def weakening_patch(archive, files):
    """A change that replaces the given test files with a test that always passes, as a delivery might."""
    with tempfile.TemporaryDirectory(prefix="er-weaken-") as work:
        with tarfile.open(archive) as tar:
            tar.extractall(work, filter="tar")
        run = lambda *args: subprocess.run(["git", "-c", "user.name=x", "-c", "user.email=x@invalid", *args], cwd=work, capture_output=True, text=True, check=True)
        run("init", "-q")
        run("add", "-A", "-f")
        run("commit", "-q", "-m", "base", "--no-verify")
        for path in files:
            target = os.path.join(work, path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("def test_placeholder():\n    pass\n")
        run("add", "-A", "-f")
        return run("diff", "--cached", "--binary").stdout


def self_calibrate(launcher, only=None):
    """Per task: the gold fix resolves it; no change, the gold fix with the tests weakened, and a change that does not
    apply do not. Runtimes are unpacked from the package's archives into a temporary cache."""
    with open(os.path.join(PACKAGE, "manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    mounts = {mount["path"]: mount for mount in manifest["runtime"]["mounts"]}
    rows = []
    with tempfile.TemporaryDirectory(prefix="er-runtimes-") as cache:
        for item in manifest["items"]:
            if only and item["id"] not in only:
                continue
            task = tasks()[item["id"]]
            mount = mounts[item["mounts"][0]]
            source = os.path.join(cache, os.path.basename(mount["archive"]))
            if not os.path.isdir(source):
                os.makedirs(source)
                with tarfile.open(os.path.join(PACKAGE, *mount["archive"].split("/"))) as tar:
                    tar.extractall(source, filter="tar")
            target = f"/{mount['path']}"
            runtime = {"mounts": [{"source": source, "target": target}], "env": {name: value.replace("{mount}", target) for name, value in mount["env"].items()}}
            sandbox = {"launcher": launcher} if launcher else None
            # Weakened tests alone: the restore undoes them, so nothing is fixed; with the gold fix, the fix still counts.
            weakened = weakening_patch(os.path.join(PACKAGE, *item["repository"]["archive"].split("/")), patch_files(task["test_patch"]))
            scenarios = [("gold", task["gold_patch"], True), ("no-change", "", False), ("weakened-tests-only", weakened, False),
                         ("does-not-apply", "diff --git a/nowhere.py b/nowhere.py\n--- a/nowhere.py\n+++ b/nowhere.py\n@@ -1 +1 @@\n-x\n+y\n", False)]
            for name, change, expected in scenarios:
                checks, metrics, evidence = grade(item["id"], change, sandbox, runtime)
                resolved = all(checks.values())
                ok = resolved == expected
                rows.append(ok)
                print(f"{item['id']} {name}: resolved {resolved}, f2pShare {metrics['f2pShare']:.2f}, regressions {metrics['p2pRegressions']}" +
                      ("" if ok else f"  EXPECTED {expected}; failing {evidence['failing'][:3]}"), flush=True)
    print(f"RESULT: {'PASS' if all(rows) else 'FAIL'} ({sum(rows)}/{len(rows)})")
    return 0 if all(rows) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--result")
    parser.add_argument("--self-calibrate", action="store_true")
    parser.add_argument("--launcher")
    parser.add_argument("--items")
    args = parser.parse_args()
    if args.self_calibrate:
        raise SystemExit(self_calibrate(args.launcher, set(args.items.split(",")) if args.items else None))
    if not args.request or not args.result:
        parser.error("--request and --result are required")
    grade_request(args.request, args.result)


if __name__ == "__main__":
    main()
