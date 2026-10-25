#!/usr/bin/env python3
"""The AP stockroom: a store's stock of four products over 40 days, with two suppliers, uncertain demand and uncertain
import delays (PLAN-007 WP3.3, TASK_LIBRARY §3.4). Everything about the rules and the distributions is public
(`public/RULES.md`); only the scenario's random draws (each day's demand, unannounced surges, import delays, which
uncertain order replies did go through) are hidden, drawn from the item's seed.

As the `simulator` of the workspace-simulator profile it reads one JSON request on standard input,
{"command": ..., "arguments": {...}}, applies it to the state in `--state`, appends every state-changing command to
`log.jsonl`, and prints the JSON reply. `replay()` runs a log on a fresh state (the grader, the policies).

Task 0.2.0 adds the `day` command (the day's orders and the end of the day in one call) and makes the morning view that
`advance` and `day` return compact (no product table, no sales history; `observe` gives both): with one call per day
and a small reply, 40 days fit a session's token budget, so the task measures the decisions, not the transcript.
"""
import argparse
import json
import math
import os
import random
import sys

DAYS = 40
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEKDAY_FACTOR = (0.9, 0.9, 0.95, 1.0, 1.1, 1.4, 1.25)
DISPERSION = 4.0            # gamma shape of the demand noise: variance = mean + mean^2 / 4
SURGE_PROBABILITY = 0.03    # per product and day, unannounced: demand x 2 to x 3
LOCAL = {"lead": 1, "fee": 15.0, "markup": 1.3, "minimum": 1}
IMPORT = {"lead": 4, "fee": 40.0, "markup": 1.0, "minimum": 25}
IMPORT_DELAYS = ((0, 0.5), (1, 0.25), (2, 0.15), (3, 0.1))   # extra days after the 4-day lead time, independently per order
UNCERTAIN_REPLY = 0.08      # share of order calls answered "status unknown"; half of those were placed
SALVAGE = 0.4               # stock left on day 40 is worth 40% of its import cost
HISTORY = 14


# Scenario ---------------------------------------------------------------------------------------------------------------

def scenario(seed):
    """The item's public parameters and hidden draws, all from its seed."""
    rng = random.Random(f"stockroom:{seed}")
    names = ["Lamps", "Kettles", "Fans", "Heaters", "Blenders", "Toasters", "Irons", "Mixers"]
    rng.shuffle(names)
    products = []
    for name in sorted(names[:4]):
        price = round(rng.uniform(20, 60), 2)
        cost = round(price * rng.uniform(0.45, 0.6), 2)
        base = rng.randint(8, 30)
        products.append({"name": name, "price": price, "cost": cost, "holding": round(cost * 0.01, 3), "penalty": round(0.3 * price, 2),
                         "base": base, "trend": round(rng.uniform(-0.25, 0.35), 2), "start": base * 5})
    promotions = []
    for product in products:
        if rng.random() < 0.75:
            start = rng.randint(9, DAYS - 6)
            promotions.append({"product": product["name"], "start": start, "end": start + rng.randint(2, 4), "multiplier": round(rng.uniform(2.0, 3.0), 1),
                               "announced": start - 7})
    capacity = 8 * sum(product["base"] for product in products)
    cash = round(15 * sum(product["base"] * product["cost"] for product in products), 2)
    hidden = random.Random(f"stockroom-hidden:{seed}")
    demand = {}
    for product in products:
        row = []
        for day in range(1, DAYS + 1):
            mean = expected(product, promotions, day)
            if hidden.random() < SURGE_PROBABILITY:
                mean *= hidden.uniform(2.0, 3.0)
            row.append(poisson(hidden, hidden.gammavariate(DISPERSION, mean / DISPERSION) if mean > 0 else 0))
        demand[product["name"]] = row
    # One delay per possible import order (product, day), and one coin per order call, drawn up front.
    delays = {f"{product['name']}:{day}": draw(hidden, IMPORT_DELAYS) for product in products for day in range(1, DAYS + 1)}
    coins = [hidden.random() for _ in range(2000)]
    return {"seed": seed, "products": products, "promotions": promotions, "capacity": capacity, "cash": cash, "demand": demand, "delays": delays, "coins": coins}


def expected(product, promotions, day):
    """The demand model's mean (public): base x weekday factor x trend x any promotion."""
    mean = product["base"] * WEEKDAY_FACTOR[(day - 1) % 7] * (1 + product["trend"] * (day - 1) / (DAYS - 1))
    for promotion in promotions:
        if promotion["product"] == product["name"] and promotion["start"] <= day <= promotion["end"]:
            mean *= promotion["multiplier"]
    return mean


def poisson(rng, mean):
    if mean <= 0:
        return 0
    if mean > 50:
        return max(0, round(rng.gauss(mean, math.sqrt(mean))))
    limit, k, p = math.exp(-mean), 0, rng.random()
    while p > limit:
        k += 1
        p *= rng.random()
    return k


def draw(rng, table):
    roll, total = rng.random(), 0.0
    for value, probability in table:
        total += probability
        if roll < total:
            return value
    return table[-1][0]


# State ------------------------------------------------------------------------------------------------------------------

def fresh(world):
    return {"day": 1, "cash": world["cash"], "stock": {product["name"]: product["start"] for product in world["products"]}, "orders": [],
            "history": [], "calls": 0, "refs": {}, "invalid": 0, "duplicates": 0, "overflow": 0, "lost": 0, "revenue": 0.0, "purchases": 0.0,
            "fees": 0.0, "holding": 0.0, "penalties": 0.0, "done": False, "arrivals_today": {}}


def product_of(world, name):
    return next((product for product in world["products"] if product["name"] == name), None)


def public_order(order):
    return {key: order[key] for key in ("id", "ref", "product", "supplier", "quantity", "placed", "due", "status")}


def observe(world, state):
    day = state["day"]
    return {
        "day": day, "weekday": WEEKDAYS[(day - 1) % 7], "days_left": DAYS - day + 1 if not state["done"] else 0, "finished": state["done"],
        "cash": round(state["cash"], 2), "capacity": world["capacity"], "on_hand": dict(state["stock"]), "free_capacity": world["capacity"] - sum(state["stock"].values()),
        "arrived_this_morning": state["arrivals_today"],
        "open_orders": [public_order(order) for order in state["orders"] if order["status"] == "open"],
        "products": [{key: product[key] for key in ("name", "price", "cost", "holding", "penalty", "base", "trend")} for product in world["products"]],
        "promotions": [promotion for promotion in world["promotions"] if promotion["announced"] <= day],
        "history": state["history"][-HISTORY:],
    }


def morning(world, state):
    """The compact view after a day ends: what changed and what a decision needs; static facts stay with `observe`."""
    day = state["day"]
    return {
        "day": day, "weekday": WEEKDAYS[(day - 1) % 7], "days_left": DAYS - day + 1 if not state["done"] else 0, "finished": state["done"],
        "cash": round(state["cash"], 2), "on_hand": dict(state["stock"]), "free_capacity": world["capacity"] - sum(state["stock"].values()),
        "arrived_this_morning": state["arrivals_today"],
        "open_orders": [public_order(order) for order in state["orders"] if order["status"] == "open"],
        "promotions": [promotion for promotion in world["promotions"] if promotion["announced"] <= day],
    }


def place(world, state, arguments):
    """An order line, idempotent by its reference."""
    name, supplier = arguments.get("product"), arguments.get("supplier")
    quantity, ref = arguments.get("quantity"), arguments.get("ref")
    product = product_of(world, name)
    terms = {"local": LOCAL, "import": IMPORT}.get(supplier)
    if state["done"]:
        return {"status": "rejected", "reason": "the 40 days are over"}
    if not isinstance(ref, str) or not 1 <= len(ref) <= 64:
        return {"status": "rejected", "reason": "ref must be a string of 1 to 64 characters"}
    request = {"product": name, "supplier": supplier, "quantity": quantity}
    if ref in state["refs"]:
        existing = next(order for order in state["orders"] if order["ref"] == ref)
        if {"product": existing["product"], "supplier": existing["supplier"], "quantity": existing["quantity"]} != request:
            state["invalid"] += 1
            return {"status": "rejected", "reason": f"ref {ref} was already used for another order"}
        return {"status": "placed", "order": public_order(existing), "note": "already placed with this ref; nothing new was ordered"}
    if product is None or terms is None or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < terms["minimum"] or quantity > 10_000:
        state["invalid"] += 1
        return {"status": "rejected", "reason": "unknown product or supplier, or a quantity outside the supplier's terms"}
    unit = round(product["cost"] * terms["markup"], 2)
    total = round(unit * quantity + terms["fee"], 2)
    if total > state["cash"] + 1e-9:
        state["invalid"] += 1
        return {"status": "rejected", "reason": f"not enough cash: the order costs {total}, cash is {round(state['cash'], 2)}"}
    delay = world["delays"][f"{name}:{state['day']}"] if supplier == "import" else 0
    due = state["day"] + terms["lead"]
    # The same product, supplier and quantity ordered twice on one day under different refs: a duplicate side effect.
    if any(order["product"] == name and order["supplier"] == supplier and order["quantity"] == quantity and order["placed"] == state["day"]
           for order in state["orders"]):
        state["duplicates"] += 1
    order = {"id": f"PO-{len(state['orders']) + 1:04d}", "ref": ref, "product": name, "supplier": supplier, "quantity": quantity, "placed": state["day"],
             "due": due, "arrives": due + delay, "status": "open", "unit": unit}
    state["orders"].append(order)
    state["refs"][ref] = order["id"]
    state["cash"] -= total
    state["purchases"] += unit * quantity
    state["fees"] += terms["fee"]
    return {"status": "placed", "order": public_order(order)}


def advance(world, state):
    """Ends the day: demand and sales, holding costs; then the next morning's deliveries."""
    if state["done"]:
        return {"status": "rejected", "reason": "the 40 days are over"}
    day = state["day"]
    sold = {}
    for product in world["products"]:
        name = product["name"]
        wanted = world["demand"][name][day - 1]
        sale = min(wanted, state["stock"][name])
        state["stock"][name] -= sale
        state["cash"] += sale * product["price"]
        state["revenue"] += sale * product["price"]
        state["penalties"] += (wanted - sale) * product["penalty"]
        state["lost"] += wanted - sale
        state["holding"] += state["stock"][name] * product["holding"]
        state["cash"] -= state["stock"][name] * product["holding"]
        sold[name] = {"demand": wanted, "sold": sale}
    state["history"].append({"day": day, "weekday": WEEKDAYS[(day - 1) % 7], "sales": sold})
    if day == DAYS:
        state["done"] = True
        return {"status": "finished", "day": day, "sales": sold, "result": result(world, state)}
    state["day"] = day + 1
    state["arrivals_today"] = {}
    for order in state["orders"]:
        if order["status"] == "open" and order["arrives"] == state["day"]:
            free = world["capacity"] - sum(state["stock"].values())
            accepted = min(free, order["quantity"])
            state["stock"][order["product"]] += accepted
            state["overflow"] += order["quantity"] - accepted
            order["status"] = "delivered" if accepted == order["quantity"] else "delivered-partly"
            state["arrivals_today"][order["product"]] = state["arrivals_today"].get(order["product"], 0) + accepted
    return {"status": "advanced", "day_ended": day, "sales": sold, "now": morning(world, state)}


def result(world, state):
    """Profit: cash gained over the 40 days and the salvage value of the stock left, minus the lost-sale penalties."""
    salvage = sum(state["stock"][product["name"]] * product["cost"] * SALVAGE for product in world["products"])
    profit = state["cash"] - world["cash"] + salvage - state["penalties"]
    return {"profit": round(profit, 2), "revenue": round(state["revenue"], 2), "purchases": round(state["purchases"], 2), "fees": round(state["fees"], 2),
            "holding": round(state["holding"], 2), "penalties": round(state["penalties"], 2), "salvage": round(salvage, 2), "lost_units": state["lost"],
            "overflow_units": state["overflow"], "invalid_actions": state["invalid"], "duplicate_orders": state["duplicates"]}


def apply(world, state, request):
    """(reply, whether the command changed the state). The reply to an order may be "unknown" (a timeout): then the
    order was placed or not by the scenario's coin, and the reply does not say which."""
    command, arguments = request.get("command"), request.get("arguments") or {}
    if command == "observe":
        return observe(world, state), False
    if command == "order":
        return order_call(world, state, arguments), True
    if command == "advance":
        return advance(world, state), True
    if command == "day":
        # The day's orders, each as an `order` call (its own reference and possibly an uncertain reply), then `advance`.
        orders = arguments.get("orders", [])
        if not isinstance(orders, list) or len(orders) > 20 or not all(isinstance(order, dict) for order in orders):
            state["invalid"] += 1
            return {"status": "rejected", "reason": "day takes {\"orders\": [up to 20 order objects]}; nothing was ordered and the day did not end"}, True
        if state["done"]:
            return {"status": "rejected", "reason": "the 40 days are over"}, True
        replies = [order_call(world, state, order) for order in orders]
        return {"orders": replies, **advance(world, state)}, True
    if command == "result":
        return {"finished": state["done"], **result(world, state)}, False
    return {"status": "rejected", "reason": "commands: observe, order {product, supplier, quantity, ref}, advance, day {orders: [...]}, result"}, False


def order_call(world, state, arguments):
    coin = world["coins"][state["calls"] % len(world["coins"])]
    state["calls"] += 1
    if coin < UNCERTAIN_REPLY:
        if coin < UNCERTAIN_REPLY / 2:
            place(world, state, arguments)
        return {"status": "unknown", "reason": "the supplier did not answer in time; the order may or may not have been placed"}
    return place(world, state, arguments)


def replay(world, requests, finish=True):
    """A fresh state through the logged requests; then, when `finish`, the days left are advanced with no orders."""
    state = fresh(world)
    for request in requests:
        apply(world, state, request)
    managed = state["done"]
    while finish and not state["done"]:
        advance(world, state)
    return state, managed


# Simulator protocol -------------------------------------------------------------------------------------------------------

def item_seed(item_id):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "items.json"), encoding="utf-8") as handle:
        return json.load(handle)[item_id]["seed"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", required=True)
    parser.add_argument("--state", required=True)
    args = parser.parse_args()
    world = scenario(item_seed(args.item))
    log_path = os.path.join(args.state, "log.jsonl")
    requests = [json.loads(line) for line in open(log_path, encoding="utf-8")] if os.path.exists(log_path) else []
    state, _ = replay(world, requests, finish=False)
    try:
        request = json.loads(sys.stdin.readline())
        if not isinstance(request, dict):
            raise ValueError
    except ValueError:
        print(json.dumps({"status": "rejected", "reason": "send one JSON object: {\"command\": ..., \"arguments\": {...}}"}))
        return
    reply, changed = apply(world, state, request)
    if changed:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"command": request.get("command"), "arguments": request.get("arguments") or {}}) + "\n")
    print(json.dumps(reply))


if __name__ == "__main__":
    main()
