"""Command line: python3 -m stockroom.cli <command> ... (see README.md)."""
import argparse
import json
import sys

from . import config as configuration
from . import db, export, importer, inventory, reports


def main(argv=None):
    parser = argparse.ArgumentParser(prog="stockroom")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("products")
    load = commands.add_parser("import")
    load.add_argument("orders")
    restock = commands.add_parser("restock")
    restock.add_argument("sku")
    restock.add_argument("qty", type=int)
    commands.add_parser("low-stock")
    report = commands.add_parser("report")
    report.add_argument("day")
    dump = commands.add_parser("export")
    dump.add_argument("path")
    args = parser.parse_args(argv)
    config = configuration.load()
    connection = db.connect(config.database)
    if args.command == "init":
        inventory.load_products(connection, args.products)
    elif args.command == "import":
        try:
            imported, skipped = importer.import_orders(connection, args.orders, config.strict, config.cache_dir)
        except importer.UnknownSku as error:
            print(f"unknown sku: {error}", file=sys.stderr)
            return 2
        print(f"imported {imported} orders, skipped {skipped} lines")
    elif args.command == "restock":
        try:
            inventory.restock(connection, config, args.sku, args.qty)
        except KeyError:
            print(f"unknown sku: {args.sku}", file=sys.stderr)
            return 2
    elif args.command == "low-stock":
        for sku, stock in inventory.low_stock(connection, config):
            print(f"{sku} {stock}")
    elif args.command == "report":
        print(json.dumps(reports.daily(connection, config, args.day)))
    elif args.command == "export":
        print(f"exported {export.export(connection, args.path)} orders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
