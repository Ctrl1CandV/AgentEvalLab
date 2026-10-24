#!/usr/bin/env python3
"""Grades an algorithm-engineering item: the solution in public/main.cpp (or public/main.py) is judged on the contest's
private cases with the official tester, its total is ranked among the human contestants of the original contest, and
the rank is converted into AtCoder performance.

Grader 2.0.0 (task 0.2.0, manifest v2) reports the raw values (grader result v2): the performance, uncapped and
extrapolated above the winner; the contest total; the performance rank. The one check per item is whether every case
was accepted (a valid delivery). The performance is normalised through the item's anchors (its naive reference, the
median contestant, the winner) by the harness, not here; rungs of performance are labels only.

Grader 2.1.0 (TASK_LIBRARY §3.6, PLAN-007 WP3.5) also judges the delivery on 50 fresh seeds of our own, drawn once
(`problems/<item>/fresh_seeds.txt`), with the same tools and rules: `freshTotal` is reported separately, normalised
through the item's naive and greedy references on the same seeds, and never ranked against the humans."""
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import ale  # noqa: E402

TASK_ID = "ae-heuristic-contests"
TASK_VERSION = "0.2.0"
GRADER_VERSION = "2.1.0"
LOCK_PATH = os.path.expanduser("~/.cache/agenteval/ae-grading.lock")


def check_names():
    return ["accepted"]


def requirement(item_id):
    return f"REQ-{item_id.upper()}-ACCEPTED"


def problem_directory(item_id):
    return os.path.join(HERE, "problems", item_id)


def judge_seeds(launcher, run_directory, judge_directory, spec, seeds_path):
    """(cases, compile error, inputs) of a delivery on the inputs the official generator makes from a seed file."""
    generated = subprocess.run(["./gen", seeds_path], cwd=judge_directory, capture_output=True, text=True)
    if generated.returncode != 0:
        raise RuntimeError(f"GENERATOR_FAILED: {generated.stderr[-500:]}")
    inputs = sorted(os.path.join(judge_directory, "in", name) for name in os.listdir(os.path.join(judge_directory, "in")))
    cases, error = ale.judge(launcher, run_directory, judge_directory, spec, inputs)
    return cases, error, inputs


def grade(item_id, public_directory, launcher):
    """(results {check: passed}, evidence)."""
    directory = problem_directory(item_id)
    spec = ale.load_problem(directory)
    standings = ale.load_table(os.path.join(directory, "standings_scores.csv"), "score")
    performance = ale.load_table(os.path.join(directory, "performance.csv"), "performance")
    evidence = {"itemId": item_id, "problem": spec["id"], "title": spec["title"]}
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ae-grade-") as work, open(LOCK_PATH, "a") as lock:
        # One judgement at a time on this machine, so that time limits are measured on an otherwise quiet judge.
        fcntl.flock(lock, fcntl.LOCK_EX)
        run_directory, judge_directory = os.path.join(work, "run"), os.path.join(work, "judge")
        os.makedirs(run_directory)
        os.makedirs(judge_directory)
        submitted = [name for name in ("main.cpp", "main.py") if os.path.isfile(os.path.join(public_directory, name))]
        for name in submitted[:1]:
            shutil.copy(os.path.join(public_directory, name), os.path.join(run_directory, name))
        evidence["language"] = "C++" if submitted[:1] == ["main.cpp"] else "Python" if submitted else None
        ale.copy_tools(os.path.join(directory, "tools"), judge_directory)
        cases, error, inputs = judge_seeds(launcher, run_directory, judge_directory, spec, os.path.join(directory, "private_seeds.txt"))
        # The same delivery on our fresh seeds, in a judge directory of its own (TASK_LIBRARY §3.6).
        fresh_directory = os.path.join(work, "fresh")
        os.makedirs(fresh_directory)
        ale.copy_tools(os.path.join(directory, "tools"), fresh_directory)
        fresh_cases, _, _ = judge_seeds(launcher, run_directory, fresh_directory, spec, os.path.join(directory, "fresh_seeds.txt"))
    total = ale.overall_score(spec["id"], cases)
    fresh_total = ale.overall_score(spec["id"], fresh_cases)
    rank, performance_rank = ale.rank_of(standings, total)
    perf, extrapolated = ale.performance_uncapped(standings, performance, total)
    verdicts = {}
    for case in cases or []:
        verdicts[case[1]] = verdicts.get(case[1], 0) + 1
    evidence.update({
        "compileError": error, "cases": len(inputs), "verdicts": verdicts, "total": total, "rank": rank,
        "contestants": standings[-1][0] - 1, "performanceRank": performance_rank, "performance": perf, "performanceExtrapolated": extrapolated,
        "humanAnchors": ale.anchors_of(standings, performance),
        "slowestSeconds": round(max((case[3] for case in cases or []), default=0.0), 3),
        "failedCases": [{"case": case[0], "verdict": case[1], "seconds": round(case[3], 3), "message": case[4]}
                        for case in (cases or []) if case[1] != "AC"][:20],
        "caseScores": {case[0]: case[2] for case in cases or []},
        "freshTotal": fresh_total, "freshCases": len(fresh_cases or []),
        "freshVerdicts": {verdict: sum(1 for case in fresh_cases or [] if case[1] == verdict) for verdict in {case[1] for case in fresh_cases or []}},
    })
    accepted = bool(cases) and all(case[1] == "AC" for case in cases)
    return {"accepted": accepted}, evidence


def metrics_of(evidence):
    """The raw values of a judgement (grader result v2)."""
    return [{"id": "performance", "value": evidence["performance"], "unit": "AtCoder performance"},
            {"id": "total", "value": evidence["total"], "unit": "contest score"},
            {"id": "performanceRank", "value": evidence["performanceRank"], "unit": "rank among contestants"},
            {"id": "performanceExtrapolated", "value": 1 if evidence["performanceExtrapolated"] else 0, "unit": "0 or 1"},
            {"id": "freshTotal", "value": evidence["freshTotal"], "unit": "contest score on 50 fresh seeds"}]


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=1)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    item_id = request["context"].get("itemId")
    if not item_id or not os.path.isdir(problem_directory(item_id)):
        raise ValueError("unknown item")
    sandbox = request.get("sandbox")
    launcher = sandbox.get("launcher") if isinstance(sandbox, dict) else None
    results, evidence = grade(item_id, os.path.join(request["submission"]["directory"], "public"), launcher)
    evidence_root = request["evidenceRoot"]
    write_json(os.path.join(evidence_root, "judgement.json"), evidence)
    active = set(request["context"]["activeRequirementIds"])
    checks = [{"id": f"{item_id}-{name}", "requirementId": requirement(item_id), "status": "pass" if passed else "fail",
               "evidenceRefs": ["judgement.json"]} for name, passed in results.items() if requirement(item_id) in active]
    write_json(result_path, {"schemaVersion": 2, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None, "metrics": metrics_of(evidence)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request")
    parser.add_argument("--result")
    parser.add_argument("--self-calibrate", action="store_true")
    args = parser.parse_args()
    if args.self_calibrate:
        import calibrate
        raise SystemExit(calibrate.self_calibrate())
    if not args.request or not args.result:
        parser.error("--request and --result are required")
    grade_request(args.request, args.result)


if __name__ == "__main__":
    main()
