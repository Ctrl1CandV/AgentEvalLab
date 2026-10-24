#!/usr/bin/env python3
"""Checks a plan for an instance and prints its cost: python3 evaluate.py INSTANCE.json PLAN.json"""
import json
import math
import sys


def check(instance, plan):
    """(cost, None) for a feasible plan, else (None, reason)."""
    if not isinstance(plan, dict) or not isinstance(plan.get("routes"), dict):
        return None, "no routes object"
    customers = {customer["id"]: customer for customer in instance["customers"]}
    vans = {van["id"]: van for van in instance["vans"]}
    depot = tuple(instance["depot"])
    seen, total = set(), 0.0
    for van_id, route in plan["routes"].items():
        if van_id not in vans:
            return None, f"unknown van {van_id!r}"
        if not isinstance(route, list) or not all(isinstance(customer, str) for customer in route):
            return None, f"route of {van_id} is not a list of ids"
        for customer in route:
            if customer not in customers:
                return None, f"unknown customer {customer!r}"
            if customer in seen:
                return None, f"customer {customer} visited twice"
            seen.add(customer)
            if customers[customer]["cold"] and not vans[van_id]["cold"]:
                return None, f"refrigerated customer {customer} in van {van_id}"
        if sum(customers[customer]["demand"] for customer in route) > vans[van_id]["capacity"]:
            return None, f"van {van_id} over capacity"
        points = [depot] + [(customers[customer]["x"], customers[customer]["y"]) for customer in route] + [depot] if route else []
        length = sum(math.hypot(points[i][0] - points[i + 1][0], points[i][1] - points[i + 1][1]) for i in range(len(points) - 1))
        if length / instance["speed"] + sum(customers[customer]["service"] for customer in route) > instance["max_duration"] + 1e-9:
            return None, f"route of {van_id} too long"
        total += length
    if len(seen) != len(customers):
        return None, f"{len(customers) - len(seen)} customers not visited"
    return total, None


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        instance = json.load(handle)
    with open(sys.argv[2], encoding="utf-8") as handle:
        plan = json.load(handle)
    cost, reason = check(instance, plan)
    print(f"infeasible: {reason}" if reason else f"feasible, cost {cost:.3f}")
    return 0 if reason is None else 1


if __name__ == "__main__":
    sys.exit(main())
