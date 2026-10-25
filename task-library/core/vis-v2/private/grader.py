#!/usr/bin/env python3
"""Grades VIS v2 submissions: runs the brief's functional scenario (private/scenarios.mjs) on the page in `site/`, in
headless Chromium inside the sandbox, and records the screenshots the design judges see. The design rating comes from
the pairwise tournament (scripts/judge-tournament-v2.ts), not from here.

Checks per item: `renders`, `labels`, `no-overflow` (every brief) and the brief's own behaviours (private/briefs.py).
A submission without site/index.html fails every check.

Usage: grader.py --request REQUEST --result RESULT
       grader.py --render SITE --brief BRIEF --out DIR [--launcher sandbox_exec.py]
       grader.py --anchor reference|plain --brief BRIEF --out DIR [--launcher sandbox_exec.py]   (DIR/site and DIR/render)
       grader.py --self-calibrate [--launcher sandbox_exec.py]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from briefs import CHECKS, COMMON_CHECKS  # noqa: E402

TASK_ID = "vis-v2"
TASK_VERSION = "0.1.0"
GRADER_VERSION = "1.0.0"
SCENARIO_TIMEOUT = 180


def requirement(check):
    return "REQ-" + check.upper()


def find_playwright():
    """playwright-core from the repository's node_modules (the package lives inside the repository or a worktree of it)."""
    if os.environ.get("PLAYWRIGHT_CORE"):
        return os.path.realpath(os.environ["PLAYWRIGHT_CORE"])
    directory = PACKAGE
    while directory != os.path.dirname(directory):
        candidate = os.path.join(directory, "node_modules", "playwright-core")
        if os.path.isfile(os.path.join(candidate, "index.mjs")):
            return os.path.realpath(candidate)
        directory = os.path.dirname(directory)
    raise RuntimeError("playwright-core not found")


def find_chromium(playwright):
    if os.environ.get("CHROMIUM_PATH"):
        return os.environ["CHROMIUM_PATH"]
    with open(os.path.join(playwright, "browsers.json"), encoding="utf-8") as handle:
        shell = next(entry for entry in json.load(handle)["browsers"] if entry["name"] == "chromium-headless-shell")
    return os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright", f"chromium_headless_shell-{shell['revision']}", "chrome-linux", "headless_shell")


def content_path(brief):
    return os.path.join(PACKAGE, "items", brief, "public", "content.json")


def run_scenario(site, brief, out, launcher):
    """{check: (passed, detail)} for one brief; the screenshots land in `out`."""
    expected = COMMON_CHECKS + CHECKS[brief]
    if not os.path.isfile(os.path.join(site, "index.html")):
        return {check: (False, "site/index.html missing") for check in expected}
    os.makedirs(out, exist_ok=True)
    playwright = find_playwright()
    chromium = find_chromium(playwright)
    node = shutil.which("node")
    # Chromium's shared libraries (nss, nspr, alsa) come from the environment that provides node.
    libraries = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(node))), "lib")
    script = [node, os.path.join(HERE, "scenarios.mjs"), playwright, os.path.realpath(site), brief, content_path(brief), os.path.realpath(out)]
    environment = {"CHROMIUM": chromium, "LD_LIBRARY_PATH": libraries}
    if launcher:
        command = [sys.executable, launcher, "--rw", os.path.realpath(out), "--ro", os.path.realpath(site), "--ro", playwright,
                   "--ro", os.path.dirname(os.path.dirname(chromium)), "--ro", HERE, "--ro", os.path.dirname(content_path(brief)),
                   *[argument for name, value in environment.items() for argument in ("--env", f"{name}={value}")], "--", *script]
        run_env = None
    else:
        command, run_env = script, {**os.environ, **environment}
    try:
        run = subprocess.run(command, capture_output=True, text=True, timeout=SCENARIO_TIMEOUT, env=run_env)
        detail = (run.stderr or run.stdout).strip().splitlines()[-1:] or [f"exit {run.returncode}"]
    except subprocess.TimeoutExpired:
        return {check: (False, "scenario timed out") for check in expected}
    try:
        with open(os.path.join(out, "checks.json"), encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {check: (False, f"scenario failed: {detail[0][:200]}") for check in expected}
    error = raw.get("__error", {}).get("detail")
    return {check: (bool(raw[check]["passed"]), raw[check]["detail"]) if check in raw else (False, f"not reached: {error or 'scenario stopped'}")
            for check in expected}


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=1)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    brief = request["context"].get("itemId")
    if brief not in CHECKS:
        raise ValueError("unknown item")
    evidence = request["evidenceRoot"]
    launcher = (request.get("sandbox") or {}).get("launcher")
    results = run_scenario(os.path.join(request["submission"]["directory"], "site"), brief, os.path.join(evidence, "render"), launcher)
    write_json(os.path.join(evidence, "checks.json"), {check: {"passed": passed, "detail": detail} for check, (passed, detail) in results.items()})
    passed = sum(1 for ok, _ in results.values() if ok)
    write_json(result_path, {"schemaVersion": 2, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed",
                             "checks": [{"id": check, "requirementId": requirement(check), "status": "pass" if ok else "fail", "evidenceRefs": ["checks.json"]}
                                        for check, (ok, _) in results.items()],
                             "dimensions": [], "unscoredCheckIds": [], "reason": None, "error": None,
                             "metrics": [{"id": "checksPassed", "value": passed}, {"id": "checks", "value": len(results)}]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--result")
    parser.add_argument("--render")
    parser.add_argument("--anchor", choices=["reference", "plain"])
    parser.add_argument("--brief")
    parser.add_argument("--out")
    parser.add_argument("--launcher")
    parser.add_argument("--self-calibrate", action="store_true")
    parser.add_argument("--briefs")
    args = parser.parse_args()
    if args.self_calibrate:
        import calibrate
        raise SystemExit(calibrate.self_calibrate(args.launcher, args.briefs.split(",") if args.briefs else None))
    if args.anchor:
        import calibrate
        if os.path.exists(os.path.join(args.out, "site")):
            shutil.rmtree(os.path.join(args.out, "site"))
        args.render = calibrate.anchor_site(args.brief, args.anchor, os.path.join(args.out, "site"))
        args.out = os.path.join(args.out, "render")
    if args.render:
        results = run_scenario(args.render, args.brief, args.out, args.launcher)
        for check, (ok, detail) in results.items():
            print(f"{'PASS' if ok else 'FAIL'} {check}: {detail}")
        return
    if not args.request or not args.result:
        parser.error("--request and --result are required")
    grade_request(args.request, args.result)


if __name__ == "__main__":
    main()
