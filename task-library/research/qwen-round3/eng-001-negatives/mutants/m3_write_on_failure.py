#!/usr/bin/env python3
import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ref_impl_a as R  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--schema", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--db")
    p.add_argument("--encoding", default="utf-8", choices=["utf-8", "utf-8-sig"])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", dest="dry_run", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = p.parse_args()
    schema, names, pk = R.load_schema(a.schema)
    idx, rows = R.read_rows(a.input, a.encoding, names)
    errors, parsed = R.validate(schema, names, pk, idx, rows)
    if a.apply:
        if not a.db:
            R.fatal("usage", "--apply requires --db")
        errors = errors + R.existing_unique_conflicts(a.db, schema, pk, parsed)
        errors.sort(key=lambda e: (e["record"], e["field"] or ""))
        R.write_db(a.db, schema, names, pk, parsed)  
    for e in errors:
        R.emit(e)
    by = {}
    for e in errors:
        by[e["code"]] = by.get(e["code"], 0) + 1
    R.emit({"summary": {"ok": not errors, "records": len(rows), "errors": len(errors), "by_code": by}})
    return 1 if errors else 0


sys.exit(main())
