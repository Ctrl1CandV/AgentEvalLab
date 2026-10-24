import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import report  # noqa: E402


class ReportTest(unittest.TestCase):
    def test_totals_by_month_and_region(self):
        rows = [{"date": "2026-10-01", "amount": "10.005", "region": "North"}, {"date": "2026-10-02", "amount": "5", "region": "North"},
                {"date": "2026-09-30", "amount": "1.10", "region": "South"}]
        self.assertEqual(report.report(rows), [("2026-09", "South", "1.10"), ("2026-10", "North", "15.01")])


if __name__ == "__main__":
    unittest.main()
