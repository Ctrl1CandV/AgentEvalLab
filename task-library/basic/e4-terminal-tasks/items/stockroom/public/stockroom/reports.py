"""Daily sales report."""


def daily(connection, config, day):
    """Orders, revenue and units per sku for one calendar day (YYYY-MM-DD) in the shop's timezone."""
    rows = connection.execute("SELECT o.id, o.placed_utc, l.sku, l.qty, l.unit_price FROM orders o JOIN order_lines l ON l.order_id = o.id").fetchall()
    orders, units, revenue = set(), {}, 0.0
    for order_id, placed, sku, qty, price in rows:
        if placed[:10] != day:
            continue
        orders.add(order_id)
        units[sku] = units.get(sku, 0) + qty
        revenue += float(price) * qty
    return {"date": day, "orders": len(orders), "revenue": f"{revenue:.2f}", "units": dict(sorted(units.items()))}
