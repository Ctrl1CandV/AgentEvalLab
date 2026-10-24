#!/usr/bin/env python3
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--db")
    ap.add_argument("--encoding", default="utf-8")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", dest="dry_run", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    schema = json.load(open(a.schema, encoding="utf-8"))
    text = open(a.input, encoding=a.encoding).read()
    lines = [l for l in text.split("\n") if l != ""]
    if not lines:
        print(json.dumps({"error": {"code": "empty_input", "message": "empty"}}))
        return 2
    header = lines[0].split(",")  
    errors = []
    rec = 0
    for l in lines[1:]:
        fields = l.split(",")  
        row = dict(zip(header, fields))
        for c in schema["columns"]:
            n = c["name"]
            raw = row.get(n, "")
            if c["type"] == "int" and raw.strip() != "":
                try:
                    int(raw)
                except ValueError:
                    errors.append({"record": rec, "line": rec + 2, "field": n, "code": "type_mismatch", "value": raw})
        rec += 1
    for e in errors:
        print(json.dumps(e, ensure_ascii=False))
    print(json.dumps({"summary": {"ok": not errors, "records": rec, "errors": len(errors), "by_code": {}}}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
