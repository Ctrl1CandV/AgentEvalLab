"""SQLite storage. Prices are decimal strings, such as "19.99", and timestamps are UTC, such as "2026-10-03T21:30:00Z"."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT NOT NULL, price TEXT NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL, placed_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS order_lines (order_id INTEGER NOT NULL, sku TEXT NOT NULL, qty INTEGER NOT NULL, unit_price TEXT NOT NULL);
"""


def connect(path):
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.execute("CREATE INDEX IF NOT EXISTS order_lines_by_order ON order_lines (order_id)")
    return connection
