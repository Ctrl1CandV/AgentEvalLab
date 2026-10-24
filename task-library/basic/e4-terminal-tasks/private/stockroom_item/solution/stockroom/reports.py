"""Daily sales report."""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo


def daily(connection, config, day):
    """Orders, revenue and units per sku for one calendar day (YYYY-MM-DD) in the shop's timezone."""
    rows = connection.execute("SELECT o.id, o.placed_utc, l.sku, l.qty, l.unit_price FROM orders o JOIN order_lines l ON l.order_id = o.id").fetchall()
    zone = ZoneInfo(config.timezone)
    orders, units, revenue = set(), {}, Decimal(0)
    for order_id, placed, sku, qty, price in rows:
        local = datetime.fromisoformat(placed.replace("Z", "+00:00")).astimezone(zone)
        if local.date().isoformat() != day:
            continue
        orders.add(order_id)
        units[sku] = units.get(sku, 0) + qty
        revenue += Decimal(price) * qty
    revenue = revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"date": day, "orders": len(orders), "revenue": f"{revenue:.2f}", "units": dict(sorted(units.items()))}
