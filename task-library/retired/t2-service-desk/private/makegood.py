"""T2 0.3.0: making good damaged and missing items at the lowest cost to the shop (POLICY.md section 11).

Each optimisation ticket reports damaged or missing units on delivered orders. Every accepted unit is made good by one
of four options: the same product sent again, a substitute of the same family sent instead, a refund, or store credit.
The policy asks for the resolution of the whole ticket that costs the shop least. The cost couples the decisions: a
shipment costs the carrier's rate once per delivery address, stock is shared between orders, and the customer may rule
options out. This module generates the catalogue and the tickets from a seed, and holds the cost model, the
compliance rules and the exact optimum (a min-cost flow for every choice of addresses that receive a shipment), which
the grader and the self-calibration share.
"""
import datetime
import itertools
import random
from decimal import ROUND_HALF_UP, Decimal

TODAY = datetime.date(2026, 10, 20)
WINDOW_DAYS = 30
CREDIT_RATE = Decimal("1.10")
CREDIT_COST = Decimal("0.70")
CENT = Decimal("0.01")
RATES = {"UK": "4.90", "FR": "9.90", "DE": "9.90", "CZ": "9.90", "NL": "9.90", "US": "24.90"}
CITIES = {"UK": ["Leeds", "York", "Bath", "Hull"], "FR": ["Lyon", "Lille"], "DE": ["Bonn", "Kiel"], "CZ": ["Brno"], "NL": ["Delft"], "US": ["Austin"]}
STREETS = ["Elm Row", "Dock Road", "Mill Lane", "Park View", "Quay Street", "Harbour Lane", "Canal Street", "Station Road"]
FAMILIES = {
    "mug": ("kitchen", ["Stoneware mug", "Porcelain mug", "Enamel mug", "Glass mug"], (9, 24)),
    "teapot": ("kitchen", ["Cast-iron teapot", "Glass teapot", "Ceramic teapot"], (28, 70)),
    "lamp": ("home", ["Desk lamp", "Clamp lamp", "Arc lamp", "Task lamp"], (35, 140)),
    "towel": ("home", ["Cotton towel", "Linen towel", "Waffle towel"], (12, 30)),
    "kettle": ("kitchen", ["Steel kettle", "Glass kettle", "Gooseneck kettle"], (39, 95)),
    "speaker": ("electronics", ["Bookshelf speaker", "Portable speaker", "Smart speaker"], (59, 180)),
    "planter": ("garden", ["Clay planter", "Fibre planter", "Hanging planter"], (14, 48)),
    "chair": ("home", ["Folding chair", "Oak chair", "Café chair"], (49, 160)),
}
LEVELS = {"S": {"orders": (1, 1), "lines": (2, 3)}, "M": {"orders": (2, 2), "lines": (4, 5)}, "L": {"orders": (3, 4), "lines": (7, 9)}}


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def unit_paid(order, line):
    return cents(Decimal(line["price"]) * (100 - order["coupon"]) / 100)


def credit_per_unit(order, line):
    return cents(unit_paid(order, line) * CREDIT_RATE)


def catalogue(rng):
    """Products of the optimisation tickets: {sku: product}, each with a list price, the shop's cost and stock."""
    products = {}
    for index, (family, (category, names, (low, high))) in enumerate(FAMILIES.items()):
        for number, name in enumerate(names):
            price = Decimal(rng.randrange(low * 100, high * 100 + 1, 50)) / 100
            cost = cents(price * Decimal(rng.randrange(38, 66)) / 100)
            products[f"MG-{index + 7}{number:02d}"] = {"name": name, "family": family, "category": category, "price": f"{price:.2f}",
                                                       "cost": f"{cost:.2f}", "stock": rng.choice([0, 1, 1, 2, 2, 3, 4]), "final_sale": False}
    return products


def address(rng, country):
    return f"{rng.randrange(1, 99)} {rng.choice(STREETS)}, {rng.choice(CITIES[country])}"


class Ticket:
    """A generated optimisation ticket: its customer, orders, reports and constraints."""

    def __init__(self, ticket_id, level, rng, products, customer_id, order_numbers):
        spec = LEVELS[level]
        self.id, self.level = ticket_id, level
        tier = rng.choice(["standard", "silver", "gold"])
        email = f"{ticket_id}.{rng.choice(['ivy', 'jon', 'kai', 'lea', 'max', 'noa', 'oli', 'pia'])}@example.com"
        self.customer_id = customer_id
        self.customer = {"name": f"Customer {ticket_id.upper()}", "email": email, "alternate_emails": [], "tier": tier,
                         "credit": f"{rng.randrange(0, 20)}.00"}
        country = rng.choice(["UK", "UK", "FR", "DE", "CZ", "NL", "US"])
        home = address(rng, country)
        count = rng.randint(*spec["orders"])
        lines_total = rng.randint(*spec["lines"])
        skus = sorted(products)
        self.orders, self.reports = {}, []
        split = sorted(rng.sample(range(1, lines_total), count - 1)) if count > 1 else []
        sizes = [b - a for a, b in zip([0] + split, split + [lines_total])]
        for number, size in zip(order_numbers, sizes):
            order_id = f"O-{number}"
            # Orders often go to the same address, so that one shipment can serve several of them.
            destination = (country, home) if rng.random() < 0.6 else (lambda c: (c, address(rng, c)))(rng.choice(sorted(RATES)))
            delivered = TODAY - datetime.timedelta(days=rng.randrange(2, 28))
            coupon = rng.choice([0, 0, 0, 10, 15, 20])
            chosen = rng.sample(skus, size)
            lines = []
            for sku in chosen:
                qty = rng.choice([1, 1, 2, 2, 3])
                lines.append({"sku": sku, "qty": qty, "price": products[sku]["price"], "state": "active", "returned": 0})
            total = sum((cents(Decimal(line["price"]) * (100 - coupon) / 100) * line["qty"] for line in lines), Decimal("0"))
            paid_credit = cents(total * Decimal(rng.choice([0, 0, 0, 20, 50])) / 100)
            self.orders[order_id] = {"customer": customer_id, "status": "delivered", "placed": str(delivered - datetime.timedelta(days=5)),
                                     "promised": str(delivered - datetime.timedelta(days=1)), "delivered": str(delivered), "coupon": coupon,
                                     "payments": {"card": f"{total - paid_credit:.2f}", "credit": f"{paid_credit:.2f}"}, "shipping": "0.00",
                                     "address": destination[1], "country": destination[0], "lines": lines, "refunds": [], "compensated": None}
            for line in lines:
                if rng.random() < 0.85:
                    self.reports.append({"order": order_id, "sku": line["sku"], "qty": rng.randint(1, line["qty"]),
                                         "how": rng.choice(["arrived broken", "arrived damaged", "was missing from the parcel"])})
        # A larger ticket may report a line delivered too long ago, or more units than were delivered: both are declined.
        if level == "L":
            old_number = order_numbers[len(self.orders)]
            old_id = f"O-{old_number}"
            sku = rng.choice(skus)
            delivered = TODAY - datetime.timedelta(days=rng.randrange(35, 50))
            self.orders[old_id] = {"customer": customer_id, "status": "delivered", "placed": str(delivered - datetime.timedelta(days=5)),
                                   "promised": str(delivered - datetime.timedelta(days=1)), "delivered": str(delivered), "coupon": 0,
                                   "payments": {"card": products[sku]["price"], "credit": "0.00"}, "shipping": "0.00", "address": home,
                                   "country": country, "lines": [{"sku": sku, "qty": 1, "price": products[sku]["price"], "state": "active", "returned": 0}],
                                   "refunds": [], "compensated": None}
            self.reports.insert(rng.randrange(len(self.reports) + 1), {"order": old_id, "sku": sku, "qty": 1, "how": "arrived broken"})
        rng.shuffle(self.reports)
        addresses = sorted({order["address"] for order in self.orders.values()})
        self.constraints = {"no_credit": rng.random() < 0.35,
                            "no_shipping_to": rng.choice(addresses) if len(addresses) > 1 and rng.random() < 0.5 else None}
        same = [report for report in self.reports if rng.random() < 0.2]
        self.same_product = {(report["order"], report["sku"]) for report in same}

    def as_dict(self, products):
        return {"id": self.id, "level": self.level, "customer": self.customer_id, "sender": self.customer["email"],
                "reports": self.reports, "constraints": self.constraints, "same_product": sorted([list(pair) for pair in self.same_product]),
                "prompt": self.text(products)}

    def text(self, products):
        lines = [f"## Ticket {self.id.upper()}", "", f"From: {self.customer['email']}", ""]
        intro = ["Several things went wrong with my recent orders."]
        if self.constraints["no_credit"]:
            intro.append("Please do not give me store credit; I do not plan to order again soon.")
        if self.constraints["no_shipping_to"]:
            intro.append(f"Please do not send anything to {self.constraints['no_shipping_to']}; nobody is there this month.")
        lines += [" ".join(intro), ""]
        for number, report in enumerate(self.reports, 1):
            name = products[report["sku"]]["name"].lower()
            units = "One" if report["qty"] == 1 else {2: "Two", 3: "Three"}[report["qty"]]
            noun = name if report["qty"] == 1 else name + "s"
            verb = report["how"] if report["qty"] == 1 else report["how"].replace("was ", "were ")
            extra = " If you send one, it must be exactly the same model." if (report["order"], report["sku"]) in self.same_product else ""
            lines.append(f"({number}) {units} {noun} from order {report['order']} {verb}.{extra}")
        return "\n".join(lines) + "\n"


def accepted(db, ticket, report):
    """A report is accepted when the order is the sender's, delivered within the window, and the units are still held."""
    order = db["orders"].get(report["order"])
    if order is None or order["customer"] != ticket["customer"] or order["status"] != "delivered" or not order["delivered"]:
        return False
    if (TODAY - datetime.date.fromisoformat(order["delivered"])).days > WINDOW_DAYS:
        return False
    line = next((line for line in order["lines"] if line["sku"] == report["sku"] and line["state"] == "active"), None)
    return line is not None and report["qty"] <= line["qty"] - line["returned"]


def options(db, ticket, report):
    """{option: (product sent or None, cost per unit)} allowed for one unit of an accepted report, before stock limits."""
    order = db["orders"][report["order"]]
    line = next(line for line in order["lines"] if line["sku"] == report["sku"])
    product = db["products"][line["sku"]]
    paid = unit_paid(order, line)
    allowed = {}
    same_only = [report["order"], report["sku"]] in ticket["same_product"]
    blocked = ticket["constraints"]["no_shipping_to"]
    if blocked is None or order["address"].strip().lower() != blocked.strip().lower():
        allowed[("replace", line["sku"])] = (line["sku"], Decimal(product["cost"]))
        if not same_only:
            for sku, other in sorted(db["products"].items()):
                if sku != line["sku"] and other["family"] == product["family"] and Decimal(other["price"]) >= paid:
                    allowed[("substitute", sku)] = (sku, Decimal(other["cost"]))
    allowed[("refund", None)] = (None, paid)
    if not ticket["constraints"]["no_credit"]:
        allowed[("credit", None)] = (None, credit_per_unit(order, line) * CREDIT_COST)
    return allowed


def credit_cost(amount):
    return amount * CREDIT_COST


def resolution_cost(db, entries):
    """The shop's cost of make-good entries: products sent at cost, one carrier rate per address that receives a
    shipment, refunds in full and store credit at 70% of its face value."""
    total, addresses = Decimal("0"), {}
    for entry in entries:
        order = db["orders"][entry["order"]]
        if entry["option"] in ("replace", "substitute"):
            total += Decimal(db["products"][entry["sent"]]["cost"]) * entry["qty"]
            addresses[(order["country"], order["address"].strip().lower())] = Decimal(db["rates"][order["country"]])
        elif entry["option"] == "refund":
            total += Decimal(entry["amount"])
        else:
            total += credit_cost(Decimal(entry["amount"]))
    return total + sum(addresses.values(), Decimal("0"))


def min_cost_flow(units, capacities):
    """Assign each unit one of its (product, cost) choices or its fallback cost, with product capacities; returns the
    minimum total cost. units: [(fallback cost or None, {product: cost})]. Successive shortest paths on a small graph."""
    nodes = ["s", "t"] + [f"u{index}" for index in range(len(units))] + [f"p{sku}" for sku in capacities]
    graph = {node: [] for node in nodes}

    def edge(a, b, capacity, cost):
        graph[a].append([b, capacity, cost, len(graph[b])])
        graph[b].append([a, 0, -cost, len(graph[a]) - 1])
    for index, (fallback, sends) in enumerate(units):
        edge("s", f"u{index}", 1, Decimal("0"))
        if fallback is not None:
            edge(f"u{index}", "t", 1, fallback)
        for sku, cost in sends.items():
            edge(f"u{index}", f"p{sku}", 1, cost)
    for sku, capacity in capacities.items():
        edge(f"p{sku}", "t", capacity, Decimal("0"))
    total, flow = Decimal("0"), 0
    while flow < len(units):
        distance, previous = {node: None for node in nodes}, {}
        distance["s"] = Decimal("0")
        for _ in range(len(nodes)):
            changed = False
            for node in nodes:
                if distance[node] is None:
                    continue
                for position, (target, capacity, cost, _) in enumerate(graph[node]):
                    if capacity > 0 and (distance[target] is None or distance[node] + cost < distance[target]):
                        distance[target], previous[target] = distance[node] + cost, (node, position)
                        changed = True
            if not changed:
                break
        if distance["t"] is None:
            return None
        node = "t"
        while node != "s":
            parent, position = previous[node]
            graph[parent][position][1] -= 1
            reverse = graph[parent][position][3]
            graph[node][reverse][1] += 1
            node = parent
        total += distance["t"]
        flow += 1
    # Each unit's choice: the product its flow went to, or None for its money option.
    choices = []
    for index in range(len(units)):
        used = next((target[1:] for target, capacity, _, _ in graph[f"u{index}"] if target.startswith("p") and capacity == 0), None)
        choices.append(used)
    return total, choices


def solve(db, ticket):
    """The least cost of a compliant resolution of the ticket and one resolution that reaches it, as make-good entries:
    for every set of addresses allowed to receive a shipment, the min-cost assignment of units to products sent (within
    stock) or to their cheaper money option."""
    units, places = [], set()
    for report in ticket["reports"]:
        if not accepted(db, ticket, report):
            continue
        order = db["orders"][report["order"]]
        place = (order["country"], order["address"].strip().lower())
        allowed = options(db, ticket, report)
        money = [cost for (option, _), (_, cost) in allowed.items() if option in ("refund", "credit")]
        sends = {sent: cost for (option, _), (sent, cost) in allowed.items() if option in ("replace", "substitute")}
        cheaper = min((option for option in allowed if option[0] in ("refund", "credit")), key=lambda option: allowed[option][1])
        for _ in range(report["qty"]):
            units.append((place, allowed[cheaper][1], sends, report, cheaper[0]))
        if sends:
            places.add(place)
    best = None
    capacities = {sku: product.get("stock", 0) for sku, product in db["products"].items() if product.get("stock", 0) > 0}
    for size in range(len(places) + 1):
        for shipping in itertools.combinations(sorted(places), size):
            fee = sum((Decimal(db["rates"][country]) for country, _ in shipping), Decimal("0"))
            flow_units = [(fallback, {sku: cost for sku, cost in sends.items() if sku in capacities} if place in shipping else {})
                          for place, fallback, sends, _, _ in units]
            cost, choices = min_cost_flow(flow_units, capacities)
            if best is None or cost + fee < best[0]:
                best = (cost + fee, choices)
    entries = {}
    for (place, _, _, report, money), sent in zip(units, best[1]):
        option = money if sent is None else "replace" if sent == report["sku"] else "substitute"
        key = (report["order"], report["sku"], option, sent)
        entries[key] = entries.get(key, 0) + 1
    resolution = [{"order": order, "sku": sku, "qty": qty, "option": option, "sent": sent} for (order, sku, option, sent), qty in entries.items()]
    return best[0], [with_amount(db, entry) for entry in resolution]


def with_amount(db, entry):
    """An entry with the money desk.py computes for it: the refund or the store credit."""
    order = db["orders"][entry["order"]]
    line = next(line for line in order["lines"] if line["sku"] == entry["sku"])
    amount = unit_paid(order, line) * entry["qty"] if entry["option"] == "refund" else \
        credit_per_unit(order, line) * entry["qty"] if entry["option"] == "credit" else None
    return {**entry, "amount": None if amount is None else f"{amount:.2f}"}


def optimum(db, ticket):
    return solve(db, ticket)[0]


def commands(entries):
    """desk.py commands that carry out make-good entries."""
    out = []
    for entry in entries:
        command = ["make-good", entry["order"], entry["sku"], str(entry["qty"]), entry["option"]]
        out.append(command + ([entry["sent"]] if entry["option"] == "substitute" else []))
    return out


def greedy(db, ticket):
    """A plausible shortcut: each unit, in report order, takes its cheapest option counting products at cost and
    ignoring carrier rates, while stock lasts; the rates are paid afterwards."""
    stock = {sku: product.get("stock", 0) for sku, product in db["products"].items()}
    entries = []
    for report in ticket["reports"]:
        if not accepted(db, ticket, report):
            continue
        allowed = options(db, ticket, report)
        for _ in range(report["qty"]):
            choice = min((option for option in allowed if option[1] is None or stock.get(allowed[option][0], 0) > 0),
                         key=lambda option: allowed[option][1])
            if choice[0] in ("replace", "substitute"):
                stock[allowed[choice][0]] -= 1
            entries.append({"order": report["order"], "sku": report["sku"], "qty": 1, "option": choice[0], "sent": allowed[choice][0]})
    return [with_amount(db, entry) for entry in entries]


def money_only(db, ticket, option="refund"):
    """Every accepted unit refunded (or credited, when the customer allows it)."""
    return [with_amount(db, {"order": report["order"], "sku": report["sku"], "qty": report["qty"], "option": option, "sent": None})
            for report in ticket["reports"] if accepted(db, ticket, report)]


def generate(seed, base_db, first_customer=2001, first_order=6001):
    """The catalogue and twelve tickets, four per level, each with its own customer and orders: (products, customers,
    orders, tickets). A ticket is kept only when the optimum needs the whole ticket in view: on M and L tickets the
    shortcut that ignores carrier rates costs at least 1% more, and on every ticket refunding everything costs at least
    5% more; the optimum also sends something and pays money back for something."""
    rng = random.Random(seed)
    products = catalogue(rng)
    customers, orders, tickets = {}, {}, []
    customer, order = first_customer, first_order
    for level in ("S", "M", "L"):
        for index in range(1, 5):
            for _ in range(2000):
                ticket = Ticket(f"o{level.lower()}{index}", level, rng, products, f"C-{customer}", list(range(order, order + 6)))
                record = ticket.as_dict(products)
                db = {"customers": {**base_db["customers"], ticket.customer_id: ticket.customer}, "orders": {**base_db["orders"], **ticket.orders},
                      "products": {**base_db["products"], **products}, "rates": dict(RATES)}
                best, entries = solve(db, record)
                options_used = {entry["option"] for entry in entries}
                shortcut = resolution_cost(db, greedy(db, record))
                refunds = resolution_cost(db, money_only(db, record))
                if best > 0 and refunds >= best * Decimal("1.05") and options_used & {"replace", "substitute"} and options_used & {"refund", "credit"} \
                        and (level == "S" or shortcut >= best * Decimal("1.01")):
                    break
            else:
                raise RuntimeError(f"no ticket for {level}")
            customers[ticket.customer_id] = ticket.customer
            orders.update(ticket.orders)
            tickets.append(record)
            customer += 1
            order += 6
    return products, customers, orders, tickets
