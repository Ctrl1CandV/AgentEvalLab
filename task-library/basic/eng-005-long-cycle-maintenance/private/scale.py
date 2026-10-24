"""S6 (scale) for eng-005 0.4.0: a large version 2 store, a fixed workload of commands, and checks against the reference.

The store holds 100,000 work orders with a dependency chain 50,000 deep, a ladder of diamonds whose paths number in the
billions, a hub with 2,000 prerequisites, and random older prerequisites elsewhere. The workload lists, shows, adds
dependencies that do and do not close a cycle, completes orders with and without finished prerequisites, creates and
renames. Correctness compares every output and the final store with the reference implementation's; speed compares the
workload's total time with the reference's, best of three interleaved runs on one CPU core.

Sorts use createdAt and id only: both are fixed-format strings, so every reasonable comparison agrees on them.
"""
import json

ORDERS = 100_000
CHAIN = 50_000
LADDER = 32
HUB_PREREQUISITES = 2_000


def order_id(number):
    return f"SC-{number:06d}"


def store(seed):
    """The version 2 store as a dict: the public generator (stages/S6/public/make_store.py) under a hidden seed."""
    import importlib.util
    import sys
    from pathlib import Path
    sys.dont_write_bytecode = True  # the stage directory must keep exactly its declared files
    path = Path(__file__).resolve().parent.parent / "stages" / "S6" / "public" / "make_store.py"
    spec = importlib.util.spec_from_file_location("make_store", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.store(seed, ORDERS, CHAIN, LADDER, HUB_PREREQUISITES)


def workload():
    """(name, arguments, group) of every command, in order. The group says which check its outcome belongs to."""
    return [
        ("list-default", ["list", "--page-size", "100"], "list"),
        ("list-open-by-id-desc", ["list", "--status", "OPEN", "--sort", "id", "--order", "desc", "--page", "41", "--page-size", "100"], "list"),
        ("list-done-by-created-desc", ["list", "--status", "DONE", "--sort", "createdAt", "--order", "desc", "--page", "7", "--page-size", "50"], "list"),
        ("list-past-the-end", ["list", "--sort", "createdAt", "--page", "5000", "--page-size", "100"], "list"),
        ("show-deep", ["show", order_id(CHAIN - 1)], "list"),
        ("cycle-through-chain", ["depends", "add", order_id(1), order_id(CHAIN)], "dependencies"),
        ("cycle-through-ladder", ["depends", "add", order_id(60_001 + 2 * (LADDER - 1)), order_id(60_001)], "dependencies"),
        ("add-past-chain", ["depends", "add", order_id(80_001), order_id(CHAIN)], "dependencies"),
        # Nothing below the ladder's top leads to SC-080002, so the search must visit every rung once, not every path.
        ("add-past-ladder", ["depends", "add", order_id(80_002), order_id(60_001)], "dependencies"),
        ("hub-not-complete", ["update", order_id(69_001), "--status", "DONE"], "status"),
        ("finisher-done", ["update", order_id(69_002), "--status", "DONE"], "status"),
        ("create", ["create", "SC-NEW-1", "Scale check order"], "status"),
        ("new-depends-on-chain", ["depends", "add", "SC-NEW-1", order_id(CHAIN)], "dependencies"),
        ("list-in-progress-after-writes", ["list", "--status", "IN_PROGRESS", "--sort", "id", "--page", "250", "--page-size", "100"], "list"),
        ("rename", ["update", order_id(90_000), "--title", "Renamed at scale"], "status"),
    ]


def outcome(returncode, stdout):
    """What a command's result is compared on: success or the error code; for list and show, the output itself."""
    if returncode != 0:
        try:
            return {"error": json.loads(stdout.strip().splitlines()[-1])["error"]["code"]}
        except (json.JSONDecodeError, KeyError, TypeError, IndexError):
            return {"error": None}
    return {"ok": True}


def listing(stdout):
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def final_state(text):
    """The final store as compared: work orders by id, without the created order's timestamp; events by count, contiguous
    sequence and order ids (types are the implementation's own)."""
    try:
        value = json.loads(text)
        orders = {order["id"]: {key: item for key, item in order.items() if not (order["id"] == "SC-NEW-1" and key == "createdAt")}
                  for order in value["workOrders"]}
        events = value["events"]
        return {"version": value["version"], "orders": orders, "eventOrders": [event.get("orderId") for event in events],
                "contiguous": [event.get("sequence") for event in events] == list(range(1, len(events) + 1))}
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return None
