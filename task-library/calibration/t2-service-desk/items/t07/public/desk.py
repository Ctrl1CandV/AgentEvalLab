#!/usr/bin/env python3
"""desk.py: the service desk's tool for the shop's data in data/db.json.

    python3 desk.py <command> [arguments]

Look-up commands print JSON. Every command that changes data is appended to data/audit.log. The tool checks that
records exist and that arguments are well formed; it does not check the shop's policy (POLICY.md). That is the job of
whoever uses it.

Commands:
  show-customer CUSTOMER          show-order ORDER          show-product SKU
  orders CUSTOMER                 find-customer EMAIL
  cancel-order ORDER              cancel a whole order; its active lines are refunded to the payment method
  cancel-line ORDER SKU           cancel one line; it is refunded to the payment method
  refund ORDER SKU QTY AMOUNT METHOD   record a refund of QTY units of a line; METHOD is "original" or "credit"
  exchange ORDER SKU NEW_SKU      replace a line's product, keeping quantity and the price paid
  set-address ORDER ADDRESS       replace an order's delivery address
  add-credit CUSTOMER AMOUNT      add store credit to a customer
  compensate ORDER AMOUNT         record a late-delivery compensation and add it to the customer's store credit
"""
import json
import os
import re
import sys
from decimal import Decimal

DB = os.path.join("data", "db.json")
AUDIT = os.path.join("data", "audit.log")
AMOUNT = re.compile(r"^[0-9]+\.[0-9]{2}$")


class Refused(Exception):
    pass


def money(value):
    if not isinstance(value, str) or not AMOUNT.match(value) or Decimal(value) <= 0:
        raise Refused(f"amount must be a positive decimal with two places, such as 12.50: {value!r}")
    return Decimal(value)


def order_of(db, order_id):
    if order_id not in db["orders"]:
        raise Refused(f"no order {order_id}")
    return db["orders"][order_id]


def line_of(order, sku):
    for line in order["lines"]:
        if line["sku"] == sku:
            return line
    raise Refused(f"order has no line {sku}")


def credit(db, customer, amount):
    record = db["customers"][customer]
    record["credit"] = str(Decimal(record["credit"]) + amount)


def refund(order, line, qty, amount, method, kind):
    order["refunds"].append({"sku": line["sku"], "qty": qty, "amount": str(amount), "method": method, "kind": kind})


def apply(db, command, args):
    """Apply one changing command to db; raises Refused for an invalid command."""
    if command == "cancel-order":
        order = order_of(db, args[0])
        if order["status"] == "cancelled":
            raise Refused("order already cancelled")
        for line in order["lines"]:
            if line["state"] == "active":
                line["state"] = "cancelled"
                refund(order, line, line["qty"], Decimal(line["price"]) * line["qty"], "original", "cancellation")
        order["status"] = "cancelled"
    elif command == "cancel-line":
        order = order_of(db, args[0])
        line = line_of(order, args[1])
        if line["state"] != "active":
            raise Refused("line is not active")
        line["state"] = "cancelled"
        refund(order, line, line["qty"], Decimal(line["price"]) * line["qty"], "original", "cancellation")
        if all(other["state"] == "cancelled" for other in order["lines"]):
            order["status"] = "cancelled"
    elif command == "refund":
        order = order_of(db, args[0])
        line = line_of(order, args[1])
        if not args[2].isdigit() or int(args[2]) < 1:
            raise Refused("quantity must be a positive integer")
        qty, amount, method = int(args[2]), money(args[3]), args[4]
        if method not in ("original", "credit"):
            raise Refused("method must be original or credit")
        if qty > line["qty"] - line["returned"]:
            raise Refused("more units than remain on the line")
        line["returned"] += qty
        refund(order, line, qty, amount, method, "return")
        if method == "credit":
            credit(db, order["customer"], amount)
    elif command == "exchange":
        order = order_of(db, args[0])
        line = line_of(order, args[1])
        if args[2] not in db["products"]:
            raise Refused(f"no product {args[2]}")
        line["exchanged_from"] = line["sku"]
        line["sku"] = args[2]
    elif command == "set-address":
        order_of(db, args[0])["address"] = args[1]
    elif command == "add-credit":
        if args[0] not in db["customers"]:
            raise Refused(f"no customer {args[0]}")
        credit(db, args[0], money(args[1]))
    elif command == "compensate":
        order = order_of(db, args[0])
        amount = money(args[1])
        order["compensated"] = str(amount)
        credit(db, order["customer"], amount)
    else:
        raise Refused(f"unknown command {command}")


ARITY = {"cancel-order": 1, "cancel-line": 2, "refund": 5, "exchange": 3, "set-address": 2, "add-credit": 2, "compensate": 2}


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
        return sorted(customer_id for customer_id, customer in db["customers"].items() if customer["email"].lower() == args[0].lower())
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
