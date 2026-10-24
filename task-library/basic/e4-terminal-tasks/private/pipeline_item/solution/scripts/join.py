"""Adds each sale's region: join.py SALES STORES prints date,amount,store,region rows.

Sales whose store is not in the store list are left out.
"""
import csv
import sys


def main(sales_path, stores_path):
    with open(stores_path, newline="", encoding="utf-8") as handle:
        regions = {int(row["store_id"]): row["region"] for row in csv.DictReader(handle)}
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["date", "amount", "store", "region"])
    with open(sales_path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            region = regions.get(int(row["store"]))
            if region is not None:
                writer.writerow([row["date"], row["amount"], row["store"], region])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
