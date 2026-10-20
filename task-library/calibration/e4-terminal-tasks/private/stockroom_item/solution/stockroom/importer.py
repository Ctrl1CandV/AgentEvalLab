"""Import orders from a CSV export with the columns ref, placed, sku, qty; one row per order line.

placed is an ISO 8601 timestamp with a UTC offset, such as 2026-10-03T23:30:00+02:00.
"""
import csv
from datetime import datetime, timezone

from . import cache


class UnknownSku(Exception):
    pass


def import_orders(connection, path, strict, cache_dir=None):
    """Returns (orders imported, lines skipped)."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    prices = dict(connection.execute("SELECT sku, price FROM products"))
    orders = {}
    for row in rows:
        orders.setdefault(row["ref"].strip(), {"placed": row["placed"], "lines": []})["lines"].append((row["sku"], int(row["qty"])))
    imported = skipped = 0
    for ref, order in orders.items():
        if connection.execute("SELECT 1 FROM orders WHERE ref = ?", (ref,)).fetchone():
            continue
        placed = datetime.fromisoformat(order["placed"]).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = []
        for sku, qty in order["lines"]:
            if sku not in prices:
                if strict:
                    raise UnknownSku(sku)
                skipped += 1
                continue
            lines.append((sku, qty, prices[sku]))
        if not lines:
            continue
        order_id = connection.execute("INSERT INTO orders (ref, placed_utc) VALUES (?, ?)", (ref, placed)).lastrowid
        for sku, qty, price in lines:
            connection.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)", (order_id, sku, qty, price))
            connection.execute("UPDATE products SET stock = stock - ? WHERE sku = ?", (qty, sku))
        imported += 1
    connection.commit()
    if cache_dir is not None:
        cache.invalidate(cache_dir, "low-stock")
    return imported, skipped
