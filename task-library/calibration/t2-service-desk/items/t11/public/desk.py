#!/usr/bin/env python3
"""desk.py: the service desk's tool for the shop's data in data/db.json.

    python3 desk.py <command> [arguments]

Look-up commands print JSON. Every command that changes data is appended to data/audit.log. The tool checks that
records exist and that arguments are well formed; it does not check the shop's policy (POLICY.md). That is the job of
whoever uses it. Amounts are euros with two decimals, such as 12.50 or 0.00.

Commands:
  show-customer CUSTOMER            show-order ORDER            show-product SKU
  orders CUSTOMER                   find-customer EMAIL         products FAMILY
  cancel-order ORDER                cancel a whole order: its active lines and its shipping fee are refunded
  cancel-line ORDER SKU             cancel one line; it is refunded, and when no active line remains the order is
                                    cancelled and its shipping fee refunded too
  refund ORDER SKU QTY CARD CREDIT  record a return of QTY units of a line, refunded with CARD to the card and CREDIT
                                    as store credit
  exchange ORDER SKU NEW_SKU        replace a line's product, keeping its quantity and the price paid
  add-credit CUSTOMER AMOUNT        add store credit to a customer
  adjust-price ORDER SKU AMOUNT     record a price-drop refund for a line, added to the customer's store credit
  compensate ORDER AMOUNT           record a late-order compensation, added to the customer's store credit
  set-address ORDER ADDRESS         replace an order's delivery address

Cancellations refund store credit first, up to the part of the order paid with store credit or a gift card
(payments.credit) that earlier refunds of the order have not yet returned as store credit, and the rest to the card.
"""
import json
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

DB = os.path.join("data", "db.json")
AUDIT = os.path.join("data", "audit.log")
AMOUNT = re.compile(r"^[0-9]+\.[0-9]{2}$")
CENT = Decimal("0.01")


class Refused(Exception):
    pass


def money(value, positive=True):
    if not isinstance(value, str) or not AMOUNT.match(value) or (positive and Decimal(value) <= 0):
        raise Refused(f"amount must be a {'positive ' if positive else ''}decimal with two places, such as 12.50: {value!r}")
    return Decimal(value)


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def order_of(db, order_id):
    if order_id not in db["orders"]:
        raise Refused(f"no order {order_id}")
    return db["orders"][order_id]


def line_of(order, sku):
    for line in order["lines"]:
        if line["sku"] == sku:
            return line
    raise Refused(f"order has no line {sku}")


def unit_paid(order, line):
    return cents(Decimal(line["price"]) * (100 - order["coupon"]) / 100)


def add_credit(db, customer, amount):
    record = db["customers"][customer]
    record["credit"] = str(Decimal(record["credit"]) + amount)


def credit_left(order):
    """The part of the order paid with store credit that its refunds have not yet returned as store credit."""
    returned = sum((Decimal(refund["credit"]) for refund in order["refunds"]), Decimal("0"))
    return max(Decimal(order["payments"]["credit"]) - returned, Decimal("0"))


def pay_back(db, order, sku, qty, amount, kind):
    """A cancellation refund: store credit first, then the card."""
    credit = min(amount, credit_left(order))
    order["refunds"].append({"sku": sku, "qty": qty, "card": str(amount - credit), "credit": str(credit), "kind": kind})
    if credit > 0:
        add_credit(db, order["customer"], credit)


def cancel_line(db, order, line):
    line["state"] = "cancelled"
    pay_back(db, order, line["sku"], line["qty"], unit_paid(order, line) * line["qty"], "cancellation")
    if all(other["state"] == "cancelled" for other in order["lines"]):
        order["status"] = "cancelled"
        if Decimal(order["shipping"]) > 0:
            pay_back(db, order, "SHIPPING", 0, Decimal(order["shipping"]), "cancellation")


def apply(db, command, args):
    """Apply one changing command to db; raises Refused for an invalid command."""
    if command == "cancel-order":
        order = order_of(db, args[0])
        if order["status"] == "cancelled":
            raise Refused("order already cancelled")
        active = [line for line in order["lines"] if line["state"] == "active"]
        if not active:
            raise Refused("order has no active line")
        for line in active:
            cancel_line(db, order, line)
    elif command == "cancel-line":
        order = order_of(db, args[0])
        line = line_of(order, args[1])
        if line["state"] != "active":
            raise Refused("line is not active")
        cancel_line(db, order, line)
    elif command == "refund":
        order = order_of(db, args[0])
        line = line_of(order, args[1])
        if not args[2].isdigit() or int(args[2]) < 1:
            raise Refused("quantity must be a positive integer")
        qty, card, credit = int(args[2]), money(args[3], positive=False), money(args[4], positive=False)
        if card + credit <= 0:
            raise Refused("the refund must be above zero")
        if qty > line["qty"] - line["returned"]:
            raise Refused("more units than remain on the line")
        line["returned"] += qty
        order["refunds"].append({"sku": line["sku"], "qty": qty, "card": str(card), "credit": str(credit), "kind": "return"})
        if credit > 0:
            add_credit(db, order["customer"], credit)
    elif command == "exchange":
        order = order_of(db, args[0])
        line = line_of(order, args[1])
        if args[2] not in db["products"]:
            raise Refused(f"no product {args[2]}")
        if any(other["sku"] == args[2] for other in order["lines"]):
            raise Refused(f"order already has a line {args[2]}")
        line["exchanged_from"] = line["sku"]
        line["sku"] = args[2]
    elif command == "add-credit":
        if args[0] not in db["customers"]:
            raise Refused(f"no customer {args[0]}")
        add_credit(db, args[0], money(args[1]))
    elif command == "adjust-price":
        order = order_of(db, args[0])
        line = line_of(order, args[1])
        amount = money(args[2])
        line["price_adjustment"] = str(amount)
        add_credit(db, order["customer"], amount)
    elif command == "compensate":
        order = order_of(db, args[0])
        amount = money(args[1])
        order["compensated"] = str(amount)
        add_credit(db, order["customer"], amount)
    elif command == "set-address":
        order_of(db, args[0])["address"] = args[1]
    else:
        raise Refused(f"unknown command {command}")


ARITY = {"cancel-order": 1, "cancel-line": 2, "refund": 5, "exchange": 3, "add-credit": 2, "adjust-price": 3, "compensate": 2,
         "set-address": 2}


def show(db, command, args):
    if command == "show-customer":
        return db["customers"].get(args[0])
    if command == "show-order":
        return db["orders"].get(args[0])
    if command == "show-product":
        return db["products"].get(args[0])
    if command == "orders":
        return sorted(order_id for order_id, order in db["orders"].items() if order["customer"] == args[0])
    if command == "find-customer":
        addresses = lambda customer: [customer["email"]] + [entry["address"] for entry in customer["alternate_emails"]]  # noqa: E731
        return sorted(customer_id for customer_id, customer in db["customers"].items()
                      if any(address.lower() == args[0].lower() for address in addresses(customer)))
    if command == "products":
        return {sku: product for sku, product in sorted(db["products"].items()) if product["family"] == args[0]}
    raise Refused(f"unknown command {command}")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, args = argv[0], argv[1:]
    with open(DB, encoding="utf-8") as handle:
        db = json.load(handle)
    try:
        if command in ARITY:
            if len(args) != ARITY[command]:
                raise Refused(f"{command} takes {ARITY[command]} arguments")
            apply(db, command, args)
            with open(DB, "w", encoding="utf-8") as handle:
                json.dump(db, handle, indent=1, sort_keys=True)
            with open(AUDIT, "a", encoding="utf-8") as handle:
                handle.write(json.dumps([command, *args]) + "\n")
            print("ok")
        else:
            if len(args) != 1:
                raise Refused(f"{command} takes 1 argument")
            print(json.dumps(show(db, command, args), indent=1, sort_keys=True))
    except Refused as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
