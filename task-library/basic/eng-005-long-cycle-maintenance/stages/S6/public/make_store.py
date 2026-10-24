#!/usr/bin/env python3
"""Writes a large version 2 work-order store for S6: python3 public/make_store.py OUTPUT.json [--seed SEED]

100,000 work orders: a dependency chain 50,000 orders deep (SC-000002 depends on SC-000001, and so on), a ladder of
paired orders where each order depends on both orders of the level below (SC-060001 to SC-060064), an order with
2,001 prerequisites (SC-069001), and random prerequisites among the later orders.
"""
import argparse
import datetime
import json
import random

VERBS = ["Inspect", "Repair", "Replace", "Calibrate", "Clean", "Test", "Service", "Audit"]
THINGS = ["pump", "valve", "reader", "boiler", "panel", "fan", "sensor", "lift", "door", "meter"]


def order_id(number):
    return f"SC-{number:06d}"


def store(seed, orders_count=100_000, chain=50_000, ladder_levels=32, hub_prerequisites=2_000):
    rng = random.Random(seed)
    moment = datetime.datetime(2024, 1, 1)
    orders = []
    for number in range(1, orders_count + 1):
        if rng.random() < 0.7:
            moment += datetime.timedelta(seconds=rng.randrange(1, 400))
        status = rng.choices(["OPEN", "IN_PROGRESS", "DONE"], [4, 3, 3])[0]
        orders.append({"id": order_id(number), "title": f"{rng.choice(VERBS)} {rng.choice(THINGS)} {rng.randrange(1, 500)}",
                       "status": status, "createdAt": moment.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                       "description": "" if rng.random() < 0.3 else f"Reported by site {rng.randrange(1, 90)}", "dependsOn": []})
    for number in range(2, chain + 1):
        orders[number - 1]["dependsOn"].append(order_id(number - 1))
    ladder = [(order_id(60_001 + 2 * level), order_id(60_002 + 2 * level)) for level in range(ladder_levels)]
    for level in range(ladder_levels - 1):
        for upper in ladder[level]:
            orders[int(upper[3:]) - 1]["dependsOn"] = list(ladder[level + 1])
    done = [order for order in orders[70_000:] if order["status"] == "DONE"]
    hub, finisher = orders[69_000], orders[69_001]
    hub["status"] = finisher["status"] = "IN_PROGRESS"
    hub["dependsOn"] = [order["id"] for order in done[:hub_prerequisites]] + [order_id(69_500)]
    orders[69_499]["status"] = "OPEN"
    finisher["dependsOn"] = [order["id"] for order in done[hub_prerequisites:hub_prerequisites + 500]]
    for number in range(70_100, orders_count + 1):
        if rng.random() < 0.5:
            orders[number - 1]["dependsOn"] = sorted({order_id(rng.randrange(70_000, number)) for _ in range(rng.randrange(1, 4))})
    events = [{"sequence": 1, "type": "state_migrated", "orderId": None, "at": "2025-01-01T00:00:00.000Z"}]
    for sequence in range(2, 1_001):
        events.append({"sequence": sequence, "type": "updated", "orderId": order_id(rng.randrange(1, orders_count + 1)), "at": "2025-01-02T00:00:00.000Z"})
    return {"version": 2, "workOrders": orders, "events": events}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--seed", default="eng005-scale-public")
    args = parser.parse_args()
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(store(args.seed), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
