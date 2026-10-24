#!/usr/bin/env python3
"""Grades E2 submissions: runs the candidate's program on each hidden fixture of the item, inside the sandbox
launcher when the request provides one, and compares its JSON output with the expected output.

Fixtures are grouped into checks; a check passes when every fixture in it passes. The score is the fraction of
checks passed, so a partly correct implementation gets partial credit.

Grader 1.6.0 (manifest v2): the routes item, the open-ended bridge, also reports its raw values. `routeShare` is the mean
over the eight hidden instances of how far each plan's cost gets from the baseline's towards the best known cost
(per instance at least 0, never capped; an infeasible, missing or late plan counts 0, as the contract says); it is the
item's headline. `routeCost` (the total cost, an instance without a feasible plan at its baseline's cost, a plan worse
than the baseline at the baseline's) and `feasibleInstances` are diagnostics. Routes gradings run one at a time under a
lock, since the contract's limit is wall time (PROTOCOL §9).
"""
import argparse
import fcntl
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TASK_ID = "e2-spec-implementation"
TASK_VERSION = "0.5.0"
GRADER_VERSION = "1.6.0"
# Per item: the file the candidate delivers, the module holding its hidden fixtures, and how a fixture becomes the
# program's input. Sheet output is compared cell by cell with numeric tolerance; the others must match exactly.
ITEMS = {
    "sheet": {"entry": "sheet.py", "fixtures": os.path.join(HERE, "sheet", "fixtures.py"), "input": lambda cells: {"cells": cells}, "cells": True},
    "ledger": {"entry": "ledger.py", "fixtures": os.path.join(HERE, "ledger", "fixtures.py"), "input": lambda data: data, "cells": False},
    "recur": {"entry": "recur.py", "fixtures": os.path.join(HERE, "recur", "fixtures.py"), "input": lambda data: data, "cells": False},
    "query": {"entry": "query.py", "fixtures": os.path.join(HERE, "query", "fixtures.py"), "input": lambda data: data, "cells": False},
    "routes": {"entry": "routes.py", "fixtures": os.path.join(HERE, "routes", "fixtures.py")},
}
FIXTURE_TIMEOUT_SECONDS = 10
ROUTES_TIMEOUT_SECONDS = 10
MAX_OUTPUT_BYTES = 1_000_000
ROUTES_LOCK = os.path.expanduser("~/.cache/agenteval/e2-routes-grading.lock")


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


def run_routes(program, data, launcher):
    """Run routes.py on one instance on one CPU core; returns (plan or None, reason)."""
    directory = tempfile.mkdtemp(prefix="e2-routes-")
    try:
        shutil.copy(program, os.path.join(directory, "routes.py"))
        with open(os.path.join(directory, "instance.json"), "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        command = ["python3", "routes.py", "instance.json"]
        if launcher:
            command = [sys.executable, launcher, "--rw", directory, "--", *command]
        # One core, inherited by every process the program starts; graders running side by side get different cores.
        cpus = sorted(os.sched_getaffinity(0))
        core = cpus[os.getpid() % len(cpus)]
        try:
            run = subprocess.run(command, cwd=directory, stdin=subprocess.DEVNULL, capture_output=True, timeout=ROUTES_TIMEOUT_SECONDS,
                                 preexec_fn=lambda: os.sched_setaffinity(0, {core}),
                                 env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8"})
        except subprocess.TimeoutExpired:
            return None, "timeout"
        if run.returncode != 0:
            return None, f"exit {run.returncode}"
        try:
            return json.loads(run.stdout.decode("utf-8")), "ok"
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "output is not JSON"
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def grade_routes(submission, launcher, raw=None):
    """Four checks per hidden instance: the plan is feasible and gets at least 50, 80, 90 or 97% of the way from the
    baseline's cost to the best-known cost. The raw values go into `raw` when given."""
    sys.path.insert(0, os.path.join(HERE, "routes"))
    import instances
    import model
    with open(os.path.join(HERE, "routes", "anchors.json"), encoding="utf-8") as handle:
        anchors = json.load(handle)
    program = os.path.join(submission, "routes.py")
    results, shares, cost_total, feasible = {}, [], 0.0, 0
    os.makedirs(os.path.dirname(ROUTES_LOCK), exist_ok=True)
    with open(ROUTES_LOCK, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for name in instances.HIDDEN:
            data = instances.instance(name)
            plan, reason = run_routes(program, data, launcher) if os.path.isfile(program) else (None, "routes.py missing")
            baseline, best = anchors[name]["baseline"], anchors[name]["best"]
            share, counted = 0.0, baseline
            if plan is not None:
                cost, problem = model.check(data, plan)
                if problem is None:
                    share = max(0.0, (baseline - cost) / (baseline - best))
                    counted, feasible = min(cost, baseline), feasible + 1
                    reason = f"cost {cost:.1f}, {share:.3f} of the way"
                else:
                    reason = f"infeasible: {problem}"
            shares.append(share)
            cost_total += counted
            for threshold in instances.THRESHOLDS:
                results[f"{name}-{threshold}"] = {"passed": share * 100 >= threshold, "fixtures": {name: reason}}
    results["readme"] = {"passed": os.path.isfile(os.path.join(submission, "README.md")), "fixtures": {}}
    if raw is not None:
        raw.update({"routeShare": sum(shares) / len(shares), "routeCost": cost_total, "feasibleInstances": feasible})
    return results


def grade_with_metrics(item_id, submission, launcher):
    """(results, metrics of grader result v2): only the routes item reports metrics."""
    if item_id != "routes":
        return grade(item_id, submission, launcher), []
    raw = {}
    results = grade_routes(submission, launcher, raw)
    return results, [{"id": "routeShare", "value": round(raw["routeShare"], 6), "unit": "mean share of the way from baseline to best known"},
                     {"id": "routeCost", "value": round(raw["routeCost"], 3), "unit": "total route length"},
                     {"id": "feasibleInstances", "value": raw["feasibleInstances"], "unit": "of 8 instances"}]


def grade(item_id, submission, launcher):
    """{check: {"passed": bool, "fixtures": {fixture: reason}}}; a missing program fails every check."""
    if item_id == "routes":
        return grade_routes(submission, launcher)
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
    results, metrics = grade_with_metrics(item_id, request["submission"]["directory"], launcher)
    write_json(os.path.join(request["evidenceRoot"], "fixtures.json"), results)
    active = set(request["context"]["activeRequirementIds"])
    checks = [{"id": check_id(item_id, check), "requirementId": requirement_id(item_id, check), "status": "pass" if result["passed"] else "fail",
               "evidenceRefs": ["fixtures.json"]} for check, result in sorted(results.items()) if requirement_id(item_id, check) in active]
    write_json(result_path, {"schemaVersion": 2, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None, "metrics": metrics})


def routes_calibration():
    """Routes has no pass-everything reference: the top thresholds on the largest instances are beyond an 8-second run.
    Instead, plain savings and a 7-second LNS each earn every 50% check, the LNS earns more than savings, and the
    baseline itself, an infeasible plan, a program that runs too long and a missing program earn nothing."""
    solutions = os.path.join(HERE, "routes", "solutions")

    def run(name):
        with tempfile.TemporaryDirectory(prefix="e2-calibration-") as submission:
            if name:
                shutil.copy(os.path.join(solutions, f"{name}.py"), os.path.join(submission, "routes.py"))
            with open(os.path.join(submission, "README.md"), "w", encoding="utf-8") as handle:
                handle.write("Calibration candidate.\n")
            return grade("routes", submission, None)

    results = {name: run(name) for name in ("lns", "savings", "nn", "infeasible", "slow", None)}
    for name, result in results.items():
        passed = sum(entry["passed"] for check, entry in result.items() if check != "readme")
        reasons = {check.split("-")[0]: next(iter(entry["fixtures"].values()), "") for check, entry in result.items() if check != "readme"}
        print(f"routes {name or 'missing'}: {passed}/32 checks; " + "; ".join(f"{instance} {reason}" for instance, reason in reasons.items()))
    earned = {name: sum(entry["passed"] for check, entry in result.items() if check != "readme") for name, result in results.items()}
    lns = results["lns"]
    return [("routes-lns-passes-every-50", all(entry["passed"] for check, entry in lns.items() if check.endswith("-50"))),
            ("routes-savings-passes-every-50", all(entry["passed"] for check, entry in results["savings"].items() if check.endswith("-50"))),
            ("routes-lns-beats-savings", earned["lns"] > earned["savings"]),
            ("routes-baseline-earns-nothing", earned["nn"] == 0),
            ("routes-infeasible-earns-nothing", earned["infeasible"] == 0),
            ("routes-timeout-earns-nothing", earned["slow"] == 0),
            ("routes-missing-earns-nothing", earned[None] == 0)]


def self_calibrate():
    """The reference passes every check of every item; every mutant fails the check it targets. No model is involved."""
    sys.path.insert(0, HERE)
    import mutants  # noqa: E402
    rows = []
    for item_id in ITEMS:
        if item_id == "routes":
            rows += routes_calibration()
            continue
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


def routes_noise(launcher, tolerance, load_processes=None):
    """PROTOCOL §9 noise test of the routes item (grader 1.6.0): the same solutions judged on a quiet machine and with
    every core busy. Verdicts are reported; the headline routeShare must change by at most `tolerance`."""
    solutions = os.path.join(HERE, "routes", "solutions")
    load_processes = load_processes or os.cpu_count() or 1
    rows = []
    for name in ("lns", "savings"):
        judged = []
        for loaded in (False, True):
            load = [subprocess.Popen([sys.executable, "-c", "while True: pass"]) for _ in range(load_processes)] if loaded else []
            try:
                with tempfile.TemporaryDirectory(prefix="e2-noise-") as submission:
                    shutil.copy(os.path.join(solutions, f"{name}.py"), os.path.join(submission, "routes.py"))
                    with open(os.path.join(submission, "README.md"), "w", encoding="utf-8") as handle:
                        handle.write("Noise test.\n")
                    results, metrics = grade_with_metrics("routes", submission, launcher)
            finally:
                for process in load:
                    process.kill()
                    process.wait()
            judged.append(({check for check, result in results.items() if result["passed"]}, {metric["id"]: metric["value"] for metric in metrics}))
        (quiet, quiet_metrics), (busy, busy_metrics) = judged
        change = abs(busy_metrics["routeShare"] - quiet_metrics["routeShare"])
        ok = change <= tolerance and busy_metrics["feasibleInstances"] == quiet_metrics["feasibleInstances"]
        print(f"routes {name}: quiet {quiet_metrics}; busy ({load_processes} busy processes on {os.cpu_count()} cores) {busy_metrics}; routeShare change {change:.4f}; "
              f"checks quiet only {sorted(quiet - busy)}, busy only {sorted(busy - quiet)}" + ("" if ok else "  NOT STABLE"))
        rows.append(ok)
    print(f"RESULT: {'PASS' if all(rows) else 'FAIL'} ({sum(rows)}/{len(rows)}), tolerance {tolerance} on routeShare")
    return 0 if all(rows) else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--result")
    parser.add_argument("--self-calibrate", action="store_true")
    parser.add_argument("--noise", action="store_true", help="the routes noise test (quiet against loaded machine)")
    parser.add_argument("--launcher", help="sandbox launcher for the noise test")
    parser.add_argument("--load", type=int, help="busy processes in the noise test's loaded run (default: one per core)")
    args = parser.parse_args()
    if args.noise:
        raise SystemExit(routes_noise(args.launcher, 0.03, args.load))
    if args.self_calibrate:
        raise SystemExit(self_calibrate())
    if not args.request or not args.result:
        parser.error("--request and --result are required")
    grade_request(args.request, args.result)


if __name__ == "__main__":
    main()
