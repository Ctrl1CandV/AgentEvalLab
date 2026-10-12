#!/usr/bin/env python3
import argparse
import csv
import datetime
import json
import math
import os
import re
import sqlite3
import sys

VALID_TYPES = {"int", "str", "float", "date", "bool"}
INT_RE = re.compile(r"^[+-]?\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BOOL_TRUE = {"true", "1"}
BOOL_FALSE = {"false", "0"}
NON_FINITE = {"nan", "inf", "-inf", "+inf", "infinity", "-infinity"}

TYPE_MAP = {"int": "INTEGER", "float": "REAL", "str": "TEXT", "bool": "INTEGER", "date": "TEXT"}


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False))


def fatal(code, message):
    emit({"error": {"code": code, "message": message}})
    sys.exit(2)


def load_schema(path):
    if not os.path.isfile(path):
        fatal("schema_error", "schema file not found")
    try:
        with open(path, encoding="utf-8") as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        fatal("schema_error", f"invalid JSON: {e}")
    if not isinstance(schema, dict) or not isinstance(schema.get("columns"), list) or not schema["columns"]:
        fatal("schema_error", "columns (non-empty list) required")
    names = []
    for c in schema["columns"]:
        if not isinstance(c, dict) or "name" not in c or "type" not in c:
            fatal("schema_error", "each column needs name and type")
        if c["type"] not in VALID_TYPES:
            fatal("schema_error", f"unknown type: {c['type']}")
        names.append(c["name"])
    if len(set(names)) != len(names):
        fatal("schema_error", "duplicate column name in schema")
    pk = schema.get("primary_key")
    if pk is None or pk not in names:
        fatal("schema_error", "primary_key must reference a column")
    return schema, names, pk


def coerce(col, raw):
    t = col["type"]
    s = "" if raw is None else raw
    if s.strip() == "":
        return None, None  
    v = s.strip()
    if t == "int":
        if not INT_RE.match(v):
            return None, "type_mismatch"
        return int(v), None
    if t == "float":
        if v.lower() in NON_FINITE:
            return None, "type_mismatch"
        try:
            f = float(v)
        except ValueError:
            return None, "type_mismatch"
        if math.isnan(f) or math.isinf(f):
            return None, "type_mismatch"
        return f, None
    if t == "bool":
        lv = v.lower()
        if lv in BOOL_TRUE:
            return 1, None
        if lv in BOOL_FALSE:
            return 0, None
        return None, "type_mismatch"
    if t == "date":
        if not DATE_RE.match(v):
            return None, "type_mismatch"
        try:
            datetime.date.fromisoformat(v)
        except ValueError:
            return None, "type_mismatch"
        return v, None
    
    return s, None


def check_constraint(col, value):
    if value is None:
        return None
    if col["type"] in ("int", "float"):
        if "min" in col and value < col["min"]:
            return "constraint"
        if "max" in col and value > col["max"]:
            return "constraint"
    if col["type"] == "str" and "maxlength" in col and len(value) > col["maxlength"]:
        return "constraint"
    return None


def read_rows(input_path, encoding, names):
    if not os.path.isfile(input_path):
        fatal("usage", "input file not found")
    if os.path.getsize(input_path) == 0:
        fatal("empty_input", "input file is empty (no header)")
    try:
        f = open(input_path, encoding=encoding, newline="")
    except (UnicodeDecodeError, LookupError) as e:
        fatal("usage", f"cannot read input: {e}")
    reader = csv.reader(f)
    try:
        header = next(reader)
    except StopIteration:
        f.close()
        fatal("empty_input", "input has no header")
    except csv.Error as e:
        f.close()
        fatal("parse_error", f"cannot parse header: {e}")
    if len(set(header)) != len(header):
        f.close()
        fatal("duplicate_header", "duplicate column name in CSV header")
    if set(header) != set(names):
        f.close()
        missing = sorted(set(names) - set(header))
        extra = sorted(set(header) - set(names))
        fatal("header_mismatch", f"header must equal schema columns; missing={missing} extra={extra}")
    idx = {name: i for i, name in enumerate(header)}
    rows = []
    try:
        for r in reader:
            line_num = reader.line_num
            if len(r) != len(header):
                f.close()
                fatal("parse_error", f"ragged row at line {line_num}: got {len(r)} fields, expected {len(header)}")
            rows.append((line_num, r))
    except csv.Error as e:
        f.close()
        fatal("parse_error", f"malformed CSV: {e}")
    f.close()
    return idx, rows


def validate(schema, names, pk, idx, rows):
    cols = {c["name"]: c for c in schema["columns"]}
    unique_cols = [c["name"] for c in schema["columns"] if c.get("unique")]
    errors = []
    parsed_records = []
    seen = {u: {} for u in unique_cols}
    for rec, (line_num, r) in enumerate(rows):
        values = {}
        for name in names:
            col = cols[name]
            raw = r[idx[name]]
            value, code = coerce(col, raw)
            if code is None and value is None and col.get("required"):
                errors.append({"record": rec, "line": line_num, "field": name, "code": "missing_required", "value": raw})
                values[name] = None
                continue
            if code is not None:
                errors.append({"record": rec, "line": line_num, "field": name, "code": code, "value": raw})
                values[name] = None
                continue
            ccode = check_constraint(col, value)
            if ccode:
                errors.append({"record": rec, "line": line_num, "field": name, "code": ccode, "value": raw})
                values[name] = None
                continue
            values[name] = value
        
        for u in unique_cols:
            val = values.get(u)
            if val is None:
                continue
            if val in seen[u]:
                errors.append({"record": rec, "line": line_num, "field": u, "code": "unique_violation",
                               "value": str(val)})
            else:
                seen[u][val] = rec
        parsed_records.append(values)
    errors.sort(key=lambda e: (e["record"], e["field"] or ""))
    return errors, parsed_records


def existing_unique_conflicts(db_path, schema, pk, parsed_records):
    extra = []
    if not os.path.isfile(db_path):
        return extra
    unique_cols = [c["name"] for c in schema["columns"] if c.get("unique") and c["name"] != pk]
    if not unique_cols:
        return extra
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        for u in unique_cols:
            try:
                cur.execute(f"SELECT {pk}, {u} FROM records WHERE {u} IS NOT NULL")
            except sqlite3.Error:
                continue
            table = {}
            for pkv, uv in cur.fetchall():
                table[uv] = pkv
            for rec, vals in enumerate(parsed_records):
                val = vals.get(u)
                if val is None:
                    continue
                if val in table and table[val] != vals.get(pk):
                    extra.append({"record": rec, "line": rec + 2, "field": u, "code": "unique_violation",
                                  "value": str(val)})
    finally:
        con.close()
    return extra


def write_db(db_path, schema, names, pk, parsed_records):
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        coldefs = []
        for c in schema["columns"]:
            d = f"{c['name']} {TYPE_MAP[c['type']]}"
            if c["name"] == pk:
                d += " PRIMARY KEY"
            if c.get("unique") and c["name"] != pk:
                d += " UNIQUE"
            coldefs.append(d)
        cur.execute(f"CREATE TABLE IF NOT EXISTS records ({', '.join(coldefs)})")
        updates = ", ".join(f"{n}=excluded.{n}" for n in names if n != pk)
        placeholders = ", ".join("?" for _ in names)
        sql = (f"INSERT INTO records ({', '.join(names)}) VALUES ({placeholders}) "
               f"ON CONFLICT({pk}) DO UPDATE SET {updates}")
        rows = [tuple(rec[n] for n in names) for rec in parsed_records]
        cur.execute("BEGIN")
        cur.executemany(sql, rows)
        con.commit()
    except sqlite3.Error as e:
        con.rollback()
        con.close()
        fatal("db_error", str(e))
    con.close()


def main(argv=None):
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--schema", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--db")
    p.add_argument("--encoding", default="utf-8", choices=["utf-8", "utf-8-sig"])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", dest="dry_run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)

    schema, names, pk = load_schema(args.schema)
    idx, rows = read_rows(args.input, args.encoding, names)
    errors, parsed = validate(schema, names, pk, idx, rows)

    if args.apply:
        if not args.db:
            fatal("usage", "--apply requires --db")
        errors = errors + existing_unique_conflicts(args.db, schema, pk, parsed)
        errors.sort(key=lambda e: (e["record"], e["field"] or ""))

    for e in errors:
        emit(e)
    by_code = {}
    for e in errors:
        by_code[e["code"]] = by_code.get(e["code"], 0) + 1
    ok = len(errors) == 0
    emit({"summary": {"ok": ok, "records": len(rows), "errors": len(errors), "by_code": by_code}})

    if not ok:
        return 1
    if args.apply:
        write_db(args.db, schema, names, pk, parsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
