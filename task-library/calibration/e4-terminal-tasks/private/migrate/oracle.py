#!/usr/bin/env python3
"""Oracle solution of the migrate item: migrates a schema 1 shop database to schema 2 in place."""
import datetime
import re
import sqlite3
import sys

CURRENCIES = {"$": "USD", "€": "EUR", "£": "GBP"}
STATUSES = {0: "pending", 1: "paid", 2: "shipped", 3: "cancelled"}
AMOUNT = re.compile(r"^([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.([0-9]{1,2}))?$")
DAY = re.compile(r"^([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})$")
MOMENT = re.compile(r"^([0-9]{1,2})/([0-9]{1,2})/([0-9]{4}) ([0-9]{1,2}):([0-9]{2})$")
SCHEMA = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL, email TEXT, joined TEXT NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), total_cents INTEGER NOT NULL,
                     currency TEXT NOT NULL, status TEXT NOT NULL, placed TEXT NOT NULL);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE TABLE migration_log (order_id INTEGER NOT NULL, reason TEXT NOT NULL);
CREATE TABLE schema_version (version INTEGER NOT NULL);
"""


class Invalid(Exception):
    pass


def split_name(name):
    name = " ".join(name.split())
    if "," in name:
        last, first = name.split(",", 1)
        return first.strip(), last.strip()
    words = name.split(" ")
    return (" ".join(words[:-1]), words[-1]) if len(words) > 1 else (name, "")


def email(value):
    if value is None:
        return None
    value = value.strip().lower()
    return value or None


def day(value):
    match = DAY.match(value)
    if not match:
        raise Invalid()
    try:
        return datetime.date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
    except ValueError:
        raise Invalid() from None


def moment(value):
    match = MOMENT.match(value)
    if not match:
        raise Invalid()
    d, m, y, hour, minute = (int(part) for part in match.groups())
    try:
        return datetime.datetime(y, m, d, hour, minute).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        raise Invalid() from None


def total(value):
    if not value or value[0] not in CURRENCIES:
        raise Invalid()
    match = AMOUNT.match(value[1:])
    if not match:
        raise Invalid()
    whole = int(match.group(1).replace(",", ""))
    fraction = (match.group(2) or "").ljust(2, "0")
    return whole * 100 + int(fraction or 0), CURRENCIES[value[0]]


def migrate(path):
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "schema_version" in tables:
            return
        customers = []
        for identifier, name, mail, joined in connection.execute("SELECT id, name, email, joined FROM customers ORDER BY id"):
            first, last = split_name(name)
            customers.append((identifier, first, last, email(mail), day(joined)))
        known = {row[0] for row in customers}
        orders, log = [], []
        for identifier, customer, amount, status, placed in connection.execute("SELECT id, customer_id, total, status, placed FROM orders ORDER BY id"):
            cents, currency = total(amount)
            if status not in STATUSES:
                raise Invalid()
            when = moment(placed)
            if customer is None or customer not in known:
                log.append((identifier, "orphan"))
                continue
            orders.append((identifier, customer, cents, currency, STATUSES[status], when))
        connection.execute("BEGIN")
        try:
            connection.execute("DROP TABLE orders")
            connection.execute("DROP TABLE customers")
            for statement in SCHEMA.strip().split(";\n"):
                connection.execute(statement)
            connection.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers)
            connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", orders)
            connection.executemany("INSERT INTO migration_log VALUES (?, ?)", log)
            connection.execute("INSERT INTO schema_version VALUES (2)")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    finally:
        connection.close()


def main():
    try:
        migrate(sys.argv[1])
    except Invalid:
        print("migration failed: invalid data; the database is unchanged", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
