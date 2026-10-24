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

TYPES = {"int", "str", "float", "date", "bool"}
SQLTYPE = {"int": "INTEGER", "float": "REAL", "str": "TEXT", "bool": "INTEGER", "date": "TEXT"}
_RE_INT = re.compile(r"^[+-]?\d+$")
_RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BAD_FLOAT = {"nan", "inf", "-inf", "+inf", "infinity", "-infinity"}


def out(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def bail(code, msg):
    out({"error": {"code": code, "message": msg}})
    raise SystemExit(2)



def _t_int(s):
    return (int(s), True) if _RE_INT.match(s) else (None, False)


def _t_float(s):
    if s.lower() in _BAD_FLOAT:
        return None, False
    try:
        f = float(s)
    except ValueError:
        return None, False
    return (None, False) if (math.isnan(f) or math.isinf(f)) else (f, True)


def _t_bool(s):
    return (1, True) if s.lower() in {"true", "1"} else ((0, True) if s.lower() in {"false", "0"} else (None, False))


def _t_date(s):
    if not _RE_DATE.match(s):
        return None, False
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return None, False
    return s, True


def _t_str(s):
    return s, True


_DISPATCH = {"int": _t_int, "float": _t_float, "bool": _t_bool, "date": _t_date, "str": _t_str}


def load_schema(path):
    if not os.path.isfile(path):
        bail("schema_error", "schema not found")
    try:
        sch = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError as e:
        bail("schema_error", f"bad JSON: {e}")
    cols = sch.get("columns") if isinstance(sch, dict) else None
    if not isinstance(cols, list) or not cols:
        bail("schema_error", "columns required")
    names = []
    for c in cols:
        if not isinstance(c, dict) or "name" not in c or c.get("type") not in TYPES:
            bail("schema_error", "bad column type/name")
        names.append(c["name"])
    if len(set(names)) != len(names):
        bail("schema_error", "duplicate column")
    if sch.get("primary_key") not in names:
        bail("schema_error", "primary_key invalid")
    return sch, names, sch["primary_key"]


def open_csv(path, encoding, names):
    if not os.path.isfile(path):
        bail("usage", "input not found")
    if os.path.getsize(path) == 0:
        bail("empty_input", "empty file")
    fh = open(path, encoding=encoding, newline="")
    rd = csv.reader(fh)
    try:
        header = next(rd)
    except StopIteration:
        fh.close(); bail("empty_input", "no header")
    except csv.Error as e:
        fh.close(); bail("parse_error", str(e))
    if len(set(header)) != len(header):
        fh.close(); bail("duplicate_header", "dup header")
    if set(header) != set(names):
        fh.close(); bail("header_mismatch", "header != schema columns")
    recs = []
    try:
        for row in rd:
            ln = rd.line_num
            if len(row) != len(header):
                fh.close(); bail("parse_error", f"ragged row line {ln}")
            recs.append((ln, dict(zip(header, row))))
    except csv.Error as e:
        fh.close(); bail("parse_error", str(e))
    fh.close()
    return recs


def field_value(col, raw):
    if raw is None or raw.strip() == "":
        return None, None
    val, ok = _DISPATCH[col["type"]](raw.strip() if col["type"] != "str" else raw)
    if not ok:
        return None, "type_mismatch"
    if col["type"] in ("int", "float"):
        if ("min" in col and val < col["min"]) or ("max" in col and val > col["max"]):
            return None, "constraint"
    if col["type"] == "str" and "maxlength" in col and len(val) > col["maxlength"]:
        return None, "constraint"
    return val, None


def validate(sch, names, recs):
    cols = {c["name"]: c for c in sch["columns"]}
    uniq = [c["name"] for c in sch["columns"] if c.get("unique")]
    errs = []
    parsed = []
    seen = {u: set() for u in uniq}
    for rec, (ln, row) in enumerate(recs):
        vals = {}
        rec_errs = []
        for n in names:
            col = cols[n]
            raw = row[n]
            v, code = field_value(col, raw)
            if v is None and code is None and col.get("required"):
                rec_errs.append((n, "missing_required", raw))
            elif code is not None:
                rec_errs.append((n, code, raw))
            vals[n] = v
        for u in uniq:
            if vals.get(u) is not None:
                if vals[u] in seen[u]:
                    rec_errs.append((u, "unique_violation", str(vals[u])))
                else:
                    seen[u].add(vals[u])
        for (n, code, raw) in sorted(rec_errs, key=lambda x: x[0]):
            errs.append({"record": rec, "line": ln, "field": n, "code": code, "value": raw})
        parsed.append(vals)
    errs.sort(key=lambda e: (e["record"], e["field"]))
    return errs, parsed


def existing_conflicts(db, sch, pk, parsed):
    extra = []
    if not os.path.isfile(db):
        return extra
    uniq = [c["name"] for c in sch["columns"] if c.get("unique") and c["name"] != pk]
    if not uniq:
        return extra
    con = sqlite3.connect(db)
    for u in uniq:
        try:
            rows = con.execute(f"SELECT {pk},{u} FROM records WHERE {u} IS NOT NULL").fetchall()
        except sqlite3.Error:
            continue
        m = {uv: pkv for pkv, uv in rows}
        for rec, vals in enumerate(parsed):
            if vals.get(u) is not None and vals[u] in m and m[vals[u]] != vals.get(pk):
                extra.append({"record": rec, "line": rec + 2, "field": u, "code": "unique_violation", "value": str(vals[u])})
    con.close()
    return extra


def persist(db, sch, names, pk, parsed):
    con = sqlite3.connect(db)
    try:
        defs = ", ".join(f"{c['name']} {SQLTYPE[c['type']]}" + (" PRIMARY KEY" if c["name"] == pk else "")
                         for c in sch["columns"])
        con.execute(f"CREATE TABLE IF NOT EXISTS records ({defs})")
        for c in sch["columns"]:
            if c.get("unique") and c["name"] != pk:
                con.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{c['name']} ON records({c['name']})")
        ph = ",".join("?" * len(names))
        con.execute("BEGIN")
        con.executemany(f"INSERT OR REPLACE INTO records ({','.join(names)}) VALUES ({ph})",
                        [tuple(r[n] for n in names) for r in parsed])
        con.commit()
    except sqlite3.Error as e:
        con.rollback(); con.close(); bail("db_error", str(e))
    con.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--db")
    ap.add_argument("--encoding", default="utf-8", choices=["utf-8", "utf-8-sig"])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", dest="dry_run", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    sch, names, pk = load_schema(a.schema)
    recs = open_csv(a.input, a.encoding, names)
    errs, parsed = validate(sch, names, recs)
    if a.apply:
        if not a.db:
            bail("usage", "--apply needs --db")
        errs = sorted(errs + existing_conflicts(a.db, sch, pk, parsed), key=lambda e: (e["record"], e["field"]))
    for e in errs:
        out(e)
    counts = {}
    for e in errs:
        counts[e["code"]] = counts.get(e["code"], 0) + 1
    out({"summary": {"ok": not errs, "records": len(recs), "errors": len(errs), "by_code": counts}})
    if errs:
        return 1
    if a.apply:
        persist(a.db, sch, names, pk, parsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
