#!/usr/bin/env python3
"""Grades R1 roster answers: rule checks on a proposed roster, or the verdict and a solver-verified conflict set."""
import argparse
import itertools
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roster  # noqa: E402

TASK_ID = "r1-rostering"
TASK_VERSION = "0.1.0"
GRADER_VERSION = "1.0.0"
KEYS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")

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


def rule_requirement(rule):
    return "REQ-" + rule.upper().replace("_", "-")


def rule_check(rule):
    return "rule-" + rule.replace("_", "-")


def evaluate(record, mode, answer):
    """{check id: passed} for an item. Feasible items: coverage and each optional rule; infeasible: verdict, conflict."""
    instance = roster.Instance(record)
    answer = answer if mode != "unparsed" and isinstance(answer, dict) else {}
    if record["feasible"]:
        results = instance.violations(answer.get("roster") if answer.get("feasible") is True else None)
        return {rule_check(rule): passed for rule, passed in results.items()}
    claimed_infeasible = answer.get("feasible") is False
    conflict = answer.get("conflict")
    names = {str(rule).strip().lower() for rule in conflict} if isinstance(conflict, list) else None
    valid = bool(claimed_infeasible and names and len(names) == len(conflict) and names <= set(roster.RULES) and instance.is_minimal_conflict(names))
    return {"verdict": claimed_infeasible, "conflict": valid}


def requirement_for(check):
    if check.startswith("rule-"):
        return "REQ-" + check[len("rule-"):].upper()
    return {"verdict": "REQ-VERDICT", "conflict": "REQ-CONFLICT", "answer-format": "REQ-FORMAT"}[check]


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    with open(KEYS_PATH, encoding="utf-8") as handle:
        keys = json.load(handle)
    context = request["context"]
    item_id = context.get("itemId")
    if item_id not in keys:
        raise ValueError("unknown item")
    evidence_root = request["evidenceRoot"]
    try:
        with open(os.path.join(evidence_root, request["answerRef"]), encoding="utf-8") as handle:
            mode, answer = parse_answer(handle.read())
    except (OSError, UnicodeDecodeError, TypeError):
        mode, answer = "unparsed", None
    results = evaluate(keys[item_id], mode, answer)
    results["answer-format"] = mode == "strict"
    active = set(context["activeRequirementIds"])
    checks = [{"id": check, "requirementId": requirement_for(check), "status": "pass" if passed else "fail", "evidenceRefs": ["checks.json"]}
              for check, passed in sorted(results.items()) if requirement_for(check) in active]
    write_json(os.path.join(evidence_root, "checks.json"), {"itemId": item_id, "parse": mode, "feasible": keys[item_id]["feasible"], "results": results})
    write_json(result_path, {"schemaVersion": 1, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed", "checks": checks, "dimensions": [],
                             "unscoredCheckIds": [], "reason": None, "error": None})


def brute_force_feasible(instance, rules):
    """Exhaustive check for small instances: does any roster satisfy coverage and the rules?"""
    groups = list(itertools.combinations(instance.people, instance.need))
    slots = instance.slots()
    probe = roster.Instance(dict(instance.record, rules=sorted(rules)))
    for choice in itertools.product(groups, repeat=len(slots)):
        candidate = {f"Day {day + 1}": {} for day in range(instance.days)}
        for (day, shift), group in zip(slots, choice):
            candidate[f"Day {day + 1}"][instance.shifts[shift]] = list(group)
        if all(probe.violations(candidate).values()):
            return True
    return False


def self_calibrate():
    """Verify the solver against brute force, every key, and the grader on known answers; no model is involved."""
    with open(KEYS_PATH, encoding="utf-8") as handle:
        keys = json.load(handle)
    rows = []
    # The solver decides feasibility for any rule subset, so it is cross-checked against brute force on small instances.
    rng = random.Random("r1-solver-cross-check")
    agreements = 0
    for trial in range(60):
        people = sorted(rng.sample(roster.PEOPLE, 3))
        record = {"people": people, "days": 3, "shifts": ["early", "late"], "need": 1, "rules": sorted(rng.sample(roster.RULES, 4)),
                  "unavailable": sorted([p, d] for p in people for d in range(3) if rng.random() < 0.3), "max_shifts": rng.choice([1, 2, 3]),
                  "min_shifts": rng.choice([1, 2, 3]), "seniors": [rng.choice(people)], "apart": [sorted(rng.sample(people, 2))]}
        instance = roster.Instance(record)
        subset = set(rng.sample(sorted(instance.rules), rng.randrange(1, 5)))
        agreements += (instance.feasible(subset) is not None) == brute_force_feasible(instance, subset)
    rows.append(("solver-agrees-with-brute-force-60-instances", agreements == 60))
    for item_id, record in sorted(keys.items()):
        instance = roster.Instance(record)
        solver = roster.Instance({key: value for key, value in record.items() if key != "subsets"})
        rows.append((f"{item_id}-subset-table-matches-solver", all(
            (solver.feasible(set(name.split("+")) if name != "-" else set()) is not None) == feasible for name, feasible in record["subsets"].items())))
        if record["feasible"]:
            rows.append((f"{item_id}-feasible-confirmed", instance.feasible() is not None))
            example = {"feasible": True, "roster": record["example"]}
            rows.append((f"{item_id}-example-passes", all(evaluate(record, "strict", example).values())))
            fenced = parse_answer("```json\n" + json.dumps(example) + "\n```")
            rows.append((f"{item_id}-fenced-recovered", fenced[0] == "recovered" and all(evaluate(record, *fenced).values())))
            empty = {"feasible": True, "roster": {day: {shift: [] for shift in shifts} for day, shifts in record["example"].items()}}
            rows.append((f"{item_id}-empty-roster-scores-zero", not any(evaluate(record, "strict", empty).values())))
            rows.append((f"{item_id}-wrong-verdict-scores-zero", not any(evaluate(record, "strict", {"feasible": False, "conflict": ["coverage"]}).values())))
        else:
            rows.append((f"{item_id}-infeasible-confirmed", instance.feasible() is None))
            conflicts = record["conflicts"]
            rows.append((f"{item_id}-conflicts-minimal", all(instance.is_minimal_conflict(conflict) for conflict in conflicts)))
            rows.append((f"{item_id}-each-conflict-passes", all(evaluate(record, "strict", {"feasible": False, "conflict": conflict}) == {"verdict": True, "conflict": True}
                                                               for conflict in conflicts)))
            everything = sorted(instance.rules)
            superset_minimal = instance.is_minimal_conflict(everything)
            rows.append((f"{item_id}-non-minimal-superset-fails", superset_minimal or evaluate(record, "strict", {"feasible": False, "conflict": everything})["conflict"] is False))
            rows.append((f"{item_id}-verdict-only-half", evaluate(record, "strict", {"feasible": False, "conflict": []}) == {"verdict": True, "conflict": False}))
            rows.append((f"{item_id}-claimed-feasible-fails", evaluate(record, "strict", {"feasible": True, "roster": {}}) == {"verdict": False, "conflict": False}))
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
