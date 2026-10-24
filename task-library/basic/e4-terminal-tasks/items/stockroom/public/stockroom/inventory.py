"""Products and stock."""
import csv

from . import cache


def load_products(connection, path):
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            connection.execute("INSERT OR REPLACE INTO products VALUES (?, ?, ?, ?)", (row["sku"], row["name"], row["price"], int(row["stock"])))
    connection.commit()


def restock(connection, config, sku, qty):
    updated = connection.execute("UPDATE products SET stock = stock + ? WHERE sku = ?", (qty, sku)).rowcount
    connection.commit()
    if not updated:
        raise KeyError(sku)


def low_stock(connection, config):
    """Products whose stock is below the threshold, as [sku, stock] pairs ordered by sku."""
    cached = cache.get(config.cache_dir, "low-stock")
    if cached is not None:
        return cached
    rows = connection.execute("SELECT sku, stock FROM products WHERE stock < ? ORDER BY sku", (config.low_stock_threshold,)).fetchall()
    value = [[sku, stock] for sku, stock in rows]
    cache.put(config.cache_dir, "low-stock", value)
    return value
