#!/usr/bin/env python3
"""Success audit of E3 (eng-005), written from the public stage briefs S1-S7 and nothing of the package's private code.
It copies a trajectory's final snapshot, writes stores the hidden checks never used, and runs the candidate CLI in the
bubblewrap sandbox:

- S1 queries: random stores with ties in every sort key, random filters, sorts, orders and pages, against an
  independent model; malformed options are rejected without writing.
- S2/S3/S5 state sequences: random dependency additions (self, duplicate, unknown, cycle-closing through chains) and
  status changes, against an independent model of the rules; every rejection leaves the file byte for byte unchanged
  and follows the error protocol with the stated code.
- S4 migration and events: a random version 1 store migrates on the first successful write only, with one
  state_migrated event and contiguous sequences; reads never write.
- S7 plans: random small stores on 1-3 crews; every plan valid, its cost right, the store untouched, and invalid input
  rejected with the stated codes.

Usage: python3 -I scripts/audits/e3_cli.py <request.json> <result.json>
"""
import glob
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAUNCHER = os.path.join(ROOT, "scripts", "sandbox_exec.py")
STATUSES = ["OPEN", "IN_PROGRESS", "DONE"]
WORDS = ["Inspect", "Repair", "Replace", "Clean", "Test", "Audit"]
THINGS = ["pump", "valve", "reader", "boiler", "panel"]


class Project:
    def __init__(self, snapshot):
        self.directory = tempfile.mkdtemp(prefix="audit-e3-")
        self.root = os.path.join(self.directory, "project")
        shutil.copytree(snapshot, self.root, ignore=shutil.ignore_patterns(".git", "node_modules"))
        self.store = os.path.join(self.root, "data", "work-orders.json")

    def write(self, value):
        with open(self.store, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)

    def raw(self):
        with open(self.store, "rb") as handle:
            return handle.read()

    def load(self):
        return json.loads(self.raw())

    def run(self, args, timeout=30):
        command = [sys.executable, LAUNCHER, "--rw", self.root, "--", "node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/cli.ts", *args]
        try:
            done = subprocess.run(command, cwd=self.root, capture_output=True, text=True, timeout=timeout)
            return done.returncode, done.stdout, done.stderr
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"

    def close(self):
        shutil.rmtree(self.directory, ignore_errors=True)


def error_code(code, stdout, stderr):
    """S5: one JSON line on stdout, {"ok": false, "error": {"code", "message"}}, exit 2, no stack trace."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    if code != 2 or len(lines) != 1 or "    at " in stderr:
        return None
    try:
        value = json.loads(lines[0])
    except json.JSONDecodeError:
        return None
    if value.get("ok") is not False or not isinstance(value.get("error"), dict) or not isinstance(value["error"].get("message"), str):
        return None
    return value["error"].get("code")


def random_orders(rng, count, prefix="AU", plan=False):
    moments = [f"2026-02-{day:02d}T0{hour}:00:00.000Z" for day in (1, 2, 3) for hour in (8, 9)]
    orders = []
    for index in range(1, count + 1):
        order = {"id": f"{prefix}-{index:03d}", "title": f"{rng.choice(WORDS)} {rng.choice(THINGS)} {rng.randrange(1, 4)}",
                 "status": rng.choice(STATUSES), "createdAt": rng.choice(moments), "description": rng.choice(["", "noted"]), "dependsOn": []}
        if plan:
            order["hours"] = rng.randrange(1, 6)
            order["priority"] = rng.randrange(1, 6)
        orders.append(order)
    rng.shuffle(orders)
    return orders


def expected_page(orders, status, sort, order, page, size):
    rows = [item for item in orders if status is None or item["status"] == status]
    rows.sort(key=lambda item: item["id"])
    rows.sort(key=lambda item: item[sort], reverse=order == "desc")
    total = len(rows)
    return {"total": total, "page": page, "pageSize": size, "pages": math.ceil(total / size), "items": [item["id"] for item in rows[(page - 1) * size: page * size]]}


def audit_queries(project, rng):
    problems = []
    orders = random_orders(rng, 23)
    project.write({"version": 2, "workOrders": orders, "events": []})
    for _ in range(40):
        status = rng.choice([None, *STATUSES])
        sort, order = rng.choice(["createdAt", "title", "id"]), rng.choice(["asc", "desc"])
        size = rng.choice([1, 2, 3, 5, 7, 100])
        expected = expected_page(orders, status, sort, order, 1, size)
        page = rng.randrange(1, max(1, expected["pages"]) + 2)
        expected = expected_page(orders, status, sort, order, page, size)
        args = ["list", "--sort", sort, "--order", order, "--page", str(page), "--page-size", str(size)] + (["--status", status] if status else [])
        code, stdout, _ = project.run(args)
        try:
            got = json.loads(stdout)
            shape = {"total": got["total"], "page": got["page"], "pageSize": got["pageSize"], "pages": got["pages"], "items": [item["id"] for item in got["items"]]}
        except (json.JSONDecodeError, KeyError, TypeError):
            shape = None
        if expected["total"] == 0 and shape:
            shape["pages"] = expected["pages"]  # the brief does not fix pages for an empty result
        if code != 0 or shape != expected:
            problems.append(f"list {' '.join(args)}: got {shape} expected {expected}")
    before = project.raw()
    for args in (["--page-size", "0"], ["--page-size", "101"], ["--page", "0"], ["--page", "1.5"], ["--page-size", "two"], ["--sort", "status"],
                 ["--order", "up"], ["--status", "CLOSED"], ["--colour", "red"]):
        code, stdout, stderr = project.run(["list", *args])
        if code == 0 or project.raw() != before:
            problems.append(f"list {' '.join(args)} accepted or wrote")
        elif error_code(code, stdout, stderr) != "INVALID_ARGUMENT":
            problems.append(f"list {' '.join(args)}: error {stdout.strip()[:120]} (expected INVALID_ARGUMENT)")
    return problems


def reaches(orders, start, goal):
    """Does start depend, directly or not, on goal?"""
    seen, stack = set(), [start]
    while stack:
        current = stack.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(orders[current]["dependsOn"])
    return False


def audit_sequences(project, rng):
    problems = []
    orders = random_orders(rng, 14)
    by_id = {order["id"]: order for order in orders}
    ids = sorted(by_id)
    # A chain to close cycles through: each order of the chain depends on the one before.
    for before, after in zip(ids[:6], ids[1:7]):
        by_id[after]["dependsOn"].append(before)
    for order in orders:  # a consistent start: an order is DONE only when its prerequisites are DONE
        pass
    for order_id in ids:
        if by_id[order_id]["status"] == "DONE" and any(by_id[item]["status"] != "DONE" for item in by_id[order_id]["dependsOn"]):
            by_id[order_id]["status"] = "IN_PROGRESS"
    project.write({"version": 2, "workOrders": orders, "events": []})
    model = {order_id: {"status": by_id[order_id]["status"], "dependsOn": list(by_id[order_id]["dependsOn"])} for order_id in ids}
    for _ in range(60):
        before = project.raw()
        if rng.random() < 0.55:
            kind = rng.choice(["self", "unknown", "duplicate", "cycle", "random", "random"])
            target = rng.choice(ids)
            if kind == "self":
                prerequisite, expect = target, {"SELF_DEPENDENCY"}
            elif kind == "unknown":
                prerequisite, expect = "AU-999", {"NOT_FOUND"}
            elif kind == "duplicate" and model[target]["dependsOn"]:
                prerequisite, expect = rng.choice(model[target]["dependsOn"]), None  # rejected; the brief names no code
            elif kind == "cycle":
                target, prerequisite = ids[0], ids[6]  # closes the chain
                expect = {"DEPENDENCY_CYCLE"} if reaches(model, prerequisite, target) else "ok"
            else:
                prerequisite = rng.choice(ids)
                if prerequisite == target:
                    expect = {"SELF_DEPENDENCY"}
                elif prerequisite in model[target]["dependsOn"]:
                    expect = None
                elif reaches(model, prerequisite, target):
                    expect = {"DEPENDENCY_CYCLE"}
                else:
                    expect = "ok"
            if kind == "duplicate" and not model[target]["dependsOn"]:
                continue
            args = ["depends", "add", target, prerequisite]
        else:
            target = rng.choice(ids)
            current = model[target]["status"]
            wanted = rng.choice([status for status in STATUSES if status != current])
            if STATUSES.index(wanted) != STATUSES.index(current) + 1:
                expect = {"INVALID_STATUS_TRANSITION"} if wanted != "DONE" or all(model[item]["status"] == "DONE" for item in model[target]["dependsOn"]) else \
                    {"INVALID_STATUS_TRANSITION", "DEPENDENCY_NOT_COMPLETE"}
            elif wanted == "DONE" and any(model[item]["status"] != "DONE" for item in model[target]["dependsOn"]):
                expect = {"DEPENDENCY_NOT_COMPLETE"}
            else:
                expect = "ok"
            args = ["update", target, "--status", wanted]
        code, stdout, stderr = project.run(args)
        if expect == "ok":
            if code != 0:
                problems.append(f"{' '.join(args)} refused: {stdout.strip()[:160]}")
                continue
            if args[0] == "depends":
                model[target]["dependsOn"].append(prerequisite)
            else:
                model[target]["status"] = wanted
        else:
            got = error_code(code, stdout, stderr)
            if code == 0:
                problems.append(f"{' '.join(args)} accepted (expected {sorted(expect) if expect else 'a rejection'})")
                return problems  # the model and the store have diverged
            if project.raw() != before:
                problems.append(f"{' '.join(args)} rejected but wrote the store")
            if got is None:
                problems.append(f"{' '.join(args)}: not the error protocol: exit {code}, {stdout.strip()[:120]!r}")
            elif expect and got not in expect:
                problems.append(f"{' '.join(args)}: code {got}, expected {sorted(expect)}")
        stored = {order["id"]: {"status": order["status"], "dependsOn": sorted(order.get("dependsOn", []))} for order in project.load()["workOrders"]}
        if stored != {key: {"status": value["status"], "dependsOn": sorted(value["dependsOn"])} for key, value in model.items()}:
            problems.append(f"after {' '.join(args)} the store differs from the model")
            return problems
    return problems


def audit_migration(project, rng):
    problems = []
    orders = random_orders(rng, 5, prefix="MG")
    for order in orders[::2]:
        order.pop("dependsOn")
    project.write({"version": 1, "workOrders": orders})
    original = project.raw()
    for args in (["list"], ["show", orders[0]["id"]], ["export", "json"]):
        project.run(args)
    if project.raw() != original:
        problems.append("a read command rewrote the version 1 store")
    code, _, _ = project.run(["create", "MG-NEW", "Migrated create"])
    first = project.load() if code == 0 else None
    code2, _, _ = project.run(["update", orders[1]["id"], "--status", STATUSES[min(2, STATUSES.index(orders[1]["status"]) + 1)]]) \
        if orders[1]["status"] != "DONE" else project.run(["create", "MG-NEW2", "Second create"])
    second = project.load()
    if code != 0 or not first or first.get("version") != 2:
        return problems + ["the first successful write did not migrate to version 2"]
    events = second.get("events", [])
    migrations = [event for event in events if event.get("type") == "state_migrated" or (event.get("orderId") is None and event.get("sequence") == 1)]
    if len(migrations) != 1 or migrations[0].get("orderId") is not None:
        problems.append(f"expected exactly one migration event with orderId null, got {migrations}")
    if [event.get("sequence") for event in events] != list(range(1, len(events) + 1)) or len(events) != 3:
        problems.append(f"events after two writes: {[(event.get('sequence'), event.get('type'), event.get('orderId')) for event in events]}")
    if any(not isinstance(event.get("at"), str) or "T" not in event.get("at", "") for event in events):
        problems.append("an event without an ISO timestamp")
    kept = {order["id"]: order for order in second["workOrders"]}
    for order in orders:
        stored = kept.get(order["id"], {})
        if any(stored.get(key) != value for key, value in order.items() if key not in ("status", "dependsOn")):
            problems.append(f"{order['id']} lost or changed a field in migration")
    return problems


def valid_plan(store, crews, output):
    """S7: every not-DONE order once, its duration, one order at a time per crew, prerequisites not DONE ended first, and
    the cost reported right."""
    orders = {order["id"]: order for order in store["workOrders"]}
    work = {key: order for key, order in orders.items() if order["status"] != "DONE"}
    try:
        schedule = {entry["id"]: entry for entry in output["schedule"]}
        if output["crews"] != crews or set(schedule) != set(work) or len(output["schedule"]) != len(work):
            return "the schedule does not hold every not-DONE order exactly once"
        for key, entry in schedule.items():
            if not (1 <= entry["crew"] <= crews) or entry["start"] < 0 or entry["end"] - entry["start"] != work[key].get("hours", 1):
                return f"{key}: crew or duration wrong"
            for item in work[key].get("dependsOn", []):
                if item in work and schedule[item]["end"] > entry["start"]:
                    return f"{key} starts before its prerequisite {item} ends"
        for crew in range(1, crews + 1):
            spans = sorted((entry["start"], entry["end"]) for entry in schedule.values() if entry["crew"] == crew)
            if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
                return f"crew {crew} overlaps"
        cost = sum(work[key].get("priority", 1) * entry["end"] for key, entry in schedule.items())
        if output["cost"] != cost:
            return f"reported cost {output['cost']}, recomputed {cost}"
    except (KeyError, TypeError):
        return "malformed plan"
    return None


def audit_plan(project, rng):
    problems = []
    for index in range(12):
        orders = random_orders(rng, rng.randrange(3, 13), prefix="PL", plan=True)
        ids = sorted(order["id"] for order in orders)
        by_id = {order["id"]: order for order in orders}
        for position, order_id in enumerate(ids):
            for other in rng.sample(ids[:position], k=min(position, rng.randrange(0, 3))):
                by_id[order_id]["dependsOn"].append(other)
        store = {"version": 2, "workOrders": orders, "events": []}
        project.write(store)
        before = project.raw()
        crews = rng.randrange(1, 4)
        code, stdout, _ = project.run(["plan", "--crews", str(crews)], timeout=20)
        if project.raw() != before:
            problems.append(f"store {index}: plan wrote the store")
        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            problems.append(f"store {index}: no JSON plan (exit {code})")
            continue
        issue = valid_plan(store, crews, output)
        if issue:
            problems.append(f"store {index} on {crews} crews: {issue}")
    project.write({"version": 2, "workOrders": random_orders(rng, 3, prefix="PL", plan=True), "events": []})
    for args, code_expected in ((["plan"], "INVALID_ARGUMENT"), (["plan", "--crews", "0"], "INVALID_ARGUMENT"), (["plan", "--crews", "51"], "INVALID_ARGUMENT"),
                                (["plan", "--crews", "two"], "INVALID_ARGUMENT"), (["plan", "--crews", "2", "--fast"], "INVALID_ARGUMENT")):
        code, stdout, stderr = project.run(args)
        if error_code(code, stdout, stderr) != code_expected:
            problems.append(f"{' '.join(args)}: {stdout.strip()[:120]!r} (expected {code_expected})")
    for field, value in (("hours", 0), ("priority", 6), ("hours", 1.5)):
        orders = random_orders(rng, 3, prefix="PL", plan=True)
        orders[1][field] = value
        project.write({"version": 2, "workOrders": orders, "events": []})
        code, stdout, stderr = project.run(["plan", "--crews", "2"])
        if error_code(code, stdout, stderr) != "STORE_INVALID":
            problems.append(f"{field} {value}: {stdout.strip()[:120]!r} (expected STORE_INVALID)")
    orders = random_orders(rng, 3, prefix="PL", plan=True)
    for order in orders:
        order["status"], order["dependsOn"] = "OPEN", []
    project.write({"version": 2, "workOrders": orders, "events": []})
    project.run(["update", orders[0]["id"], "--status", "IN_PROGRESS"])
    kept = {order["id"]: order for order in project.load()["workOrders"]}
    if any((kept[order["id"]].get("hours"), kept[order["id"]].get("priority")) != (order["hours"], order["priority"]) for order in orders):
        problems.append("an update lost hours or priority")
    return problems


def final_snapshot(trial):
    """The last graded snapshot of the trajectory, and the stage it belongs to."""
    trajectory = json.load(open(os.path.join(trial, "trajectory.json"))) if os.path.exists(os.path.join(trial, "trajectory.json")) else None
    snapshots = sorted(glob.glob(os.path.join(trial, "snapshots", "S*-cycle-*")), key=lambda path: (int(os.path.basename(path)[1:].split("-")[0]), path))
    return (snapshots[-1], os.path.basename(snapshots[-1]).split("-")[0]) if snapshots else (None, None)


def grader_groups(trial, stage):
    """The checks of the final snapshot's grade, by requirement group."""
    groups = {"QUERY": "query.", "DEPENDENCY": "dependency.", "NO_MUTATION": "failure.", "MIGRATION": "migration.", "ERRORS": "errors.", "PLAN": "plan.valid"}
    runs = []
    for path in glob.glob(os.path.join(trial, "score-runs", "*", "score.json")):
        score = json.load(open(path))
        if score.get("stageId") == stage:
            runs.append((score["createdAt"], os.path.dirname(path)))
    if not runs:
        return {}
    result = json.load(open(os.path.join(max(runs)[1], "grader", "result.json")))
    checks = {check["id"]: check["status"] == "pass" for check in result["checks"]}
    return {group: all(passed for name, passed in checks.items() if name.startswith(prefix)) if any(name.startswith(prefix) for name in checks) else None
            for group, prefix in groups.items()} | {"PLAN": all(checks.get(name, False) for name in ("plan.valid-small", "plan.valid-large", "plan.read-only", "plan.errors", "plan.fields-preserved"))
                                                   if any(name.startswith("plan.") for name in checks) else None}


def main():
    request = json.load(open(sys.argv[1]))
    findings = []
    for trial in request["trials"]:
        snapshot, stage = final_snapshot(trial["directory"])
        if not snapshot:
            continue
        groups = grader_groups(trial["directory"], stage)
        rng = random.Random(f"e3-audit-{os.path.basename(trial['directory'])}")
        units = [("S1 queries on random stores", ["QUERY"], audit_queries), ("S2/S3/S5 dependency and status sequences", ["DEPENDENCY", "NO_MUTATION", "ERRORS"], audit_sequences),
                 ("S4 migration and events", ["MIGRATION"], audit_migration)]
        if stage == "S7":
            units.append(("S7 plans on random stores", ["PLAN"], audit_plan))
        for unit, group_names, function in units:
            project = Project(snapshot)
            try:
                problems = function(project, rng)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                problems = [f"the store or an output became unreadable: {type(error).__name__}: {error}"]
            finally:
                project.close()
            known = [groups.get(name) for name in group_names if groups.get(name) is not None]
            grader = "pass" if known and all(known) else "fail" if known else "n/a"
            verdict = ("true pass" if not problems else "false pass") if grader == "pass" else ("note" if not problems else "true fail")
            findings.append({"trial": trial["directory"], "label": trial["label"], "item": stage, "unit": unit, "grader": grader, "verdict": verdict,
                             "detail": "; ".join(problems[:4]) + (f" (+{len(problems) - 4} more)" if len(problems) > 4 else "")})
    notes = ["Each unit runs on a fresh copy of the trajectory's final snapshot, in the sandbox, with stores generated for the audit (seeded per trial).",
             "Where a brief leaves something open (the code of a duplicate dependency, the pages of an empty result, the code when a skipped transition also lacks finished prerequisites), the audit accepts any of the readings.",
             "A unit whose grader checks failed but where the audit found no defect is a note, not a false fail: the audit uses other inputs than the hidden checks."]
    json.dump({"findings": findings, "notes": notes}, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
