#!/usr/bin/env python3
"""Calibration candidate: ruin and recreate with simulated annealing for 7 seconds of CPU time (the reference solver, standalone)."""
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





class Problem:
    def __init__(self, instance):
        self.instance = instance
        self.customers = instance["customers"]
        self.ids = [customer["id"] for customer in self.customers]
        points = [tuple(instance["depot"])] + [(customer["x"], customer["y"]) for customer in self.customers]
        self.dist = [[distance(a, b) for b in points] for a in points]
        self.demand = [0] + [customer["demand"] for customer in self.customers]
        self.service = [0] + [customer["service"] for customer in self.customers]
        self.cold = [False] + [customer["cold"] for customer in self.customers]
        self.vans = instance["vans"]
        self.speed, self.max_duration = instance["speed"], instance["max_duration"]
        count = len(points)
        self.near = [sorted(range(1, count), key=lambda other: self.dist[node][other]) for node in range(count)]

    def length(self, route):
        stops = [0] + route + [0]
        return sum(self.dist[stops[index]][stops[index + 1]] for index in range(len(stops) - 1))

    def fits(self, van, route, length):
        return sum(self.demand[node] for node in route) <= van["capacity"] and \
            length / self.speed + sum(self.service[node] for node in route) <= self.max_duration + 1e-9


def insert_all(problem, routes, loads, lengths, services, removed, rng):
    """Greedy cheapest feasible insertion, in a random order with occasional blinks; False when a customer does not fit."""
    order = list(removed)
    mode = rng.random()
    if mode < 0.4:
        rng.shuffle(order)
    elif mode < 0.7:
        order.sort(key=lambda node: -problem.demand[node])
    else:
        order.sort(key=lambda node: -problem.dist[0][node])
    dist, speed, limit = problem.dist, problem.speed, problem.max_duration
    for node in order:
        best = None
        for index, van in enumerate(problem.vans):
            if problem.cold[node] and not van["cold"]:
                continue
            if loads[index] + problem.demand[node] > van["capacity"]:
                continue
            route = routes[index]
            stops = [0] + route + [0]
            base = lengths[index]
            room = limit - services[index] - problem.service[node]
            for position in range(len(stops) - 1):
                if rng.random() < 0.01:
                    continue
                a, b = stops[position], stops[position + 1]
                delta = dist[a][node] + dist[node][b] - dist[a][b]
                if best is not None and delta >= best[0]:
                    continue
                if (base + delta) / speed > room + 1e-9:
                    continue
                best = (delta, index, position)
        if best is None:
            return False
        delta, index, position = best
        routes[index].insert(position, node)
        loads[index] += problem.demand[node]
        lengths[index] += delta
        services[index] += problem.service[node]
    return True


def ruin(problem, routes, rng, size):
    """Remove about `size` customers near a random seed customer: whole strings from the routes they touch."""
    where = {node: index for index, route in enumerate(routes) for node in route}
    seed = rng.randrange(1, len(problem.dist))
    removed, touched = set(), set()
    for node in problem.near[seed]:
        if len(removed) >= size:
            break
        index = where[node]
        if index in touched or node in removed:
            continue
        touched.add(index)
        route = routes[index]
        position = route.index(node)
        length = min(len(route), max(1, int(rng.random() * min(10, len(route))) + 1))
        start = max(0, min(position - rng.randrange(length), len(route) - length))
        removed.update(route[start:start + length])
    for index in touched:
        routes[index] = [node for node in routes[index] if node not in removed]
    return removed


def solve(instance, seconds, seed):
    problem = Problem(instance)
    rng = random.Random(seed)
    start = baseline(instance)
    index_of = {cid: position + 1 for position, cid in enumerate(problem.ids)}
    van_index = {van["id"]: index for index, van in enumerate(problem.vans)}
    routes = [[] for _ in problem.vans]
    for van_id, route in start["routes"].items():
        routes[van_index[van_id]] = [index_of[cid] for cid in route]

    def totals(routes):
        lengths = [problem.length(route) for route in routes]
        return lengths, [sum(problem.demand[node] for node in route) for route in routes], [sum(problem.service[node] for node in route) for route in routes]

    lengths, loads, services = totals(routes)
    current = best = sum(lengths)
    best_routes = [list(route) for route in routes]
    n = len(problem.ids)
    t_start, t_end = 0.02 * current / n, 0.0005 * current / n
    began = time.process_time()
    while True:
        elapsed = time.process_time() - began
        if elapsed > seconds:
            break
        temperature = t_start * (t_end / t_start) ** (elapsed / seconds)
        trial = [list(route) for route in routes]
        removed = ruin(problem, trial, rng, rng.randint(5, max(6, min(40, n // 6))))
        lengths_t, loads_t, services_t = totals(trial)
        if not insert_all(problem, trial, loads_t, lengths_t, services_t, removed, rng):
            continue
        cost = sum(lengths_t)
        if cost < current - temperature * math.log(rng.random()):
            routes, current = trial, cost
            if cost < best - 1e-9:
                best, best_routes = cost, [list(route) for route in trial]
    solution = {"routes": {van["id"]: [problem.ids[node - 1] for node in route] for van, route in zip(problem.vans, best_routes) if route}}
    cost, reason = check(instance, solution)
    assert reason is None, reason
    return cost, solution




if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(solve(data, 7.0, 1)[1]))
