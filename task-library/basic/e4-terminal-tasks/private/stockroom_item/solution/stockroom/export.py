"""Export every order with its lines as JSON."""
import json


def export(connection, path):
    orders = connection.execute("SELECT id, ref, placed_utc FROM orders ORDER BY id").fetchall()
    result = []
    for order_id, ref, placed in orders:
        lines = connection.execute("SELECT sku, qty, unit_price FROM order_lines WHERE order_id = ?", (order_id,)).fetchall()
        result.append({"ref": ref, "placed_utc": placed, "lines": [{"sku": sku, "qty": qty, "unit_price": price} for sku, qty, price in lines]})
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    return len(result)
