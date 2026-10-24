"""POLICY.md as code: derives each ticket's desk.py commands and done/declined lists from the structured intents in
tickets.py, independently of the commands written there by hand. The self-calibration checks that both agree."""
import copy
import datetime
from decimal import ROUND_HALF_UP, Decimal

import desk
import tickets

TODAY = datetime.date(2026, 10, 20)
CENT = Decimal("0.01")
WINDOWS = {"books": 14, "clothing": 60}
FEES = {"standard": Decimal("0.15"), "silver": Decimal("0.10"), "gold": Decimal("0")}


def date(text):
    return datetime.date.fromisoformat(text)


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def text(value):
    return f"{value:.2f}"


def verified_customer(db, sender):
    for customer_id, customer in db["customers"].items():
        if customer["email"].lower() == sender.lower():
            return customer_id
        if any(entry["address"].lower() == sender.lower() and entry["verified"] for entry in customer["alternate_emails"]):
            return customer_id
    return None


def unit_paid(order, line):
    return cents(Decimal(line["price"]) * (100 - order["coupon"]) / 100)


def find_line(order, sku):
    return next((line for line in order["lines"] if line["sku"] == sku), None)


def in_window(db, order, line):
    product = db["products"][line["sku"]]
    if order["status"] != "delivered" or product["category"] == "food" or product["final_sale"]:
        return False
    days = WINDOWS.get(product["category"], 30) + (15 if db["customers"][order["customer"]]["tier"] == "gold" else 0)
    return (TODAY - date(order["delivered"])).days <= days


def credit_left(order):
    returned = sum((Decimal(refund["credit"]) for refund in order["refunds"]), Decimal("0"))
    return max(Decimal(order["payments"]["credit"]) - returned, Decimal("0"))


def late(order):
    if order["status"] == "cancelled":
        return False
    if order["delivered"]:
        return (date(order["delivered"]) - date(order["promised"])).days >= 3
    return (TODAY - date(order["promised"])).days >= 3


def decide(db, customer_id, intent):
    """The commands that carry out one request, or None when the policy declines it."""
    kind = intent["kind"]
    if kind in ("goodwill", "unidentified") or customer_id is None:
        return None
    order = db["orders"].get(intent["order"])
    if order is None or order["customer"] != customer_id:
        return None
    tier = db["customers"][customer_id]["tier"]
    if kind == "set-address":
        return [["set-address", intent["order"], intent["address"]]] if order["status"] in ("pending", "processing") else None
    if kind == "cancel-line":
        line = find_line(order, intent["sku"])
        ok = order["status"] in ("pending", "processing") and line is not None and line["state"] == "active"
        return [["cancel-line", intent["order"], intent["sku"]]] if ok else None
    if kind == "compensate":
        if not late(order) or order["compensated"] is not None:
            return None
        total = sum((unit_paid(order, line) * line["qty"] for line in order["lines"]), Decimal("0"))
        rate = Decimal("0.15") if tier == "gold" else Decimal("0.10")
        return [["compensate", intent["order"], text(cents(total * rate))]]
    line = find_line(order, intent["sku"])
    if line is None or line["state"] != "active":
        return None
    product = db["products"][line["sku"]]
    if kind == "return":
        if not in_window(db, order, line) or intent["qty"] > line["qty"] - line["returned"]:
            return None
        amount = unit_paid(order, line) * intent["qty"]
        fee = Decimal("0") if product["category"] != "electronics" or intent["defective"] else cents(amount * FEES[tier])
        refund = amount - fee
        credit = min(refund, credit_left(order))
        return [["refund", intent["order"], intent["sku"], str(intent["qty"]), text(refund - credit), text(credit)]]
    if kind == "exchange":
        new = db["products"][intent["new"]]
        paid = unit_paid(order, line)
        if not in_window(db, order, line) or line["returned"] or "exchanged_from" in line or new["family"] != product["family"] \
                or Decimal(new["price"]) > paid:
            return None
        commands = [["exchange", intent["order"], intent["sku"], intent["new"]]]
        difference = (paid - Decimal(new["price"])) * line["qty"]
        return commands + ([["add-credit", customer_id, text(difference)]] if difference > 0 else [])
    if kind == "price-drop":
        paid, current = unit_paid(order, line), Decimal(product["price"])
        recent = order["status"] == "delivered" and date(order["delivered"]) >= TODAY - datetime.timedelta(days=7)
        if not recent or current >= paid or "price_adjustment" in line:
            return None
        return [["adjust-price", intent["order"], intent["sku"], text((paid - current) * (line["qty"] - line["returned"]))]]
    raise ValueError(kind)


def handle(ticket_id):
    """The ticket's commands and done/declined lists, applying each request before the next."""
    ticket = tickets.TICKETS[ticket_id]
    db = copy.deepcopy(tickets.BASE_DB)
    customer_id = verified_customer(db, ticket["sender"])
    commands, done, declined = [], [], []
    for number, entry in enumerate(ticket["requests"], 1):
        actions = decide(db, customer_id, entry["intent"])
        if actions is None:
            declined.append(number)
            continue
        for action in actions:
            desk.apply(db, action[0], action[1:])
        commands += actions
        done.append(number)
    return commands, done, declined
