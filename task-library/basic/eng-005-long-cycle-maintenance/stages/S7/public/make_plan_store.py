#!/usr/bin/env python3
"""Writes a sample store for S7: python3 public/make_plan_store.py OUTPUT.json [--kind KIND] [--seed SEED]

KIND is one of tiny (7 orders, 2 crews), small (9 orders, 3 crews), chains (40 orders in chains, 1 crew), general
(300 orders, 5 crews) and large (3,000 orders, 16 crews); the crews are the number the hidden checks plan with. Open
orders carry hours and priority (absent when 1, as earlier data may be), some depend on others, some on DONE orders,
and some are long, low-priority orders that short, high-priority ones depend on. A few orders are DONE.
"""
import argparse
import json
import random

STORES = {
    "tiny": {"orders": 7, "crews": 2, "dependencies": "dag"},
    "small": {"orders": 9, "crews": 3, "dependencies": "dag"},
    "chains": {"orders": 40, "crews": 1, "dependencies": "chains"},
    "general": {"orders": 300, "crews": 5, "dependencies": "dag"},
    "large": {"orders": 3000, "crews": 16, "dependencies": "dag"},
}


def order_id(number):
    return f"PL-{number:05d}"


def store(name, key):
    """A version 2 store for one planning case: the open orders of the case, some IN_PROGRESS, and DONE orders that
    some of them depend on (which impose nothing). Ids are shuffled against the dependency order, so that id order
    is not a good plan."""
    spec = STORES[name]
    rng = random.Random(key)
    count = spec["orders"]
    done = max(2, count // 8)
    numbers = rng.sample(range(1, 10 * (count + done)), count + done)
    finished, open_ids = numbers[:done], numbers[done:]
    orders = []
    for index, number in enumerate(finished):
        orders.append({"id": order_id(number), "title": f"Finished work {index + 1}", "status": "DONE",
                       "createdAt": f"2026-08-{1 + index % 28:02d}T08:00:00.000Z", "description": "", "dependsOn": [],
                       "hours": rng.randrange(1, 9), "priority": rng.randrange(1, 6)})
    # Open orders in a hidden topological order: position i may depend on earlier positions only.
    for position, number in enumerate(open_ids):
        hours = rng.choice([1, 1, 2, 2, 3, 4, 5, 6, 8, 12, 16])
        priority = rng.choice([1, 1, 2, 2, 3, 3, 4, 5])
        order = {"id": order_id(number), "title": f"Planned work {position + 1}", "status": "IN_PROGRESS" if rng.random() < 0.1 else "OPEN",
                 "createdAt": f"2026-09-{1 + position % 28:02d}T{8 + position % 10:02d}:00:00.000Z", "description": "", "dependsOn": [],
                 "hours": hours, "priority": priority}
        orders.append(order)
    open_orders = orders[done:]
    # Gateways: long, low-priority orders that a few short, high-priority ones depend on. The greedy plan, which looks
    # only at each ready order's own priority per hour, starts them late.
    gateways = set()
    if spec["dependencies"] != "none":
        for position, order in enumerate(open_orders[:-1]):
            if rng.random() < 0.18:
                order["hours"], order["priority"] = rng.choice([6, 8, 12, 16]), 1
                gateways.add(position)
    if spec["dependencies"] == "dag":
        for position, order in enumerate(open_orders):
            if position and rng.random() < 0.7:
                # Mostly recent predecessors, sometimes far ones: chains, fans and joins.
                pool = open_orders[max(0, position - 12):position] if rng.random() < 0.8 else open_orders[:position]
                order["dependsOn"] = sorted({other["id"] for other in rng.sample(pool, min(len(pool), rng.choice([1, 1, 1, 2, 3])))})
            if rng.random() < 0.15:
                order["dependsOn"] = sorted(set(order["dependsOn"]) | {rng.choice(orders[:done])["id"]})
        for position in sorted(gateways):
            later = open_orders[position + 1:position + 15]
            for follower in rng.sample(later, min(len(later), rng.randrange(2, 5))):
                follower["dependsOn"] = sorted(set(follower["dependsOn"]) | {open_orders[position]["id"]})
                follower["hours"], follower["priority"] = rng.choice([1, 1, 2, 3]), rng.choice([4, 5])
    elif spec["dependencies"] == "chains":
        heads = rng.sample(range(len(open_orders)), 6)
        chains = [[index] for index in sorted(heads)]
        for index in range(len(open_orders)):
            if index in heads:
                continue
            chain = rng.choice(chains)
            chains[chains.index(chain)] = chain + [index]
        for chain in chains:
            for before, after in zip(chain, chain[1:]):
                open_orders[after]["dependsOn"] = [open_orders[before]["id"]]
        open_orders[chains[0][0]]["dependsOn"] = [orders[0]["id"]]  # a DONE prerequisite imposes nothing
    # Some orders omit hours or priority when it is 1, as earlier data does.
    for order in open_orders:
        if order["hours"] == 1 and rng.random() < 0.5:
            del order["hours"]
        if order["priority"] == 1 and rng.random() < 0.5:
            del order["priority"]
    rng.shuffle(orders)
    return {"version": 2, "workOrders": orders, "events": [{"sequence": 1, "type": "state_migrated", "orderId": None, "at": "2026-09-01T00:00:00.000Z"}]}


def main():
    parser = argparse.ArgumentParser(description="Write a sample S7 store.")
    parser.add_argument("output")
    parser.add_argument("--kind", choices=sorted(STORES), default="general")
    parser.add_argument("--seed", default="public")
    args = parser.parse_args()
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(store(args.kind, f"{args.seed}:{args.kind}"), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"{args.output}: {STORES[args.kind]['orders']} open orders; the hidden checks plan this kind with --crews {STORES[args.kind]['crews']}")


if __name__ == "__main__":
    main()
