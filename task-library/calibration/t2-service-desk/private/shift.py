"""T2 0.4.0: a shift of coupled tickets (SHIFT_POLICY.md, items sh1-sh4).

One item is a shift of eight tickets from about eight customers, handled in order in one workspace. The policy keeps
the 0.3.0 rules (verified senders, prices paid, store credit first, return windows and fees, late orders, least-cost
make-good) and adds four whose conditions must be derived and couple the tickets:

- recalls: a notice covers a product's units on orders placed within its dates and delivered to its countries. Covered
  units are returned whatever the window and made good only by refund, and a recalled product is never sent;
- claims review: a customer with 3 or more reports made good since 2026-07-22, including today's earlier tickets and
  this ticket's accepted reports, has further reports passed to review instead;
- goodwill limit: a customer with 80.00 or more of compensation and make-good credit since 2026-09-20, including
  today's, gets no store credit in a ticket;
- consolidation: an address that already received a shipment today costs no further carrier rate.

So a ticket's correct handling depends on what earlier tickets did: stock they used, shipments they made, reports they
accepted and credit they gave. Each ticket is graded against the oracle run on the state the model's own commands had
produced when the ticket began (its `begin` marker), so one mistake is deducted where it was made and nowhere else.

The generator plants these couplings and keeps a shift only when each modelled misreading changes some ticket's correct
handling, on the true state before that ticket.
"""
import copy
import datetime
import itertools
import json
import random
from decimal import Decimal

import makegood
import shift_desk

TODAY = datetime.date(2026, 10, 20)
REPORTS_FROM = datetime.date(2026, 7, 22)
GOODWILL_FROM = datetime.date(2026, 9, 20)
GOODWILL_LIMIT = Decimal("80.00")
REVIEW_AT = 3
REPORT_DAYS = 30
WINDOWS = {"books": 14, "clothing": 60}
FEES = {"standard": Decimal("0.15"), "silver": Decimal("0.10"), "gold": Decimal("0")}
EXTRA_FAMILIES = {"book": ("books", ["Atlas of Rivers", "Field Guide", "Collected Letters"], (12, 40)),
                  "jacket": ("clothing", ["Rain jacket", "Fleece jacket", "Down jacket"], (60, 180)),
                  "coffee": ("food", ["Coffee beans", "Espresso blend"], (9, 18))}
NAMES = ["Ada Brook", "Bo Lindqvist", "Cleo Marsh", "Dev Patel", "Esme Vance", "Femi Ade", "Gus Moreno", "Hana Ito", "Ivo Kral", "Jun Park"]
TICKETS = 8
MISTAKES = {
    "today-reports": "counts only reports made before today",
    "today-goodwill": "counts only goodwill given before today",
    "boundary": "reads 'on 2026-07-22 or later' and 'on 2026-09-20 or later' as after those dates",
    "no-consolidation": "charges a carrier rate for an address that already received a shipment today",
    "recall-ignored": "ignores the recall notices",
    "recall-sku-only": "treats every unit of a recalled product as covered",
}
SHIFTS = {"sh1": "t2-shift-2026-10:sh1", "sh2": "t2-shift-2026-10:sh2", "sh3": "t2-shift-2026-10:sh3", "sh4": "t2-shift-2026-10:sh4"}


def date(text):
    return datetime.date.fromisoformat(text)


def money(value):
    return f"{value:.2f}"


def catalogue(rng):
    products = {}
    families = {**makegood.FAMILIES, **EXTRA_FAMILIES}
    for index, (family, (category, names, (low, high))) in enumerate(families.items()):
        for number, name in enumerate(names):
            price = Decimal(rng.randrange(low * 100, high * 100 + 1, 50)) / 100
            cost = makegood.cents(price * Decimal(rng.randrange(38, 66)) / 100)
            products[f"SH-{index + 1}{number:02d}"] = {"name": name, "family": family, "category": category, "price": money(price),
                                                       "cost": money(cost), "stock": rng.choice([0, 1, 1, 2, 2, 3]),
                                                       "final_sale": category == "clothing" and rng.random() < 0.3}
    return products


# Facts of the policy, each with the misreadings that the generator checks.

def verified_customer(db, sender):
    for customer_id, customer in sorted(db["customers"].items()):
        if customer["email"].lower() == sender.lower():
            return customer_id
        if any(entry["address"].lower() == sender.lower() and entry["verified"] for entry in customer["alternate_emails"]):
            return customer_id
    return None


def since(entry_date, first, mistakes):
    day = date(entry_date)
    if "today-reports" in mistakes and first == REPORTS_FROM and day == TODAY:
        return False
    if "today-goodwill" in mistakes and first == GOODWILL_FROM and day == TODAY:
        return False
    return day > first if "boundary" in mistakes else day >= first


def report_count(db, customer, mistakes=()):
    """Order lines made good for the customer since REPORTS_FROM, one per line and day."""
    seen = set()
    for order_id, order in db["orders"].items():
        if order["customer"] == customer:
            for entry in order.get("make_good", []):
                if since(entry["date"], REPORTS_FROM, mistakes):
                    seen.add((order_id, entry["sku"], entry["date"]))
    return len(seen)


def goodwill(db, customer, mistakes=()):
    return sum((Decimal(entry["amount"]) for entry in db["customers"][customer].get("credits", [])
                if entry["kind"] in ("compensation", "make-good") and since(entry["date"], GOODWILL_FROM, mistakes)), Decimal("0"))


def covered(db, order, sku, mistakes=()):
    if "recall-ignored" in mistakes:
        return False
    for notice in db["recalls"]:
        if notice["sku"] == sku and ("recall-sku-only" in mistakes or
                                     (notice["placed_from"] <= order["placed"] <= notice["placed_to"] and order["country"] in notice["countries"])):
            return True
    return False


def recalled(db, mistakes=()):
    return set() if "recall-ignored" in mistakes else {notice["sku"] for notice in db["recalls"]}


def find_line(order, sku):
    return next((line for line in order["lines"] if line["sku"] == sku), None)


def report_accepted(db, customer, request):
    order = db["orders"].get(request["order"])
    if customer is None or order is None or order["customer"] != customer or order["status"] != "delivered":
        return False
    if (TODAY - date(order["delivered"])).days > REPORT_DAYS:
        return False
    line = find_line(order, request["sku"])
    return line is not None and line["state"] == "active" and request["qty"] <= line["qty"] - line["returned"]


def decide_return(db, customer, request, mistakes):
    order = db["orders"].get(request["order"])
    if customer is None or order is None or order["customer"] != customer or order["status"] != "delivered":
        return None
    line = find_line(order, request["sku"])
    if line is None or line["state"] != "active" or request["qty"] > line["qty"] - line["returned"]:
        return None
    product = db["products"][line["sku"]]
    tier = db["customers"][customer]["tier"]
    amount = makegood.unit_paid(order, line) * request["qty"]
    if covered(db, order, line["sku"], mistakes):
        refund = amount
    else:
        days = WINDOWS.get(product["category"], 30) + (15 if tier == "gold" else 0)
        if product["category"] == "food" or product["final_sale"] or (TODAY - date(order["delivered"])).days > days:
            return None
        fee = Decimal("0") if product["category"] != "electronics" or request["defective"] else makegood.cents(amount * FEES[tier])
        refund = amount - fee
    credit = min(refund, shift_desk.credit_left(order))
    return ["refund", request["order"], request["sku"], str(request["qty"]), money(refund - credit), money(credit)]


def decide_compensation(db, customer, request, credit_ok):
    order = db["orders"].get(request["order"])
    if customer is None or order is None or order["customer"] != customer or not credit_ok:
        return None
    if order["status"] != "delivered" or (date(order["delivered"]) - date(order["promised"])).days < 3 or order["compensated"] is not None:
        return None
    total = sum((makegood.unit_paid(order, line) * line["qty"] for line in order["lines"]), Decimal("0"))
    rate = Decimal("0.15") if db["customers"][customer]["tier"] == "gold" else Decimal("0.10")
    return ["compensate", request["order"], money(makegood.cents(total * rate))]


def shipped_today(db):
    return {(shipment["country"], shipment["address"].strip().lower()) for shipment in db["shipments"] if shipment["date"] == db["today"]}


def options(db, ticket, report, credit_ok, mistakes=()):
    """{(option, product): (product sent or None, cost per unit)} allowed for one unit of an accepted report."""
    order = db["orders"][report["order"]]
    line = find_line(order, report["sku"])
    paid = makegood.unit_paid(order, line)
    allowed = {("refund", None): (None, paid)}
    if covered(db, order, line["sku"], mistakes):
        return allowed
    constraints = ticket["constraints"]
    blocked = constraints["no_shipping_to"]
    stopped = recalled(db, mistakes)
    if blocked is None or order["address"].strip().lower() != blocked.strip().lower():
        product = db["products"][line["sku"]]
        if line["sku"] not in stopped:
            allowed[("replace", line["sku"])] = (line["sku"], Decimal(product["cost"]))
        if [report["order"], report["sku"]] not in constraints["same_product"]:
            for sku, other in sorted(db["products"].items()):
                if sku != line["sku"] and sku not in stopped and other["family"] == product["family"] and Decimal(other["price"]) >= paid:
                    allowed[("substitute", sku)] = (sku, Decimal(other["cost"]))
    if credit_ok and not constraints["no_credit"]:
        allowed[("credit", None)] = (None, makegood.credit_per_unit(order, line) * makegood.CREDIT_COST)
    return allowed


def solve(db, ticket, reports, credit_ok, mistakes=()):
    """The least cost of making good the accepted reports and entries that reach it: for every set of addresses that
    receive a shipment, a min-cost flow of units to products in stock or to their cheaper money option. Addresses that
    already received a shipment today cost nothing more."""
    free = set() if "no-consolidation" in mistakes else shipped_today(db)
    units, places = [], set()
    for report in reports:
        order = db["orders"][report["order"]]
        place = (order["country"], order["address"].strip().lower())
        allowed = options(db, ticket, report, credit_ok, mistakes)
        sends = {sent: cost for (option, _), (sent, cost) in allowed.items() if option in ("replace", "substitute")}
        cheaper = min((option for option in allowed if option[0] in ("refund", "credit")), key=lambda option: (allowed[option][1], option[0]))
        for _ in range(report["qty"]):
            units.append((place, allowed[cheaper][1], sends, report, cheaper[0]))
        if sends:
            places.add(place)
    if not units:
        return Decimal("0"), []
    capacities = {sku: product.get("stock", 0) for sku, product in db["products"].items() if product.get("stock", 0) > 0}
    best = None
    for size in range(len(places) + 1):
        for shipping in itertools.combinations(sorted(places), size):
            fee = sum((Decimal(db["rates"][country]) for country, address in shipping if (country, address) not in free), Decimal("0"))
            flow_units = [(fallback, {sku: cost for sku, cost in sends.items() if sku in capacities} if place in shipping else {})
                          for place, fallback, sends, _, _ in units]
            cost, choices = makegood.min_cost_flow(flow_units, capacities)
            if best is None or cost + fee < best[0]:
                best = (cost + fee, choices)
    entries = {}
    for (_, _, _, report, cheaper), sent in zip(units, best[1]):
        option = cheaper if sent is None else "replace" if sent == report["sku"] else "substitute"
        key = (report["order"], report["sku"], option, sent)
        entries[key] = entries.get(key, 0) + 1
    return best[0], [{"order": order, "sku": sku, "qty": qty, "option": option, "sent": sent} for (order, sku, option, sent), qty in entries.items()]


def handle(db, ticket, mistakes=()):
    """The oracle for one ticket on a state (not changed): commands, done, declined, the accepted reports with their
    allowed options, whether credit was allowed, and the least make-good cost."""
    db = copy.deepcopy(db)
    customer = verified_customer(db, ticket["sender"])
    credit_ok = customer is not None and goodwill(db, customer, mistakes) < GOODWILL_LIMIT
    count = report_count(db, customer, mistakes) if customer else 0
    commands, done, declined, accepted = [["begin", ticket["id"]]], [], [], []
    for number, request in enumerate(ticket["requests"], 1):
        action = None
        if request["kind"] == "report":
            if report_accepted(db, customer, request):
                if count >= REVIEW_AT:
                    action = ["review", request["order"], request["sku"]]
                    shift_desk.apply(db, action[0], action[1:])
                    commands.append(action)
                    declined.append(number)
                    continue
                accepted.append(request)
                count += 0 if "today-reports" in mistakes else 1
                done.append(number)
                continue
        elif request["kind"] == "return":
            action = decide_return(db, customer, request, mistakes)
        elif request["kind"] == "compensate":
            action = decide_compensation(db, customer, request, credit_ok)
        if action is None:
            declined.append(number)
            continue
        shift_desk.apply(db, action[0], action[1:])
        commands.append(action)
        done.append(number)
    cost, entries = solve(db, ticket, accepted, credit_ok, mistakes)
    allowed = {(report["order"], report["sku"]): options(db, ticket, report, credit_ok) for report in accepted}
    for entry in entries:
        command = ["make-good", entry["order"], entry["sku"], str(entry["qty"]), entry["option"]] + ([entry["sent"]] if entry["option"] == "substitute" else [])
        commands.append(command)
    return {"commands": commands, "done": done, "declined": declined, "accepted": accepted, "allowed": allowed, "credit_ok": credit_ok,
            "cost": cost, "free": shipped_today(db)}


def run(db, tickets, mistakes=()):
    """The whole shift by the oracle: per ticket, its result and the state it began on."""
    db = copy.deepcopy(db)
    results = []
    for ticket in tickets:
        result = handle(db, ticket, mistakes)
        results.append((copy.deepcopy(db), result))
        for command in result["commands"]:
            shift_desk.apply(db, command[0], command[1:])
    return results, db


def mistake_effects(db, tickets):
    """For each misreading, the tickets whose handling by it would fail a check, judged on the true state before each
    ticket (a misreading that changes only the oracle's arithmetic, not what it does, has no effect)."""
    results, _ = run(db, tickets)
    names = check_names(tickets, db)
    effects = {}
    for mistake in MISTAKES:
        effects[mistake] = []
        for ticket, (state, _) in zip(tickets, results):
            wrong = handle(state, ticket, (mistake,))
            checks, _ = judge_ticket(state, ticket, wrong["commands"], {"done": wrong["done"], "declined": wrong["declined"]}, names, True)
            if not all(checks.values()):
                effects[mistake].append(ticket["id"])
    return effects


# Generation.

def generate(seed):
    rng = random.Random(seed)
    for _ in range(3000):
        db, tickets = draft(rng)
        effects = mistake_effects(db, tickets)
        results, _ = run(db, tickets)
        affected = {ticket for touched in effects.values() for ticket in touched}
        makegoods = sum(1 for _, result in results if result["accepted"])
        kinds = {request["kind"] for ticket in tickets for request in ticket["requests"]}
        if all(effects.values()) and len(affected) >= TICKETS // 2 and makegoods >= 4 and kinds == {"report", "return", "compensate"} \
                and sum(len(result["declined"]) for _, result in results) >= 3 and sum(len(result["done"]) for _, result in results) >= 8:
            return db, tickets, effects
    raise RuntimeError("no shift")


def draft(rng):
    """A shop and a shift of eight tickets with planted couplings, plus random requests around them:

    - two households (two customers at one address): the first member's report on an expensive line is likely to be
      made good by sending, so the second member's later report may ship to that address at no carrier rate;
    - a goodwill customer just under the limit, whose first ticket's compensation crosses it, so that their second
      ticket may give no credit; history entries fall on the first counted day and the day before;
    - a review customer two reports short of the threshold, whose first ticket's report reaches it, so that their
      second ticket's report goes to review;
    - a recall that covers one order (a return past its window) and misses another order of the same product, placed
      after the notice's dates (a report that may still be made good by credit or a substitute).
    """
    products = catalogue(rng)
    db = {"today": TODAY.isoformat(), "customers": {}, "orders": {}, "products": products, "recalls": [], "rates": dict(makegood.RATES), "shipments": []}
    ids = [f"C-{4001 + index}" for index in range(8)]
    names = rng.sample(NAMES, 8)
    homes = {}
    for customer in ids:
        country = rng.choice(["UK", "UK", "FR", "DE", "CZ", "NL", "US"])
        homes[customer] = (country, makegood.address(rng, country))
    homes[ids[1]], homes[ids[3]] = homes[ids[0]], homes[ids[2]]
    shippable = [sku for sku in sorted(products) if products[sku]["category"] != "food"]
    numbers = iter(range(8001, 8100))

    def price(sku):
        return Decimal(products[sku]["price"])

    def add_order(customer, days_ago, lines, late=False, home=True, placed_days=None):
        order_id = f"O-{next(numbers)}"
        delivered = TODAY - datetime.timedelta(days=days_ago)
        promised = delivered - datetime.timedelta(days=rng.choice([3, 4, 6]) if late else rng.choice([0, 1, 2]))
        placed = TODAY - datetime.timedelta(days=placed_days) if placed_days is not None else promised - datetime.timedelta(days=rng.randrange(3, 8))
        country, address = homes[customer] if home else (lambda c: (c, makegood.address(rng, c)))(rng.choice(sorted(makegood.RATES)))
        coupon = rng.choice([0, 0, 0, 10, 15, 20])
        rows = [{"sku": sku, "qty": qty, "price": products[sku]["price"], "state": "active", "returned": 0} for sku, qty in lines]
        total = sum((makegood.cents(Decimal(row["price"]) * (100 - coupon) / 100) * row["qty"] for row in rows), Decimal("0"))
        paid_credit = makegood.cents(total * Decimal(rng.choice([0, 0, 0, 20, 50])) / 100)
        db["orders"][order_id] = {"customer": customer, "status": "delivered", "placed": placed.isoformat(), "promised": promised.isoformat(),
                                  "delivered": delivered.isoformat(), "coupon": coupon,
                                  "payments": {"card": money(total - paid_credit), "credit": money(paid_credit)}, "shipping": "0.00",
                                  "address": address, "country": country, "lines": rows, "refunds": [], "compensated": None, "make_good": []}
        return order_id

    def random_lines():
        return [(sku, rng.choice([1, 1, 2, 2, 3])) for sku in rng.sample(shippable, rng.choice([1, 2, 2, 3]))]

    for index, customer in enumerate(ids):
        first, last = names[index].lower().split()
        alternates = [{"address": f"{first}@mail.example", "verified": rng.random() < 0.6}] if rng.random() < 0.4 else []
        db["customers"][customer] = {"name": names[index], "email": f"{first}.{last}@example.com", "alternate_emails": alternates,
                                     "tier": rng.choice(["standard", "standard", "silver", "gold"]), "credit": f"{rng.randrange(0, 30)}.00", "credits": []}
        for _ in range(2):
            add_order(customer, rng.choice([rng.randrange(2, 29), rng.randrange(25, 75)]), random_lines(), late=rng.random() < 0.3, home=rng.random() < 0.8)
    planted = {customer: [] for customer in ids}
    expensive = [sku for sku in shippable if price(sku) >= 60]
    middling = [sku for sku in shippable if 15 <= price(sku) < 60]
    # Households: the first member's expensive line, then the second member's line, both delivered home recently.
    for first, second in ((ids[0], ids[1]), (ids[2], ids[3])):
        sku = rng.choice(expensive)
        products[sku]["stock"] = max(products[sku]["stock"], 2)
        order_id = add_order(first, rng.randrange(3, 20), [(sku, 2)] + random_lines()[:1])
        planted[first].append({"kind": "report", "order": order_id, "sku": sku, "qty": 2, "how": rng.choice(["arrived broken", "arrived damaged"])})
        sku = rng.choice(middling)
        products[sku]["stock"] = max(products[sku]["stock"], 1)
        order_id = add_order(second, rng.randrange(3, 20), [(sku, rng.choice([1, 2]))] + random_lines()[:1])
        line = db["orders"][order_id]["lines"][0]
        planted[second].append({"kind": "report", "order": order_id, "sku": sku, "qty": line["qty"], "how": "was missing from the parcel"})
    # The goodwill customer: two late orders; history just under the limit, less than the first compensation short.
    keeper = ids[4]
    late = [add_order(keeper, rng.randrange(5, 25), [(sku, rng.choice([1, 2])) for sku in rng.sample(expensive, 2)], late=True) for _ in range(2)]
    tier = db["customers"][keeper]["tier"]
    first_total = sum((makegood.unit_paid(db["orders"][late[0]], line) * line["qty"] for line in db["orders"][late[0]]["lines"]), Decimal("0"))
    compensation = makegood.cents(first_total * (Decimal("0.15") if tier == "gold" else Decimal("0.10")))
    history = GOODWILL_LIMIT - compensation + makegood.cents(compensation * Decimal(rng.randrange(20, 80)) / 100)
    history = min(history, GOODWILL_LIMIT - Decimal("0.50"))
    on_boundary = makegood.cents(history * Decimal(rng.randrange(20, 50)) / 100)
    db["customers"][keeper]["credits"] = [
        {"date": (GOODWILL_FROM - datetime.timedelta(days=1)).isoformat(), "amount": money(Decimal(rng.randrange(1000, 3000)) / 100), "kind": "compensation"},
        {"date": GOODWILL_FROM.isoformat(), "amount": money(on_boundary), "kind": "make-good"},
        {"date": (GOODWILL_FROM + datetime.timedelta(days=rng.randrange(3, 25))).isoformat(), "amount": money(history - on_boundary), "kind": "compensation"}]
    recent = add_order(keeper, rng.randrange(3, 20), [(rng.choice(middling), rng.choice([1, 2]))])
    planted[keeper] = [[{"kind": "compensate", "order": late[0]}],
                       [{"kind": "compensate", "order": late[1]},
                        {"kind": "report", "order": recent, "sku": db["orders"][recent]["lines"][0]["sku"], "qty": 1, "how": "arrived damaged"}]]
    # The review customer: reports on the first counted day and inside the period (and one the day before, which does
    # not count); a report in each of their two tickets.
    reviewer = ids[5]
    old = add_order(reviewer, rng.randrange(80, 95), random_lines())
    order = db["orders"][old]
    for day in (REPORTS_FROM - datetime.timedelta(days=1), REPORTS_FROM, REPORTS_FROM + datetime.timedelta(days=rng.randrange(10, 60))):
        line = rng.choice(order["lines"])
        order["make_good"].append({"date": day.isoformat(), "sku": line["sku"], "qty": 1, "option": "refund", "sent": None,
                                   "amount": money(makegood.unit_paid(order, line))})
    order["delivered"] = min(order["delivered"], (REPORTS_FROM - datetime.timedelta(days=2)).isoformat())
    targets = [add_order(reviewer, rng.randrange(3, 25), random_lines()) for _ in range(2)]
    planted[reviewer] = [[{"kind": "report", "order": targets[0], "sku": db["orders"][targets[0]]["lines"][0]["sku"], "qty": 1, "how": "arrived broken"}],
                         [{"kind": "report", "order": targets[1], "sku": db["orders"][targets[1]]["lines"][0]["sku"], "qty": 1, "how": "arrived damaged"}]]
    # The recall: one covered order of household B's first member, delivered long ago; one uncovered order of the
    # second member, placed after the notice's last day.
    recalled_sku = rng.choice([sku for sku in expensive if sum(1 for other in shippable if products[other]["family"] == products[sku]["family"]) > 1])
    covered_order = add_order(ids[2], rng.randrange(38, 55), [(recalled_sku, 1)] + random_lines()[:1])
    placed = date(db["orders"][covered_order]["placed"])
    country = db["orders"][covered_order]["country"]
    countries = sorted(set(rng.sample(sorted(makegood.RATES), rng.randrange(1, 4))) | {country, db["orders"][covered_order]["country"]})
    low, high = placed - datetime.timedelta(days=rng.randrange(1, 8)), placed + datetime.timedelta(days=rng.randrange(1, 8))
    db["recalls"].append({"id": f"RC-{rng.randrange(10, 50)}", "sku": recalled_sku, "placed_from": low.isoformat(), "placed_to": high.isoformat(),
                          "countries": countries})
    uncovered = add_order(ids[3], rng.randrange(3, 15), [(recalled_sku, 1)], placed_days=None)
    if date(db["orders"][uncovered]["placed"]) <= high:
        db["orders"][uncovered]["placed"] = (high + datetime.timedelta(days=rng.randrange(2, 10))).isoformat()
    planted[ids[2]].append({"kind": "return", "order": covered_order, "sku": recalled_sku, "qty": 1, "defective": False})
    planted[ids[3]].append({"kind": "report", "order": uncovered, "sku": recalled_sku, "qty": 1, "how": "arrived damaged"})
    other = rng.choice([sku for sku in shippable if sku != recalled_sku])
    others = [order["placed"] for order in db["orders"].values() if any(line["sku"] == other for line in order["lines"])] or [TODAY.isoformat()]
    low = date(rng.choice(others)) - datetime.timedelta(days=rng.randrange(0, 10))
    db["recalls"].append({"id": f"RC-{rng.randrange(50, 99)}", "sku": other, "placed_from": low.isoformat(),
                          "placed_to": (low + datetime.timedelta(days=rng.randrange(10, 40))).isoformat(),
                          "countries": sorted(rng.sample(sorted(makegood.RATES), rng.randrange(2, 5)))})
    # Other customers' histories, away from the limits.
    for customer in ids[:4] + ids[6:]:
        for _ in range(rng.choice([0, 1, 1, 2])):
            day = GOODWILL_FROM + datetime.timedelta(days=rng.randrange(-20, 29))
            db["customers"][customer]["credits"].append({"date": day.isoformat(), "amount": money(Decimal(rng.randrange(300, 2500)) / 100),
                                                         "kind": rng.choice(["compensation", "make-good"])})
        db["customers"][customer]["credits"].sort(key=lambda entry: entry["date"])
    # The shift: the first four tickets in some order, then the second household members and the returning customers.
    head = [ids[0], ids[2], keeper, reviewer]
    rng.shuffle(head)
    tail = [ids[1], ids[3], keeper, reviewer]
    rng.shuffle(tail)
    if tail[0] == head[-1]:  # no customer writes two tickets in a row, so ticket boundaries can be inferred without markers
        tail[0], tail[1] = tail[1], tail[0]
    tickets, seen = [], set()
    for position, customer in enumerate(head + tail, 1):
        forced = planted[customer]
        if customer in (keeper, reviewer):
            forced = forced[1] if customer in seen else forced[0]
        seen.add(customer)
        tickets.append(make_ticket(rng, db, f"T{position}", customer, forced))
    return db, tickets


def make_ticket(rng, db, ticket_id, customer, forced):
    """A ticket: the planted requests and up to two random ones, in random order."""
    record = db["customers"][customer]
    orders = [order_id for order_id, order in db["orders"].items() if order["customer"] == customer]
    verified = [entry["address"] for entry in record["alternate_emails"] if entry["verified"]]
    sender = verified[0] if verified and rng.random() < 0.4 else record["email"]
    requests = [dict(request) for request in forced]
    kinds = {}
    for request in requests:
        kinds.setdefault(request["order"], set()).add(request["kind"])
    for _ in range(rng.choice([0, 1, 1])):
        order_id = rng.choice(orders)
        line = rng.choice(db["orders"][order_id]["lines"])
        kind = rng.choice(["report", "report", "return", "compensate"])
        # A return and a report never share an order in one ticket, so the store-credit split does not depend on the
        # order in which they are carried out; a line is named once per ticket.
        if kind in ("return", "report") and ("report" if kind == "return" else "return") in kinds.get(order_id, set()):
            continue
        if any(request.get("sku") == line["sku"] and request["order"] == order_id for request in requests):
            continue
        if kind == "compensate":
            if any(request["kind"] == "compensate" and request["order"] == order_id for request in requests):
                continue
            requests.append({"kind": "compensate", "order": order_id})
        elif kind == "return":
            requests.append({"kind": "return", "order": order_id, "sku": line["sku"], "qty": rng.randint(1, line["qty"]),
                             "defective": db["products"][line["sku"]]["category"] == "electronics" and rng.random() < 0.4})
        else:
            requests.append({"kind": "report", "order": order_id, "sku": line["sku"], "qty": rng.randint(1, line["qty"]),
                             "how": rng.choice(["arrived broken", "arrived damaged", "was missing from the parcel"])})
        kinds.setdefault(order_id, set()).add(kind)
    rng.shuffle(requests)
    addresses = sorted({db["orders"][request["order"]]["address"] for request in requests})
    # A customer who refuses store credit never also asks for a compensation, which is paid as store credit.
    constraints = {"no_credit": rng.random() < 0.15 and not any(request["kind"] == "compensate" for request in requests),
                   "no_shipping_to": rng.choice(addresses) if len(addresses) > 1 and rng.random() < 0.25 else None,
                   "same_product": [[request["order"], request["sku"]] for request in requests if request["kind"] == "report" and rng.random() < 0.15]}
    return {"id": ticket_id, "customer": customer, "sender": sender, "requests": requests, "constraints": constraints}


def ticket_text(db, ticket):
    lines = [f"## Ticket {ticket['id']}", "", f"From: {ticket['sender']}", ""]
    intro = []
    if ticket["constraints"]["no_credit"]:
        intro.append("Please do not give me store credit.")
    if ticket["constraints"]["no_shipping_to"]:
        intro.append(f"Please do not send anything to {ticket['constraints']['no_shipping_to']}.")
    if intro:
        lines += [" ".join(intro), ""]
    words = {1: "One", 2: "Two", 3: "Three"}
    for number, request in enumerate(ticket["requests"], 1):
        if request["kind"] == "compensate":
            text = f"Order {request['order']} arrived late. Please compensate me as your policy says."
        else:
            name = db["products"][request["sku"]]["name"].lower()
            noun = name if request["qty"] == 1 or name.endswith("s") else name + "s"
            if request["kind"] == "return":
                text = f"Please take back {words[request['qty']].lower()} {noun} from order {request['order']}." + \
                       (" It does not work." if request["defective"] and request["qty"] == 1 else " They do not work." if request["defective"] else "")
            else:
                verb = request["how"] if request["qty"] == 1 else request["how"].replace("was ", "were ")
                text = f"{words[request['qty']]} {noun} from order {request['order']} {verb}."
                if [request["order"], request["sku"]] in ticket["constraints"]["same_product"]:
                    text += " If you send one, it must be exactly the same model."
        lines.append(f"({number}) {text}")
    return "\n".join(lines)


def prompt(shift_id, db, tickets):
    parts = [f"## Shift {shift_id.upper()}", "",
             f"Today's queue holds {len(tickets)} tickets. Handle them in this order, under POLICY.md, and end with the one JSON reply it describes.", ""]
    for ticket in tickets:
        parts += [ticket_text(db, ticket), ""]
    return "\n".join(parts).rstrip() + "\n"


# Grading.

def segments(commands, tickets, db):
    """The commands of each ticket and the log position where each ticket began. With begin markers, a ticket's
    commands are those after its marker (commands before the first marker belong to no ticket). Without any marker,
    the boundaries are inferred: each command belongs to the current ticket when it touches an order of that ticket's
    customer, and otherwise to the next ticket whose customer's order it touches."""
    by_ticket, start = {}, {}
    if any(command[0] == "begin" for command in commands):
        current = None
        for position, command in enumerate(commands):
            if command[0] == "begin":
                current = command[1]
                start.setdefault(current, position)
                by_ticket.setdefault(current, [])
            elif current is not None:
                by_ticket[current].append(command)
        return by_ticket, start
    owner = lambda command: db["orders"].get(command[1], {}).get("customer") if len(command) > 1 else None  # noqa: E731
    pointer = 0
    for position, command in enumerate(commands):
        customer = owner(command)
        if tickets[pointer]["customer"] != customer:
            later = [index for index in range(pointer + 1, len(tickets)) if tickets[index]["customer"] == customer]
            if later:
                pointer = later[0]
        ticket_id = tickets[pointer]["id"]
        start.setdefault(ticket_id, position)
        by_ticket.setdefault(ticket_id, []).append(command)
    return by_ticket, start


def normalized_others(commands):
    """Returns, compensations and reviews of a ticket, with returns of one line summed, so that a split return compares
    equal to the single command."""
    refunds, others = {}, []
    for command in commands:
        if command[0] == "refund":
            key = (command[1], command[2])
            qty, card, credit = refunds.get(key, (0, Decimal("0"), Decimal("0")))
            refunds[key] = (qty + int(command[3]), card + Decimal(command[4]), credit + Decimal(command[5]))
        elif command[0] not in ("begin", "make-good"):
            others.append(json.dumps(command))
    others += [json.dumps(["refund", order, sku, str(qty), money(card), money(credit)]) for (order, sku), (qty, card, credit) in refunds.items()]
    return sorted(others)


def resolution(state, commands):
    """The make-good entries a ticket's commands create on a state, with the addresses they ship to."""
    db = copy.deepcopy(state)
    before = {order_id: len(order.get("make_good", [])) for order_id, order in db["orders"].items()}
    for command in commands:
        shift_desk.apply(db, command[0], command[1:])
    entries = []
    for order_id, order in db["orders"].items():
        for entry in order.get("make_good", [])[before[order_id]:]:
            entries.append({"order": order_id, **entry})
    return entries


def resolution_cost(state, entries, free):
    total, places = Decimal("0"), {}
    for entry in entries:
        order = state["orders"][entry["order"]]
        if entry["option"] in ("replace", "substitute"):
            total += Decimal(state["products"][entry["sent"]]["cost"]) * entry["qty"]
            place = (order["country"], order["address"].strip().lower())
            if place not in free:
                places[place] = Decimal(state["rates"][order["country"]])
        elif entry["option"] == "refund":
            total += Decimal(entry["amount"])
        else:
            total += Decimal(entry["amount"]) * makegood.CREDIT_COST
    return total + sum(places.values(), Decimal("0"))


def check_names(tickets, base):
    """Each ticket's checks: its reply; its returns, compensations and reviews when it has any; its make-good when it
    accepts reports (every unit made good as allowed, then the cost within 5% of the least and equal to it); and no
    other changes. Check names do not depend on the state, so they come from the oracle's run on the starting data."""
    results, _ = run(base, tickets)
    names = []
    for ticket, (_, result) in zip(tickets, results):
        prefix = ticket["id"].lower()
        names.append(f"{prefix}-reply")
        if normalized_others(result["commands"]):
            names.append(f"{prefix}-actions")
        if result["accepted"]:
            names += [f"{prefix}-makegood", f"{prefix}-cost-5", f"{prefix}-cost-0"]
        names.append(f"{prefix}-clean")
    return names


def judge_ticket(state, ticket, mine, given, names, begun):
    """The checks of one ticket: its commands `mine` and its reply entry `given`, against the oracle on `state`, the
    state when it began. Without a beginning (no marker and, when markers are inferred, no command), only the reply
    can pass, so that an untouched ticket earns nothing for work that happens to be due nowhere in an untouched shop."""
    prefix = ticket["id"].lower()
    results, details = {}, {}
    expected = handle(state, ticket)
    reply_ok = isinstance(given, dict) and isinstance(given.get("done"), list) and isinstance(given.get("declined"), list) and \
        sorted(map(str, given["done"])) == sorted(map(str, expected["done"])) and sorted(map(str, given["declined"])) == sorted(map(str, expected["declined"]))
    results[f"{prefix}-reply"] = reply_ok
    if f"{prefix}-actions" in names:
        results[f"{prefix}-actions"] = begun and normalized_others(mine) == normalized_others(expected["commands"])
    entries = resolution(state, [command for command in mine if command[0] == "make-good"])
    reports = {(report["order"], report["sku"]): report for report in expected["accepted"]}
    made = {key: 0 for key in reports}
    allowed_entries = True
    for entry in entries:
        key = (entry["order"], entry["sku"])
        option = (entry["option"], entry["sent"] if entry["option"] == "substitute" else entry["sku"] if entry["option"] == "replace" else None)
        if key not in reports or option not in expected["allowed"][key]:
            allowed_entries = False
        else:
            made[key] += entry["qty"]
    complete = allowed_entries and all(made[key] == report["qty"] for key, report in reports.items())
    if f"{prefix}-makegood" in names:
        results[f"{prefix}-makegood"] = begun and complete
        results[f"{prefix}-cost-5"] = results[f"{prefix}-cost-0"] = False
        if begun and complete:
            cost = resolution_cost(state, entries, expected["free"])
            results[f"{prefix}-cost-5"] = cost <= expected["cost"] * Decimal("1.05") + Decimal("0.005")
            results[f"{prefix}-cost-0"] = cost <= expected["cost"] + Decimal("0.005")
            details = {"cost": money(cost), "least": money(expected["cost"])}
    # Nothing beyond the ticket: its other commands are the oracle's (or none when it has none), and its make-goods are
    # of accepted reports, as allowed, never more units than reported. A ticket with something to carry out needs it
    # carried out; one that only declines needs the right reply.
    within = allowed_entries and all(made[key] <= report["qty"] for key, report in reports.items()) and \
        set(normalized_others(mine)) <= set(normalized_others(expected["commands"]))
    work = [results[name] for name in (f"{prefix}-actions", f"{prefix}-makegood") if name in results]
    results[f"{prefix}-clean"] = within and (any(work) if work else reply_ok)
    return results, details


def grade_shift(base, tickets, commands, reply):
    """Per ticket, against the oracle on the state when the ticket began. Returns ({check: bool}, cost details)."""
    by_ticket, start = segments(commands, tickets, base)
    names = check_names(tickets, base)
    results, details = {}, {}
    state = copy.deepcopy(base)
    for ticket in tickets:
        if ticket["id"] in start:
            state = copy.deepcopy(base)
            for command in commands[:start[ticket["id"]]]:
                shift_desk.apply(state, command[0], command[1:])
        mine = by_ticket.get(ticket["id"], [])
        given = reply.get(ticket["id"]) if isinstance(reply, dict) else None
        checks, cost = judge_ticket(state, ticket, mine, given, names, ticket["id"] in start)
        results.update(checks)
        if cost:
            details[ticket["id"]] = cost
        for command in mine:
            shift_desk.apply(state, command[0], command[1:])
    return results, details


def build_all():
    """{shift id: (db, tickets, effects)} for every shift."""
    return {shift_id: generate(seed) for shift_id, seed in SHIFTS.items()}


SHIFTS_PATH = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "shifts.json")


def write_all():
    """Generate every shift into shifts.json: its starting data, tickets and which misreadings change which tickets."""
    shifts = {}
    for shift_id, (db, tickets, effects) in build_all().items():
        shifts[shift_id] = {"seed": SHIFTS[shift_id], "db": db, "tickets": tickets, "effects": effects, "prompt": prompt(shift_id, db, tickets)}
    with open(SHIFTS_PATH, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(shifts, indent=1, sort_keys=True) + "\n")


def load():
    try:
        with open(SHIFTS_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except OSError:
        return {}
