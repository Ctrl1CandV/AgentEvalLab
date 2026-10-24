"""The routes item's reference solver: ruin and recreate with simulated annealing (in the spirit of SISR), run offline
for minutes per instance to find the best-known cost that anchors the score. Standard library only.

    python3 reference.py INSTANCE.json SECONDS SEED  -> prints {"cost": ..., "routes": {...}}
"""
import json
import math
import random
import sys
import time

import model


class Problem:
    def __init__(self, instance):
        self.instance = instance
        self.customers = instance["customers"]
        self.ids = [customer["id"] for customer in self.customers]
        points = [tuple(instance["depot"])] + [(customer["x"], customer["y"]) for customer in self.customers]
        self.dist = [[model.distance(a, b) for b in points] for a in points]
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
    start = model.baseline(instance)
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
    began = time.time()
    while True:
        elapsed = time.time() - began
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
    cost, reason = model.check(instance, solution)
    assert reason is None, reason
    return cost, solution


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    cost, solution = solve(data, float(sys.argv[2]), int(sys.argv[3]))
    print(json.dumps({"cost": cost, **solution}))
