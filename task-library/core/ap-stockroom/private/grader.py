#!/usr/bin/env python3
"""Grades AP stockroom trials by replaying the simulator's command log (`simulatorRef`) on a fresh state of the item's
scenario. Days the model did not reach are advanced with no orders, so the profit is always defined; the run counts as
a valid delivery (`completed`, critical) only when the model itself ended day 40. Raw values: `profit` (the headline,
normalised per item through the myopic and strong policies' profits, uncapped), the hindsight `bound` and the `regret`
to it, and the hard-constraint counts. Hard constraints (invalid actions, duplicate orders, units refused for lack of
capacity) are recorded as non-critical checks; their cost is their effect on the profit (rejected commands do nothing,
duplicates and refused units are paid for).

Grader 1.1.0 (task 0.2.0): the `day` command (orders and the end of the day in one call) replays like its parts;
`daysManaged` counts the days the model itself ended, whichever command ended them.

Usage: grader.py --request REQUEST --result RESULT | --self-calibrate
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stockroom as sr  # noqa: E402
import policies  # noqa: E402

TASK_ID = "ap-stockroom"
TASK_VERSION = "0.2.0"
GRADER_VERSION = "1.1.0"


def items():
    with open(os.path.join(HERE, "items.json"), encoding="utf-8") as handle:
        return json.load(handle)


def grade(item_id, log_text):
    world = sr.scenario(items()[item_id]["seed"])
    requests = []
    for line in log_text.splitlines():
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(request, dict):
            requests.append(request)
    own, _ = sr.replay(world, requests, finish=False)
    days_managed = len(own["history"])
    state, managed = sr.replay(world, requests)
    result = sr.result(world, state)
    bound = items()[item_id]["bound"]
    checks = {"completed": managed, "no-invalid-actions": result["invalid_actions"] == 0, "no-duplicate-orders": result["duplicate_orders"] == 0,
              "no-overflow": result["overflow_units"] == 0}
    metrics = {"profit": result["profit"], "bound": bound, "regret": round(bound - result["profit"], 2), "invalidActions": result["invalid_actions"],
               "duplicateOrders": result["duplicate_orders"], "overflowUnits": result["overflow_units"], "lostUnits": result["lost_units"],
               "daysManaged": days_managed}
    return checks, metrics, result


REQUIREMENTS = {"completed": "REQ-COMPLETED", "no-invalid-actions": "REQ-NO-INVALID", "no-duplicate-orders": "REQ-NO-DUPLICATES", "no-overflow": "REQ-NO-OVERFLOW"}


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=1)
        handle.write("\n")


def grade_request(request_path, result_path):
    with open(request_path, encoding="utf-8") as handle:
        request = json.load(handle)
    item_id = request["context"].get("itemId")
    if item_id not in items():
        raise ValueError("unknown item")
    log_text = ""
    if request.get("simulatorRef"):
        with open(os.path.join(request["evidenceRoot"], request["simulatorRef"]), encoding="utf-8") as handle:
            log_text = handle.read()
    checks, metrics, result = grade(item_id, log_text)
    write_json(os.path.join(request["evidenceRoot"], "run.json"), {"itemId": item_id, "result": result, "metrics": metrics})
    write_json(result_path, {"schemaVersion": 2, "requestId": request["requestId"], "taskId": TASK_ID, "taskVersion": TASK_VERSION,
                             "graderVersion": GRADER_VERSION, "gradingStatus": "completed",
                             "checks": [{"id": check, "requirementId": REQUIREMENTS[check], "status": "pass" if ok else "fail", "evidenceRefs": ["run.json"]}
                                        for check, ok in checks.items()],
                             "dimensions": [], "unscoredCheckIds": [], "reason": None, "error": None,
                             "metrics": [{"id": name, "value": value} for name, value in metrics.items()]})


def self_calibrate():
    """Per item: the myopic and strong policies' logs replay to their anchors, the strong policy beats the myopic one by
    at least 0.3 of the way to the bound and stays below the bound; an empty log is incomplete; duplicate orders, invalid
    orders and overflowing deliveries are counted. One item also runs through the simulator's command-line protocol."""
    rows = []
    catalogue = items()
    for item_id, entry in sorted(catalogue.items()):
        world = sr.scenario(entry["seed"])
        myopic_log, _ = policies.run_policy(world, policies.myopic())
        strong_log, _ = policies.run_policy(world, policies.strong(policies.public_parameters(world), *entry["setting"]))
        _, myopic_metrics, _ = grade(item_id, "\n".join(json.dumps(request) for request in myopic_log))
        checks, strong_metrics, _ = grade(item_id, "\n".join(json.dumps(request) for request in strong_log))
        gap = (strong_metrics["profit"] - myopic_metrics["profit"]) / (entry["bound"] - myopic_metrics["profit"])
        rows.append((f"{item_id} anchors replay", abs(myopic_metrics["profit"] - entry["myopic"]) < 0.01 and abs(strong_metrics["profit"] - entry["strong"]) < 0.01))
        rows.append((f"{item_id} gap >= 0.3 and strong below the bound", gap >= 0.3 and strong_metrics["profit"] < entry["bound"]))
        # The strong policy is a heuristic: delays can bunch its imports past the capacity; that is recorded, not required.
        rows.append((f"{item_id} strong run complete, no invalid actions or duplicates", checks["completed"] and checks["no-invalid-actions"] and checks["no-duplicate-orders"]))
        empty, empty_metrics, _ = grade(item_id, "")
        rows.append((f"{item_id} null agent incomplete", not empty["completed"] and empty_metrics["daysManaged"] == 0))
        product = min(world["products"], key=lambda entry: entry["cost"])["name"]
        twice = [{"command": "order", "arguments": {"product": product, "supplier": "local", "quantity": 5, "ref": f"d{index}"}} for index in range(3)]
        duplicate, duplicate_metrics, _ = grade(item_id, "\n".join(json.dumps(request) for request in twice))
        rows.append((f"{item_id} duplicates counted", not duplicate["no-duplicate-orders"] and duplicate_metrics["duplicateOrders"] >= 1))
        invalid = [{"command": "order", "arguments": {"product": "Nothing", "supplier": "local", "quantity": 5, "ref": "x"}},
                   {"command": "order", "arguments": {"product": product, "supplier": "import", "quantity": 3, "ref": "y"}}]
        bad, bad_metrics, _ = grade(item_id, "\n".join(json.dumps(request) for request in invalid))
        rows.append((f"{item_id} invalid actions counted", not bad["no-invalid-actions"] and bad_metrics["invalidActions"] >= 1))
        # More than the free capacity, even after day 1's sales: units are refused the next morning.
        excess = world["capacity"] - sum(entry["start"] for entry in world["products"]) + 2 * sum(entry["base"] for entry in world["products"])
        flood = [{"command": "order", "arguments": {"product": product, "supplier": "local", "quantity": excess, "ref": "f"}}]
        over, over_metrics, _ = grade(item_id, "\n".join(json.dumps(request) for request in flood))
        rows.append((f"{item_id} overflow counted", not over["no-overflow"] and over_metrics["overflowUnits"] > 0))
        print(f"{item_id}: myopic {myopic_metrics['profit']}, strong {strong_metrics['profit']}, bound {entry['bound']}, gap {gap:.2f}, "
              f"strong overflow {strong_metrics['overflowUnits']} units, lost {strong_metrics['lostUnits']}", flush=True)
    # The command-line protocol on the first item: the myopic policy's commands, one process each, give the same profit.
    item_id = sorted(catalogue)[0]
    world = sr.scenario(catalogue[item_id]["seed"])
    myopic_log, _ = policies.run_policy(world, policies.myopic())
    with tempfile.TemporaryDirectory(prefix="ap-protocol-") as state:
        for request in myopic_log:
            subprocess.run([sys.executable, os.path.join(HERE, "stockroom.py"), "--item", item_id, "--state", state], input=json.dumps(request) + "\n",
                           capture_output=True, text=True, check=True)
        with open(os.path.join(state, "log.jsonl"), encoding="utf-8") as handle:
            _, protocol_metrics, _ = grade(item_id, handle.read())
    rows.append((f"{item_id} command-line protocol matches", abs(protocol_metrics["profit"] - catalogue[item_id]["myopic"]) < 0.01))
    # The `day` command: the myopic policy issued as one call per day gives, through the command line, the profit its
    # in-process replay gives, and ends all 40 days; a malformed `day` is an invalid action and ends no day.
    state, day_log, decide = sr.fresh(world), [], policies.myopic()
    while not state["done"]:
        request = {"command": "day", "arguments": {"orders": decide(sr.observe(world, state))}}
        sr.apply(world, state, request)
        day_log.append(request)
    in_process = sr.result(world, state)["profit"]
    with tempfile.TemporaryDirectory(prefix="ap-day-") as directory:
        for request in day_log:
            subprocess.run([sys.executable, os.path.join(HERE, "stockroom.py"), "--item", item_id, "--state", directory], input=json.dumps(request) + "\n",
                           capture_output=True, text=True, check=True)
        with open(os.path.join(directory, "log.jsonl"), encoding="utf-8") as handle:
            day_checks, day_metrics, _ = grade(item_id, handle.read())
    rows.append((f"{item_id} day command: command line equals in-process, 40 days managed",
                 abs(day_metrics["profit"] - in_process) < 0.01 and day_checks["completed"] and day_metrics["daysManaged"] == 40))
    bad_checks, bad_metrics, _ = grade(item_id, json.dumps({"command": "day", "arguments": {"orders": "all"}}))
    rows.append((f"{item_id} malformed day: invalid, no day ended", not bad_checks["no-invalid-actions"] and bad_metrics["daysManaged"] == 0))
    failed = [name for name, ok in rows if not ok]
    for name in failed:
        print(f"FAIL: {name}")
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
