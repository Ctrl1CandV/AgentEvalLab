#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = shutil.which("python") or sys.executable


class _Tee:
    def __init__(self, path, orig):
        self.fh = open(path, "w", encoding="utf-8")
        self.orig = orig

    def write(self, s):
        self.fh.write(s)
        try:
            self.orig.write(s)
        except Exception:
            self.orig.write(s.encode("ascii", "replace").decode("ascii"))
        return len(s)

    def flush(self):
        self.fh.flush()
        try:
            self.orig.flush()
        except Exception:
            pass
SCHEMA_PATH = os.path.join(HERE, "schema.json")
COLS = ["id", "email", "age", "signup_date", "active", "score"]
DDL = ("CREATE TABLE records (id INTEGER PRIMARY KEY, email TEXT UNIQUE, "
       "age INTEGER, signup_date TEXT, active INTEGER, score REAL)")


def run_impl(impl, args):
    cmd = [PY, impl, "--schema", args.get("schema", SCHEMA_PATH), "--input", args["input"]]
    if args.get("db"):
        cmd += ["--db", args["db"]]
    cmd += ["--dry-run" if args["mode"] == "dry-run" else "--apply"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    errors, summary, top = [], None, None
    for ln in p.stdout.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if "record" in o:
            errors.append(o)
        elif "summary" in o:
            summary = o["summary"]
        elif "error" in o:
            top = o["error"]
    return p.returncode, errors, summary, top, p.stderr


def write_csv(tmp, name, rows):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS)
        for r in rows:
            w.writerow(r)
    return path


def prepopulate(path, rows):
    con = sqlite3.connect(path)
    con.execute(DDL)
    con.executemany("INSERT INTO records (id,email,age,signup_date,active,score) VALUES (?,?,?,?,?,?)",
                    [(r["id"], r["email"], r["age"], r["signup_date"], r["active"], r["score"]) for r in rows])
    con.commit()
    con.close()


def read_rows(path):
    if not os.path.isfile(path):
        return None
    con = sqlite3.connect(path)
    try:
        cur = con.execute("SELECT id,email,age,signup_date,active,score FROM records ORDER BY id")
        return [dict(zip(COLS, r)) for r in cur.fetchall()]
    finally:
        con.close()


def db_hash(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.isfile(path) else None


def err_triples(errors):
    return [(e["record"], e["field"], e["code"]) for e in errors]


# Internal calibration detail.
def s1_full_row_content(impl, tmp):
    csvp = write_csv(tmp, "s1.csv", [
        ["1", "alice@x.com", "30", "2024-01-15", "true", "9.5"],
        ["2", "bob@x.com", "", "", "false", ""],
    ])
    db = os.path.join(tmp, "s1.sqlite")
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "db": db, "mode": "apply"})
    exp = [
        {"id": 1, "email": "alice@x.com", "age": 30, "signup_date": "2024-01-15", "active": 1, "score": 9.5},
        {"id": 2, "email": "bob@x.com", "age": None, "signup_date": None, "active": 0, "score": None},
    ]
    got = read_rows(db)
    if rc != 0:
        return False, f"exit {rc}!=0 ({se.strip()[:80]})"
    if got != exp:
        return False, f"database rows differ from the expected upsert rows:\n     got={got}\n     exp={exp}"
    return True, "case passed"


def s2_existing_pk_update(impl, tmp):
    db = os.path.join(tmp, "s2.sqlite")
    prepopulate(db, [{"id": 1, "email": "old@x.com", "age": 20, "signup_date": "2020-01-01", "active": 1, "score": 1.0}])
    csvp = write_csv(tmp, "s2.csv", [
        ["1", "new@x.com", "31", "2024-02-02", "false", "2.5"],
        ["3", "c@x.com", "40", "2024-03-03", "true", "3.0"],
    ])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "db": db, "mode": "apply"})
    exp = [
        {"id": 1, "email": "new@x.com", "age": 31, "signup_date": "2024-02-02", "active": 0, "score": 2.5},
        {"id": 3, "email": "c@x.com", "age": 40, "signup_date": "2024-03-03", "active": 1, "score": 3.0},
    ]
    got = read_rows(db)
    if rc != 0:
        return False, f"exit {rc}!=0 ({se.strip()[:80]})"
    if got != exp:
        return False, f"database rows differ from the expected upsert rows:\n     got={got}\n     exp={exp}"
    return True, "case passed"


def s3_nonpk_unique_conflict(impl, tmp):
    db = os.path.join(tmp, "s3.sqlite")
    prepopulate(db, [{"id": 1, "email": "dup@x.com", "age": 20, "signup_date": "2020-01-01", "active": 1, "score": 1.0}])
    before = db_hash(db)
    csvp = write_csv(tmp, "s3.csv", [["2", "dup@x.com", "30", "2024-01-01", "true", "5.0"]])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "db": db, "mode": "apply"})
    if rc != 1:
        return False, f"exit {rc}!=1"
    if (0, "email", "unique_violation") not in err_triples(errs):
        return False, f"missing unique-constraint error: {err_triples(errs)}"
    if db_hash(db) != before:
        return False, "database changed after a unique-constraint conflict"
    return True, "case passed"


def s4_failure_no_db_change(impl, tmp):
    db = os.path.join(tmp, "s4.sqlite")
    prepopulate(db, [{"id": 1, "email": "keep@x.com", "age": 20, "signup_date": "2020-01-01", "active": 1, "score": 1.0}])
    before = db_hash(db)
    csvp = write_csv(tmp, "s4.csv", [
        ["1", "keep@x.com", "21", "2020-01-01", "true", "1.0"],
        ["2", "b@x.com", "bad", "", "", ""],
    ])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "db": db, "mode": "apply"})
    if rc != 1:
        return False, f"exit {rc}!=1"
    if db_hash(db) != before:
        return False, "database changed after a unique-constraint conflict"
    return True, "case passed"


def s5_dryrun_no_db_change(impl, tmp):
    db = os.path.join(tmp, "s5.sqlite")
    prepopulate(db, [{"id": 1, "email": "keep@x.com", "age": 20, "signup_date": "2020-01-01", "active": 1, "score": 1.0}])
    before = db_hash(db)
    csvp = write_csv(tmp, "s5.csv", [["1", "new@x.com", "31", "2024-02-02", "false", "2.5"],
                                     ["2", "c@x.com", "40", "2024-03-03", "true", "3.0"]])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "db": db, "mode": "dry-run"})
    if rc != 0:
        return False, f"exit {rc}!=0"
    if db_hash(db) != before:
        return False, "database changed after validation failure"
    db2 = os.path.join(tmp, "s5_nonexistent.sqlite")
    rc2, *_ = run_impl(impl, {"input": csvp, "db": db2, "mode": "dry-run"})
    if os.path.exists(db2):
        return False, "dry-run created the database file"
    return True, "case passed"


def s6_all_nonpk_wrong(impl, tmp):
    long_email = "a" * 250 + "@x.com"  # 262 > 254
    csvp = write_csv(tmp, "s6.csv", [["1", long_email, "abc", "2024-13-45", "maybe", "nan"]])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "mode": "dry-run"})
    want = {(0, "email", "constraint"), (0, "age", "type_mismatch"), (0, "signup_date", "type_mismatch"),
            (0, "active", "type_mismatch"), (0, "score", "type_mismatch")}
    if rc != 1:
        return False, f"exit {rc}!=1"
    if set(err_triples(errs)) != want:
        return False, f"validation errors differ: got={set(err_triples(errs))} want={want}"
    for e in errs:
        if e.get("line") != 2:
            return False, f"error should report physical line 2; got {e.get('line')}"
    rawmap = {"email": long_email, "age": "abc", "signup_date": "2024-13-45", "active": "maybe", "score": "nan"}
    for e in errs:
        if e.get("value") != rawmap[e["field"]]:
            return False, f"{e['field']} reported value does not preserve the original cell text: {e.get('value')!r} != {rawmap[e['field']]!r}"
    return True, "case passed"


def s7_value_is_raw(impl, tmp):
    csvp = write_csv(tmp, "s7.csv", [["1", "a@x.com", " 12x ", "2024-01-01", "true", "1.0"]])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "mode": "dry-run"})
    age = [e for e in errs if e["field"] == "age"]
    if rc != 1 or not age:
        return False, f"exit {rc} did not report the malformed age value"
    if age[0].get("value") != " 12x ":
        return False, f"error value should preserve the original cell text ' 12x '; got {age[0].get('value')!r}"
    return True, "case passed"


def s8_error_order(impl, tmp):
    csvp = write_csv(tmp, "s8.csv", [
        ["1", "a@x.com", "bad", "", "", ""],   # (0,'age',type_mismatch)
        ["2", "", "30", "", "", ""],           # (1,'email',missing_required)
    ])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "mode": "dry-run"})
    order = [(e["record"], e["field"]) for e in errs]  # Internal calibration detail.
    if rc != 1:
        return False, f"exit {rc}!=1"
    if order != sorted(order):
        return False, f"error order is not sorted by (record, field): {order}"
    if order != [(0, "age"), (1, "email")]:
        return False, f"unexpected error order: {order}"
    return True, "case passed"


def s9_summary(impl, tmp):
    long_email = "a" * 250 + "@x.com"
    csvp = write_csv(tmp, "s9.csv", [["1", long_email, "abc", "2024-13-45", "maybe", "nan"]])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "mode": "dry-run"})
    exp = {"ok": False, "records": 1, "errors": 5, "by_code": {"constraint": 1, "type_mismatch": 4}}
    if summ != exp:
        return False, f"summary mismatch: got={summ} exp={exp}"
    return True, "case passed"


def s10_fatal_no_summary(impl, tmp):
    badsch = os.path.join(tmp, "bad.json")
    with open(badsch, "w", encoding="utf-8") as f:
        json.dump({"primary_key": "id", "columns": [{"name": "id", "type": "integer"}]}, f)
    csvp = write_csv(tmp, "s10.csv", [["1", "a@x.com", "30", "2024-01-01", "true", "1.0"]])
    rc, errs, summ, top, se = run_impl(impl, {"input": csvp, "schema": badsch, "mode": "dry-run"})
    if rc != 2:
        return False, f"exit {rc}!=2"
    if not top or top.get("code") != "schema_error":
        return False, f"fatal error is not schema_error: {top}"
    if summ is not None:
        return False, "fatal schema error unexpectedly included a row summary"
    return True, "case passed"


SCENARIOS = [
    ("S1_full_row_content", s1_full_row_content, None),
    ("S2_existing_pk_update", s2_existing_pk_update, None),
    ("S3_nonpk_unique_conflict", s3_nonpk_unique_conflict, None),
    ("S4_failure_no_db_change", s4_failure_no_db_change, None),
    ("S5_dryrun_no_db_change", s5_dryrun_no_db_change, None),
    ("S6_all_nonpk_wrong", s6_all_nonpk_wrong, None),
    ("S7_value_is_raw", s7_value_is_raw, None),
    ("S8_error_order", s8_error_order, None),
    ("S9_summary", s9_summary, None),
    ("S10_fatal_no_summary", s10_fatal_no_summary, None),
]


def run_all(impl):
    res = {}
    for name, fn, _ in SCENARIOS:
        tmp = tempfile.mkdtemp(prefix="qwen_eng001_")
        try:
            res[name] = fn(impl, tmp)
        except Exception as e:
            res[name] = (False, f"{type(e).__name__}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return res


# Internal calibration detail.
MUTANT_TARGET = {
    "m1_wrong_email_db.py": "S1_full_row_content",
    "m2_insert_no_upsert.py": "S2_existing_pk_update",
    "m3_write_on_failure.py": "S4_failure_no_db_change",
    "m4_dryrun_touches_db.py": "S5_dryrun_no_db_change",
    "m5_unsorted_errors.py": "S8_error_order",
    "m6_wrong_value.py": "S7_value_is_raw",
    "m7_skip_unique_conflict.py": "S3_nonpk_unique_conflict",
}


def self_calibrate():
    logpath = os.path.join(HERE, "logs", "self-calibration.log")
    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    _orig = sys.stdout
    sys.stdout = _Tee(logpath, _orig)
    allok = True
    print("Engineering negative-case self-calibration")
    ref = os.path.join(HERE, "ref_impl_a.py")
    r = run_all(ref)
    npass = sum(1 for ok, _ in r.values() if ok)
    print(f"-- reference implementation: {npass}/{len(r)} cases passed")
    for k, (ok, d) in r.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {k}: {d}")
    ref_all = all(ok for ok, _ in r.values())
    allok &= ref_all

    for m, target in MUTANT_TARGET.items():
        mp = os.path.join(HERE, "mutants", m)
        res = run_all(mp)
        n = sum(1 for ok, _ in res.values() if ok)
        target_failed = not res[target][0]
        print(f"-- mutant {m}: {n}/{len(res)} cases passed; target={target}; {'REJECTED' if target_failed else 'NOT REJECTED'}; failed_cases={[k for k,(ok,_) in res.items() if not ok]}")
        allok &= target_failed

    print("RESULT:", "PASS" if allok else "FAIL")
    sys.stdout = _orig
    sys.stdout.flush()
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-calibrate", action="store_true")
    ap.add_argument("--impl")
    a = ap.parse_args()
    if a.self_calibrate:
        sys.exit(self_calibrate())
    if a.impl:
        res = run_all(a.impl)
        for k, (ok, d) in res.items():
            print(f"[{'PASS' if ok else 'FAIL'}] {k}: {d}")
        sys.exit(0 if all(ok for ok, _ in res.values()) else 1)
    ap.error("Provide --impl or --self-calibrate.")


if __name__ == "__main__":
    main()
