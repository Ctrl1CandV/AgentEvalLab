import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class StockroomTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        for name in ("stockroom", "stockroom.toml", "products.csv", "orders-sample.csv"):
            source = os.path.join(HERE, name)
            (shutil.copytree if os.path.isdir(source) else shutil.copy)(source, os.path.join(self.directory, name))
        self.run_cli("init", "products.csv")

    def tearDown(self):
        shutil.rmtree(self.directory)

    def run_cli(self, *args, env=None):
        result = subprocess.run([sys.executable, "-m", "stockroom.cli", *args], cwd=self.directory, capture_output=True, text=True,
                                env={**os.environ, **(env or {})})
        return result

    def test_import_and_report(self):
        self.assertEqual(self.run_cli("import", "orders-sample.csv").stdout.strip(), "imported 3 orders, skipped 0 lines")
        report = json.loads(self.run_cli("report", "2026-10-02").stdout)
        self.assertEqual(report, {"date": "2026-10-02", "orders": 2, "revenue": "61.90", "units": {"BK-101": 2, "PN-201": 1, "WR-301": 1}})

    def test_strict_rejects_unknown_sku(self):
        path = os.path.join(self.directory, "bad.csv")
        with open(path, "w") as handle:
            handle.write("ref,placed,sku,qty\nX-1,2026-10-02T10:00:00+02:00,ZZ-999,1\n")
        self.assertEqual(self.run_cli("import", "bad.csv").returncode, 2)

    def test_restock(self):
        self.assertEqual(self.run_cli("restock", "WR-301", "10").returncode, 0)
        self.assertEqual(self.run_cli("restock", "NOPE", "1").returncode, 2)

    def test_low_stock(self):
        self.assertEqual(self.run_cli("low-stock").stdout, "")
        self.run_cli("import", "orders-sample.csv")

    def test_export(self):
        self.run_cli("import", "orders-sample.csv")
        self.run_cli("export", "out.json")
        with open(os.path.join(self.directory, "out.json")) as handle:
            orders = json.load(handle)
        self.assertEqual([order["ref"] for order in orders], ["S-1001", "S-1002", "S-1003"])
        self.assertEqual(orders[0]["lines"], [{"sku": "BK-101", "qty": 2, "unit_price": "12.50"}, {"sku": "WR-301", "qty": 1, "unit_price": "2.00"}])


if __name__ == "__main__":
    unittest.main()
