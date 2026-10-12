#!/usr/bin/env python3
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
UNIVERSE = ["coverage", "per_person_max", "availability"]


def _load(rel):
    with open(os.path.join(PKG, rel), encoding="utf-8") as f:
        return json.load(f)


def _all_subsets(items):
    for r in range(len(items) + 1):
        for c in itertools.combinations(items, r):
            yield frozenset(c)


def _day_options(inst, constraints):
    people = inst["people"]
    if "coverage" in constraints and inst.get("daily_need") is not None:
        need = inst["daily_need"]
        if need > len(people):
            return []
        return [frozenset(c) for c in itertools.combinations(people, need)]
    return list(_all_subsets(people))


def _assignments(inst, constraints):
    opts = _day_options(inst, constraints)
    if not opts:
        return
    for combo in itertools.product(opts, repeat=inst["days"]):
        yield list(combo)


def satisfies(asgn, constraints, inst):
    days = inst["days"]
    if "coverage" in constraints:
        need = inst.get("daily_need")
        if need is None:
            return False
        for d in range(days):
            if len(asgn[d]) != need:
                return False
    if "per_person_max" in constraints:
        mx = inst["per_person_max"]
        for p in inst["people"]:
            if sum(1 for d in range(days) if p in asgn[d]) > mx:
                return False
    if "availability" in constraints:
        for p in inst.get("unavailable", []):
            if any(p in asgn[d] for d in range(days)):
                return False
    return True


def solve(constraints, inst):
    constraints = set(constraints)
    for asgn in _assignments(inst, constraints):
        if satisfies(asgn, constraints, inst):
            return True, asgn
    return False, None


def all_mus(inst):
    unsat = []
    for r in range(len(UNIVERSE) + 1):
        for sub in itertools.combinations(UNIVERSE, r):
            s = set(sub)
            if not solve(s, inst)[0]:
                unsat.append(s)
    mus = [s for s in unsat if not any(t < s for t in unsat)]
    return sorted(sorted(m) for m in mus)


def check_A(inst, ans):
    if not isinstance(ans, dict) or ans.get("feasible") is not False:
        return False, 'answer must declare infeasible'
    cs = ans.get("conflict_set")
    if not isinstance(cs, list) or not all(isinstance(x, str) for x in cs) or len(set(cs)) != len(cs):
        return False, 'conflict_set must contain unique string constraint names'
    mus = all_mus(inst)
    if sorted(set(cs)) in mus:
        return True, 'conflict_set is a minimal unsatisfiable subset'
    return False, f"conflict_set={sorted(set(cs))}  is not a minimal unsatisfiable subset; expected MUS={mus}"


def check_B(inst, ans):
    if not isinstance(ans, dict):
        return False, 'answer must be an object'
    identified = ans.get("gap") == "daily_need"
    if ans.get("clarify") is True:
        question = ans.get("question")
        if identified and ans.get("clarificationTarget") == "daily_need" and isinstance(question, str) and question.strip():
            return True, 'clarification must identify daily_need and include a question'
        return False, 'answer must identify daily_need and provide both branches'
    branches = ans.get("branches")
    if not identified or not isinstance(branches, dict):
        return False, 'both branches must report boolean feasibility'
    i1 = dict(inst, daily_need=1)
    i2 = dict(inst, daily_need=2)
    f1 = solve(UNIVERSE, i1)[0]
    f2 = solve(UNIVERSE, i2)[0]
    b1 = branches.get("1", branches.get(1))
    b2 = branches.get("2", branches.get(2))
    if not isinstance(b1, dict) or not isinstance(b2, dict):
        return False, 'both daily_need branches match the reference feasibility'
    if type(b1.get("feasible")) is bool and type(b2.get("feasible")) is bool and b1.get("feasible") is f1 and b2.get("feasible") is f2:
        return True, f"Both branches match feasibility (daily_need=1: {f1}, daily_need=2: {f2})"
    return False, f"Branch feasibility mismatch (daily_need=1: {f1}, daily_need=2: {f2})"


def check_C(inst, ans):
    if not isinstance(ans, dict) or ans.get("feasible") is not True:
        return False, 'answer must declare feasibility'
    sch = ans.get("schedule")
    if not isinstance(sch, dict) or set(sch) != {str(d) for d in range(inst["days"])}:
        return False, 'schedule must include every day'
    asgn = []
    for d in range(inst["days"]):
        v = sch.get(str(d), sch.get(d))
        if not isinstance(v, list) or not all(isinstance(p, str) and p in inst["people"] for p in v) or len(set(v)) != len(v):
            return False, f"day {d} must contain unique known people"
        asgn.append(frozenset(v))
    if satisfies(asgn, set(UNIVERSE), inst):
        return True, 'assignment must contain unique known people'
    return False, 'schedule satisfies all constraints'


CHECKS = {"A": check_A, "B": check_B, "C": check_C}


def grade(instance_id, ans):
    inst = _load("public/instances.json")["instances"][instance_id]
    return CHECKS[instance_id](inst, ans)


def _old_7day_wo_availability_unsat():
    old = _load("private/oracle.json")["regression_old_7day"]
    inst = {k: old[k] for k in ("people", "days", "daily_need", "per_person_max", "unavailable")}
    return not solve({"coverage", "per_person_max"}, inst)[0]


def self_calibrate():
    rows = []

    def rec(name, expect, got, note=""):
        ok = expect == got
        rows.append((name, expect, got, "OK" if ok else "MISMATCH", note))
        return ok

    allok = True
    instances = _load("public/instances.json")["instances"]
    oracle = _load("private/oracle.json")
    negatives = _load("private/negatives.json")

    # Internal calibration detail.
    allok &= rec("A_infeasible", False, solve(UNIVERSE, instances["A"])[0], "The full constraint set is infeasible")
    allok &= rec("C_feasible", True, solve(UNIVERSE, instances["C"])[0], "The full constraint set has a schedule")
    # Internal calibration detail.
    allok &= rec("A_MUS==oracle", oracle["A"]["minimal_conflict_sets"], all_mus(instances["A"]), "Computed minimal conflict sets match the oracle")
    # Internal calibration detail.
    allok &= rec("regression_old_7day_bug", True, _old_7day_wo_availability_unsat(),
                 "The regression instance remains infeasible without availability")
    # Internal calibration detail.
    for iid in ("A", "B", "C"):
        allok &= rec(f"reference_{iid}_pass", True, grade(iid, oracle["reference_answers"][iid])[0], "Reference answer passes")
    # Internal calibration detail.
    for iid, negs in negatives.items():
        for n in negs:
            allok &= rec(f"neg_{iid}_{n['name']}", False, grade(iid, n["answer"])[0], n.get("why", ""))
    # Internal calibration detail.
    for iid in ("A", "B", "C"):
        allok &= rec(f"empty_{iid}_fail", False, grade(iid, {})[0], "Empty answer is rejected")
    # Internal calibration detail.
    first = [grade(i, oracle["reference_answers"][i])[0] for i in ("A", "B", "C")]
    second = [grade(i, oracle["reference_answers"][i])[0] for i in ("A", "B", "C")]
    allok &= rec("repeatable", first, second, "Repeated evaluation is identical")

    print("Shift-scheduling self-calibration")
    print(f"{'Check':34}{'Expected':>8}{'Actual':>8}  Status     Notes")
    for name, exp, got, verdict, note in rows:
        e = str(exp)
        g = str(got)
        if len(e) > 7:
            e = e[:6] + "…"
        if len(g) > 7:
            g = g[:6] + "…"
        print(f"{name:34}{e:>8}{g:>8}  {verdict:9} {note}")
    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(self_calibrate())
