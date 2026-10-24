"""Schema 1 shop databases for the migrate item: seeded random ones, and a small one with expectations written by hand."""
import random
import sqlite3

SCHEMA_1 = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT, joined TEXT NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total TEXT NOT NULL, status INTEGER NOT NULL, placed TEXT NOT NULL);
"""
FIRST = ["Ada", "Grace", "Alan", "Mary Ann", "Juana Inés", "Hedy", "Emmy", "Rosalind", "Srinivasa", "Katherine", "Chien-Shiung", "Sofia"]
LAST = ["Lovelace", "Hopper", "Turing", "Evans", "de la Cruz", "Lamarr", "Noether", "Franklin", "Ramanujan", "Johnson", "Wu", "Kovalevskaya"]


def write(path, customers, orders):
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA_1)
    connection.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customers)
    connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)
    connection.commit()
    connection.close()


def name(rng):
    first, last = rng.choice(FIRST), rng.choice(LAST)
    form = rng.random()
    if form < 0.2:
        return f"{last}, {first}"
    if form < 0.3:
        return f"  {first}   {last} "
    if form < 0.35:
        return first.split()[0]
    if form < 0.4:
        return f"{last},{first}"
    return f"{first} {last}"


def amount(rng):
    symbol = rng.choice(["$", "$", "€", "£"])
    whole = rng.choice([rng.randrange(0, 100), rng.randrange(100, 100000), rng.randrange(1000, 5000000)])
    text = f"{whole:,}" if whole >= 1000 and rng.random() < 0.6 else str(whole)
    fraction = rng.choice(["", f".{rng.randrange(10)}", f".{rng.randrange(100):02d}"])
    return symbol + text + fraction


def generated(path, seed, customers=120, orders=400, bad=None):
    """A random schema 1 database. bad: None, or the kind of invalid value to plant in one order."""
    rng = random.Random(seed)
    rows = []
    for identifier in range(1, customers + 1):
        mail = rng.choice([None, "", "   ", f" User{identifier}@Example.COM ", f"user{identifier}@example.org"])
        joined = f"{rng.randrange(1, 29)}/{rng.randrange(1, 13)}/{rng.randrange(2015, 2027)}"
        rows.append((identifier * 3, name(rng), mail, joined))
    ids = [row[0] for row in rows]
    order_rows = []
    for identifier in range(1, orders + 1):
        customer = rng.choice(ids) if rng.random() > 0.05 else rng.choice([None, 1, 2, 100000])
        placed = f"{rng.randrange(1, 29)}/{rng.randrange(1, 13)}/2026 {rng.randrange(0, 24)}:{rng.randrange(60):02d}"
        order_rows.append((1000 + identifier, customer, amount(rng), rng.randrange(4), placed))
    if bad:
        index = rng.randrange(len(order_rows))
        identifier, customer, total, status, placed = order_rows[index]
        total, status, placed = {"total": ("$12,34.00", status, placed), "status": (total, 7, placed), "date": (total, status, "31/2/2026 9:15")}[bad]
        order_rows[index] = (identifier, customer, total, status, placed)
    write(path, rows, order_rows)


# A small database whose schema 2 content was written by hand from the rules in the prompt.
SMALL_CUSTOMERS = [
    (1, "Ada Lovelace", " Ada@Example.COM ", "10/12/2015"),
    (2, "  grace   brewster  hopper ", "", "1/2/2020"),
    (3, "Turing, Alan", None, "23/6/2012"),
    (4, "Plato", "  ", "31/12/2025"),
    (5, "de la Cruz,Juana  Inés", "juana@example.org", "5/11/2019"),
]
SMALL_ORDERS = [
    (10, 1, "$1,234.5", 0, "1/3/2026 9:05"),
    (11, 2, "€12", 1, "15/3/2026 23:59"),
    (12, 3, "£0.07", 2, "2/4/2026 0:00"),
    (13, 9, "$5", 3, "3/4/2026 12:30"),
    (14, None, "$1,000,000.00", 1, "4/4/2026 7:07"),
    (15, 5, "$1234567.89", 3, "28/2/2026 18:45"),
]
SMALL_EXPECTED = {
    "customers": [(1, "Ada", "Lovelace", "ada@example.com", "2015-12-10"), (2, "grace brewster", "hopper", None, "2020-02-01"),
                  (3, "Alan", "Turing", None, "2012-06-23"), (4, "Plato", "", None, "2025-12-31"),
                  (5, "Juana Inés", "de la Cruz", "juana@example.org", "2019-11-05")],
    "orders": [(10, 1, 123450, "USD", "pending", "2026-03-01T09:05"), (11, 2, 1200, "EUR", "paid", "2026-03-15T23:59"),
               (12, 3, 7, "GBP", "shipped", "2026-04-02T00:00"), (15, 5, 123456789, "USD", "cancelled", "2026-02-28T18:45")],
    "migration_log": [(13, "orphan"), (14, "orphan")],
    "schema_version": [(2,)],
}

# The workspace database, and the hidden one the checks migrate.
WORKSPACE = ("m-workspace", 150, 500)
HIDDEN = ("m-hidden", 90, 300)
