#!/usr/bin/env python3
"""Offline policies and the hindsight bound of the AP stockroom (anchors, TASK_LIBRARY §3.4).

- `myopic`: each morning, reorder yesterday's sales of every product from the local supplier. It reacts and never plans.
- `strong`: forecast-driven ordering from the public demand model (weekdays, trend, announced promotions): imports cover
  the lead time, the expected delay and a review period, with safety stock; the local supplier tops up when tomorrow
  looks short; arrivals are kept within the free capacity. Its three parameters are tuned per item by simulating 30
  sampled futures for each of 72 settings, drawn from the public distributions, never from the item's hidden draws:
  far more compute than a trial gets.
- `bound`: the hindsight optimum of the realised scenario with capacity and cash relaxed (so a bound above the true
  optimum): every unit of demand served at the cheapest cost, by a lot-sizing dynamic programme per product with both
  suppliers, the realised delays and the holding costs.

Run as a script, it prints the three for given seeds.
"""
import itertools
import json
import math
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stockroom as sr  # noqa: E402


def run_policy(world, decide):
    """Runs a policy through the simulator's own commands; returns (requests, final state)."""
    state, requests = sr.fresh(world), []
    while not state["done"]:
        view = sr.observe(world, state)
        for order in decide(view):
            request = {"command": "order", "arguments": order}
            reply, _ = sr.apply(world, state, request)
            requests.append(request)
            if reply.get("status") == "unknown":
                # Re-send with the same ref: idempotent, so never a duplicate.
                requests.append(request)
                sr.apply(world, state, request)
        requests.append({"command": "advance", "arguments": {}})
        sr.apply(world, state, {"command": "advance"})
    return requests, state


def myopic():
    counter = itertools.count(1)

    def decide(view):
        orders = []
        last = view["history"][-1]["sales"] if view["history"] else None
        for product in view["products"]:
            name = product["name"]
            quantity = last[name]["demand"] if last else 0
            if quantity > 0:
                orders.append({"product": name, "supplier": "local", "quantity": quantity, "ref": f"m{next(counter)}"})
        return orders
    return decide


def mean_demand(view, product, day):
    """The public model's mean demand of a product on a day, from what the view shows (announced promotions only)."""
    model = {"name": product["name"], "base": product["base"], "trend": product["trend"]}
    return sr.expected(model, view["promotions"], day) if 1 <= day <= sr.DAYS else 0.0


def strong(public, z_import, review, z_local):
    """`public`: the per-product base and trend (from the item's public parameters, as RULES.md states them)."""
    counter = itertools.count(1)
    expected_delay = sum(value * probability for value, probability in sr.IMPORT_DELAYS)

    def decide(view):
        day = view["day"]
        orders = []
        incoming = {}
        for order in view["open_orders"]:
            incoming.setdefault(order["product"], []).append(order)
        free = view["free_capacity"]
        for product in view["products"]:
            name = product["name"]
            model = {**product, **public[name]}
            on_hand = view["on_hand"][name]
            pipeline = sum(order["quantity"] for order in incoming.get(name, []))
            # Imports: every `review` days, cover lead time + expected delay + review with safety stock.
            horizon = sr.IMPORT["lead"] + expected_delay + review
            need = sum(mean_demand(view, model, day + offset) for offset in range(0, int(math.ceil(horizon))))
            sigma = math.sqrt(sum(mean_demand(view, model, day + offset) * (1 + mean_demand(view, model, day + offset) / sr.DISPERSION)
                                  for offset in range(0, int(math.ceil(horizon)))))
            target = need + z_import * sigma
            if (day - 1) % review == 0 and day + sr.IMPORT["lead"] <= sr.DAYS:
                quantity = int(round(target - on_hand - pipeline))
                if quantity >= sr.IMPORT["minimum"]:
                    orders.append({"product": name, "supplier": "import", "quantity": quantity, "ref": f"s{next(counter)}"})
                    pipeline += quantity
            # Local top-up when today and tomorrow look short of what is on hand and due by tomorrow.
            due_tomorrow = sum(order["quantity"] for order in incoming.get(name, []) if order["due"] <= day + 1 and order["supplier"] == "local")
            two_days = mean_demand(view, model, day) + mean_demand(view, model, day + 1)
            sigma2 = math.sqrt(two_days * (1 + two_days / (2 * sr.DISPERSION)))
            short = two_days + z_local * sigma2 - on_hand - due_tomorrow
            if short >= 1 and day < sr.DAYS:
                quantity = int(min(math.ceil(short), max(0, free)))
                if quantity >= 1:
                    orders.append({"product": name, "supplier": "local", "quantity": quantity, "ref": f"s{next(counter)}"})
                    free -= quantity
        return orders
    return decide


def public_parameters(world):
    return {product["name"]: {"base": product["base"], "trend": product["trend"]} for product in world["products"]}


def resampled(world, rng):
    """The same public scenario with new hidden draws from the public distributions."""
    copy = dict(world)
    demand = {}
    for product in world["products"]:
        row = []
        for day in range(1, sr.DAYS + 1):
            mean = sr.expected(product, world["promotions"], day)
            if rng.random() < sr.SURGE_PROBABILITY:
                mean *= rng.uniform(2.0, 3.0)
            row.append(sr.poisson(rng, rng.gammavariate(sr.DISPERSION, mean / sr.DISPERSION) if mean > 0 else 0))
        demand[product["name"]] = row
    copy["demand"] = demand
    copy["delays"] = {key: sr.draw(rng, sr.IMPORT_DELAYS) for key in world["delays"]}
    copy["coins"] = [rng.random() for _ in world["coins"]]
    return copy


SETTINGS = list(itertools.product((0.5, 1.0, 1.5, 2.0, 2.5, 3.0), (1, 2, 3, 5), (0.0, 1.0, 2.0)))
SAMPLES = 30


def tuned_strong(world, samples=SAMPLES):
    """The strong policy's parameters, chosen by mean profit over sampled futures (never the item's own draws)."""
    public = public_parameters(world)
    rng = random.Random(f"tuning:{world['seed']}")
    futures = [resampled(world, rng) for _ in range(samples)]
    best = None
    for setting in SETTINGS:
        total = 0.0
        for future in futures:
            _, state = run_policy(future, strong(public, *setting))
            total += sr.result(future, state)["profit"]
        if best is None or total > best[0]:
            best = (total, setting)
    return best[1]


def bound(world):
    """Hindsight bound: serve all demand at the least cost, per product, capacity and cash relaxed (upper bound)."""
    profit = 0.0
    for product in world["products"]:
        name = product["name"]
        demand = world["demand"][name]
        stock = product["start"]
        # The starting stock serves the first days' demand (free; its salvage counts if left over).
        remaining = list(demand)
        for day in range(sr.DAYS):
            used = min(stock, remaining[day])
            stock -= used
            remaining[day] -= used
        # Arrival days each supplier can reach: local orders placed on day t arrive t + 1; imports t + 4 + their realised delay.
        arrivals = {"local": {t + sr.LOCAL["lead"]: t for t in range(1, sr.DAYS)},
                    "import": {}}
        for t in range(1, sr.DAYS + 1):
            arrives = t + sr.IMPORT["lead"] + world["delays"][f"{name}:{t}"]
            if arrives <= sr.DAYS:
                arrivals["import"].setdefault(arrives, t)

        def block_cost(first, last):
            """The cheapest single order covering days first..last (1-based), or None."""
            units = sum(remaining[first - 1:last])
            if units == 0:
                return 0.0
            best = None
            for supplier, terms in (("local", sr.LOCAL), ("import", sr.IMPORT)):
                reachable = [day for day in arrivals[supplier] if day <= first]
                if not reachable:
                    continue
                arrive = max(reachable)
                quantity = max(units, terms["minimum"])
                holding = sum(remaining[day - 1] * (day - arrive) * product["holding"] for day in range(first, last + 1))
                cost = terms["fee"] + quantity * product["cost"] * terms["markup"] + holding - (quantity - units) * product["cost"] * sr.SALVAGE
                best = cost if best is None else min(best, cost)
            return best
        # cost[j]: least cost to serve days 1..j; a day may also go unserved (its penalty and lost margin).
        cost = [0.0] + [math.inf] * sr.DAYS
        for last in range(1, sr.DAYS + 1):
            cost[last] = cost[last - 1] + remaining[last - 1] * (product["price"] + product["penalty"])   # unserved
            for first in range(1, last + 1):
                block = block_cost(first, last)
                if block is not None:
                    cost[last] = min(cost[last], cost[first - 1] + block)
        served_revenue = sum(remaining) * product["price"]
        profit += served_revenue - cost[sr.DAYS] + (sum(demand) - sum(remaining)) * product["price"] + stock * product["cost"] * sr.SALVAGE
    return round(profit, 2)


def anchors(seed):
    world = sr.scenario(seed)
    _, state = run_policy(world, myopic())
    naive = sr.result(world, state)["profit"]
    setting = tuned_strong(world)
    strong_requests, state = run_policy(world, strong(public_parameters(world), *setting))
    best = sr.result(world, state)["profit"]
    return {"myopic": naive, "strong": best, "bound": bound(world), "setting": list(setting)}


if __name__ == "__main__":
    for seed in sys.argv[1:]:
        print(json.dumps({"seed": seed, **anchors(seed)}), flush=True)
