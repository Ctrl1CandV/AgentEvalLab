#!/usr/bin/env python3
"""Calibration candidate: Clarke-Wright savings, run separately for refrigerated and other customers, then routes
assigned to vans (refrigerated routes to refrigerated vans). A typical medium-quality plan."""
import json
import math
import sys


def solve(instance):
    depot = tuple(instance["depot"])
    customers = {customer["id"]: customer for customer in instance["customers"]}
    point = {cid: (customer["x"], customer["y"]) for cid, customer in customers.items()}

    def dist(a, b):
        pa = depot if a is None else point[a]
        pb = depot if b is None else point[b]
        return math.hypot(pa[0] - pb[0], pa[1] - pb[1])

    def duration(route):
        stops = [None] + route + [None]
        return sum(dist(stops[i], stops[i + 1]) for i in range(len(stops) - 1)) / instance["speed"] + sum(customers[c]["service"] for c in route)

    capacity = min(van["capacity"] for van in instance["vans"])

    def savings_routes(ids):
        routes = {cid: [cid] for cid in ids}
        owner = {cid: cid for cid in ids}
        pairs = sorted(((dist(None, a) + dist(None, b) - dist(a, b), a, b) for i, a in enumerate(ids) for b in ids[i + 1:]), reverse=True)
        for saving, a, b in pairs:
            if saving <= 0:
                break
            ra, rb = owner[a], owner[b]
            if ra == rb:
                continue
            left, right = routes[ra], routes[rb]
            if left[-1] == a and right[0] == b:
                merged = left + right
            elif left[0] == a and right[-1] == b:
                merged = right + left
            elif left[-1] == a and right[-1] == b:
                merged = left + right[::-1]
            elif left[0] == a and right[0] == b:
                merged = left[::-1] + right
            else:
                continue
            if sum(customers[c]["demand"] for c in merged) > capacity or duration(merged) > instance["max_duration"]:
                continue
            del routes[rb]
            routes[ra] = merged
            for c in merged:
                owner[c] = ra
        return list(routes.values())

    cold = savings_routes([cid for cid, customer in customers.items() if customer["cold"]])
    warm = savings_routes([cid for cid, customer in customers.items() if not customer["cold"]])
    cold_vans = [van["id"] for van in instance["vans"] if van["cold"]]
    other_vans = [van["id"] for van in instance["vans"] if not van["cold"]]
    if len(cold) > len(cold_vans) or len(cold) + len(warm) > len(instance["vans"]):
        return None
    plan = dict(zip(cold_vans, cold))
    free = other_vans + cold_vans[len(cold):]
    plan.update(zip(free, warm))
    return {"routes": plan}


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(solve(data)))
