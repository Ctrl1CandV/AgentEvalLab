"""Monthly revenue per region: report.py JOINED prints month,region,revenue rows, ordered by month, then region."""
import csv
import sys
from decimal import ROUND_HALF_UP, Decimal


def report(rows):
    totals = {}
    for row in rows:
        key = (row["date"][:7], row["region"])
        totals[key] = totals.get(key, Decimal(0)) + Decimal(row["amount"])
    return [(month, region, str(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))) for (month, region), total in sorted(totals.items())]


def main(path):
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["month", "region", "revenue"])
    writer.writerows(report(rows))


if __name__ == "__main__":
    main(sys.argv[1])
