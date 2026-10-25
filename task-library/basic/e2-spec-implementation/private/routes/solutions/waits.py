#!/usr/bin/env python3
"""Calibration candidate: the baseline printed after waiting 12 seconds of wall time with no CPU time spent."""
import json
import math
import random
import sys
import time


SPEED = 4.0


def generate(seed, size, layout, cold_share, capacity, max_duration):
    rng = random.Random(seed)
    if layout == "random":
        points = [(rng.uniform(0, 1000), rng.uniform(0, 1000)) for _ in range(size)]
    else:
        centres = [(rng.uniform(100, 900), rng.uniform(100, 900)) for _ in range(max(3, size // 40))]
        points = []
        for _ in range(size):
            x, y = rng.choice(centres)
            points.append((min(1000, max(0, rng.gauss(x, 60))), min(1000, max(0, rng.gauss(y, 60)))))
    customers = [{"id": f"C{index + 1:03d}", "x": round(x, 1), "y": round(y, 1), "demand": rng.randint(1, 30), "service": rng.randint(3, 15),
                  "cold": rng.random() < cold_share} for index, (x, y) in enumerate(points)]
    instance = {"depot": [500.0, 500.0], "speed": SPEED, "max_duration": max_duration, "vans": [], "customers": customers}
    total = sum(customer["demand"] for customer in customers)
    cold = sum(customer["demand"] for customer in customers if customer["cold"])
    cold_vans = math.ceil(cold / capacity * 1.4) + 1
    vans = max(math.ceil(total / capacity * 1.4) + 2, cold_vans + 2)
    while True:
        instance["vans"] = [{"id": f"V{index + 1:02d}", "capacity": capacity, "cold": index < cold_vans} for index in range(vans)]
        if baseline(instance) is not None:
            return instance
        vans += 1


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def route_cost(instance, route, places):
    depot = tuple(instance["depot"])
    if not route:
        return 0.0
    points = [depot] + [places[customer] for customer in route] + [depot]
    return sum(distance(points[index], points[index + 1]) for index in range(len(points) - 1))


def check(instance, solution):
    """(cost, None) for a feasible solution, else (None, reason)."""
    if not isinstance(solution, dict) or not isinstance(solution.get("routes"), dict):
        return None, "no routes object"
    customers = {customer["id"]: customer for customer in instance["customers"]}
    vans = {van["id"]: van for van in instance["vans"]}
    places = {cid: (customer["x"], customer["y"]) for cid, customer in customers.items()}
    seen, total = set(), 0.0
    for van_id, route in solution["routes"].items():
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
        length = route_cost(instance, route, places)
        if length / instance["speed"] + sum(customers[customer]["service"] for customer in route) > instance["max_duration"] + 1e-9:
            return None, f"route of {van_id} too long"
        total += length
    if len(seen) != len(customers):
        return None, f"{len(customers) - len(seen)} customers not visited"
    return total, None


def baseline(instance):
    """Nearest neighbour: refrigerated vans take refrigerated customers, then the other vans take the rest, each route
    growing by the nearest customer that still fits. Returns a feasible solution or None."""
    customers = {customer["id"]: customer for customer in instance["customers"]}
    depot = tuple(instance["depot"])
    left = set(customers)
    routes = {}
    vans = sorted(instance["vans"], key=lambda van: not van["cold"])
    phases = [lambda customer: customer["cold"], lambda customer: not customer["cold"], lambda customer: True]
    for wanted in phases:
        for van in vans:
            if van["id"] in routes and routes[van["id"]]:
                continue
            route, load, minutes, here = [], 0, 0.0, depot
            while True:
                best = None
                for cid in left:
                    customer = customers[cid]
                    if not wanted(customer) or (customer["cold"] and not van["cold"]) or load + customer["demand"] > van["capacity"]:
                        continue
                    point = (customer["x"], customer["y"])
                    step = distance(here, point)
                    if minutes + (step + distance(point, depot)) / instance["speed"] + customer["service"] > instance["max_duration"]:
                        continue
                    if best is None or step < best[0]:
                        best = (step, cid)
                if best is None:
                    break
                step, cid = best
                customer = customers[cid]
                route.append(cid)
                left.discard(cid)
                load += customer["demand"]
                minutes += step / instance["speed"] + customer["service"]
                here = (customer["x"], customer["y"])
            if route:
                routes[van["id"]] = route
    return {"routes": routes} if not left else None


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    time.sleep(12)
    print(json.dumps(baseline(data)))
