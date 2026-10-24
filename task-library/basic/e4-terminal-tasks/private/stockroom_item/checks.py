#!/usr/bin/env python3
"""Hidden checks of the stockroom item, run inside the sandbox from a directory holding the delivered workspace (its
public/ directory). Prints one JSON object {check: true/false}. Expected values were written by hand from README.md.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
PRODUCTS = "sku,name,price,stock\nBK-101,Linen notebook,12.50,40\nBK-102,Dot grid pad,4.125,25\nPN-201,Fountain pen,34.90,8\nPN-202,Ink cartridges (6),3.335,60\nWR-301,Gift wrap,2.00,6\n"
CONFIG = '[stockroom]\ndatabase = "stockroom.db"\ntimezone = "Europe/Berlin"\nstrict = true\nlow_stock_threshold = 5\ncache_dir = "cache"\n'


class Shop:
    """A fresh working directory with the delivered package, the hidden products and the default configuration."""

    def __init__(self):
        self.directory = tempfile.mkdtemp(prefix="stockroom-check-", dir=ROOT)
        shutil.copytree(os.path.join(ROOT, "stockroom"), os.path.join(self.directory, "stockroom"))
        self.write("stockroom.toml", CONFIG)
        self.write("products.csv", PRODUCTS)
        self.ok = self.cli("init", "products.csv").returncode == 0

    def write(self, name, text):
        with open(os.path.join(self.directory, name), "w", encoding="utf-8") as handle:
            handle.write(text)

    def cli(self, *args, env=None, timeout=60):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("STOCKROOM_")}
        environment.update(env or {})
        try:
            return subprocess.run([sys.executable, "-m", "stockroom.cli", *args], cwd=self.directory, capture_output=True, text=True,
                                  env=environment, timeout=timeout)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args, 124, "", "timeout")

    def orders(self, name, rows):
        self.write(name, "ref,placed,sku,qty\n" + "".join(f"{ref},{placed},{sku},{qty}\n" for ref, placed, sku, qty in rows))
        return name

    def report(self, day, env=None):
        result = self.cli("report", day, env=env)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

    def low_stock(self):
        return self.cli("low-stock").stdout.split("\n")

    def exported(self):
        if self.cli("export", "out.json").returncode != 0:
            return None
        with open(os.path.join(self.directory, "out.json"), encoding="utf-8") as handle:
            return json.load(handle)

    def stock(self, sku):
        connection = sqlite3.connect(os.path.join(self.directory, "stockroom.db"))
        try:
            return connection.execute("SELECT stock FROM products WHERE sku = ?", (sku,)).fetchone()[0]
        finally:
            connection.close()


def check(function):
    try:
        return bool(function())
    except Exception:
        return False


def strict_env():
    mixed = [("E-1", "2026-10-02T10:00:00+02:00", "BK-101", 1), ("E-1", "2026-10-02T10:00:00+02:00", "ZZ-999", 1)]
    for value, expected in (("false", 0), ("OFF", 0), ("0", 0), ("No", 0), ("TRUE", 2), ("on", 2)):
        shop = Shop()
        result = shop.cli("import", shop.orders("mixed.csv", mixed), env={"STOCKROOM_STRICT": value})
        if result.returncode != expected:
            return False
        if expected == 0 and result.stdout.strip() != "imported 1 orders, skipped 1 lines":
            return False
    shop = Shop()
    return shop.cli("import", shop.orders("mixed.csv", mixed)).returncode == 2


def timezone_days():
    shop = Shop()
    shop.cli("import", shop.orders("late.csv", [("T-1", "2026-10-03T23:30:00+02:00", "BK-101", 1), ("T-2", "2026-10-03T23:30:00+00:00", "PN-201", 1),
                                                 ("T-3", "2026-10-04T00:30:00+02:00", "WR-301", 2)]))
    berlin_3 = {"date": "2026-10-03", "orders": 1, "revenue": "12.50", "units": {"BK-101": 1}}
    berlin_4 = {"date": "2026-10-04", "orders": 2, "revenue": "38.90", "units": {"PN-201": 1, "WR-301": 2}}
    new_york_3 = {"date": "2026-10-03", "orders": 3, "revenue": "51.40", "units": {"BK-101": 1, "PN-201": 1, "WR-301": 2}}
    return (shop.report("2026-10-03") == berlin_3 and shop.report("2026-10-04") == berlin_4
            and shop.report("2026-10-03", env={"STOCKROOM_TZ": "America/New_York"}) == new_york_3)


def stock_cache():
    shop = Shop()
    if shop.low_stock() != [""]:
        return False
    shop.cli("import", shop.orders("pens.csv", [("C-1", "2026-10-02T10:00:00+02:00", "PN-201", 4)]))
    if shop.low_stock() != ["PN-201 4", ""]:
        return False
    shop.cli("restock", "PN-201", "10")
    if shop.low_stock() != [""]:
        return False
    shop.cli("import", shop.orders("wrap.csv", [("C-2", "2026-10-02T11:00:00+02:00", "WR-301", 3)]))
    return shop.low_stock() == ["WR-301 3", ""]


def duplicates():
    shop = Shop()
    first = shop.orders("day.csv", [("D-1", "2026-10-02T10:00:00+02:00", "BK-101", 2), ("D-2", "2026-10-02T11:00:00+02:00", "PN-202", 3)])
    shop.cli("import", first)
    shop.cli("import", first)
    shop.cli("import", shop.orders("spaced.csv", [(" D-1 ", "2026-10-02T10:00:00+02:00", "BK-101", 2), ("d-1", "2026-10-02T12:00:00+02:00", "BK-102", 1)]))
    orders = shop.exported()
    return ([order["ref"] for order in orders] == ["D-1", "D-2", "d-1"] and shop.stock("BK-101") == 38 and shop.stock("PN-202") == 57
            and shop.stock("BK-102") == 24)


def money():
    shop = Shop()
    shop.cli("import", shop.orders("cents.csv", [("M-1", "2026-10-05T10:00:00+02:00", "BK-102", 2), ("M-1", "2026-10-05T10:00:00+02:00", "PN-202", 1),
                                                  ("M-2", "2026-10-06T10:00:00+02:00", "PN-202", 3)]))
    return (shop.report("2026-10-05") == {"date": "2026-10-05", "orders": 1, "revenue": "11.59", "units": {"BK-102": 2, "PN-202": 1}}
            and shop.report("2026-10-06") == {"date": "2026-10-06", "orders": 1, "revenue": "10.01", "units": {"PN-202": 3}})


def export_speed():
    """An existing database of 30,000 orders, built with the original schema, must export in under 10 seconds."""
    shop = Shop()
    connection = sqlite3.connect(os.path.join(shop.directory, "stockroom.db"))
    skus = ["BK-101", "BK-102", "PN-201", "PN-202", "WR-301"]
    prices = {"BK-101": "12.50", "BK-102": "4.125", "PN-201": "34.90", "PN-202": "3.335", "WR-301": "2.00"}
    expected = []
    for number in range(1, 30001):
        ref, placed = f"B-{number:05d}", f"2026-09-{number % 28 + 1:02d}T{number % 24:02d}:{number % 60:02d}:00Z"
        order_id = connection.execute("INSERT INTO orders (ref, placed_utc) VALUES (?, ?)", (ref, placed)).lastrowid
        lines = [(skus[(number + index) % 5], (number * 7 + index) % 9 + 1) for index in range(3)]
        for sku, qty in lines:
            connection.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)", (order_id, sku, qty, prices[sku]))
        expected.append({"ref": ref, "placed_utc": placed, "lines": [{"sku": sku, "qty": qty, "unit_price": prices[sku]} for sku, qty in lines]})
    connection.commit()
    connection.close()
    start = time.monotonic()
    result = shop.cli("export", "out.json", timeout=30)
    elapsed = time.monotonic() - start
    if result.returncode != 0 or elapsed > 10:
        return False
    with open(os.path.join(shop.directory, "out.json"), encoding="utf-8") as handle:
        return json.load(handle) == expected


def regression():
    """Behaviour that already worked must still work: the shipped tests and the documented outputs."""
    shop = Shop()
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    if tests.returncode != 0:
        return False
    sample = shop.orders("sample.csv", [("R-1", "2026-10-02T09:15:00+02:00", "BK-101", 2), ("R-1", "2026-10-02T09:15:00+02:00", "WR-301", 1),
                                        ("R-2", "2026-10-02T14:40:00+02:00", "PN-201", 1)])
    if shop.cli("import", sample).stdout.strip() != "imported 2 orders, skipped 0 lines":
        return False
    return (shop.report("2026-10-02") == {"date": "2026-10-02", "orders": 2, "revenue": "61.90", "units": {"BK-101": 2, "PN-201": 1, "WR-301": 1}}
            and shop.report("2026-10-09") == {"date": "2026-10-09", "orders": 0, "revenue": "0.00", "units": {}}
            and shop.cli("restock", "NOPE", "1").returncode == 2 and shop.cli("restock", "WR-301", "1").returncode == 0 and shop.stock("WR-301") == 6)


CHECKS = {"strict-env": strict_env, "timezone": timezone_days, "stock-cache": stock_cache, "duplicates": duplicates, "money": money,
          "export-speed": export_speed, "regression": regression}

if __name__ == "__main__":
    results = {name: check(function) for name, function in CHECKS.items()}
    # The regression check guards the fixes, so it counts only once some symptom is fixed: the shipped code passes it.
    results["regression"] = results["regression"] and any(value for name, value in results.items() if name != "regression")
    print(json.dumps(results))
