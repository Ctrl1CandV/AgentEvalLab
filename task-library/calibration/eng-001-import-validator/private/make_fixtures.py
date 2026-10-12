#!/usr/bin/env python3
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PUB = os.path.join(PKG, "public")
FIX = os.path.join(HERE, "fixtures")
HEADER = "id,email,age,signup_date,active,score\n"


def w(rel, text, encoding="utf-8"):
    path = os.path.join(PKG, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)


def main():
    clean = HEADER + (
        "1,alice@example.com,30,2024-01-15,true,9.5\n"
        "2,bob@example.com,25,2024-02-20,false,7.0\n"
        "3,carol@example.com,,2024-03-10,true,\n"
    )
    w("public/data_clean.csv", clean)
    w("private/fixtures/clean.csv", clean)
    
    w("public/expected_dry_run_clean.jsonl",
      json.dumps({"summary": {"ok": True, "records": 3, "errors": 0, "by_code": {}}}, ensure_ascii=False) + "\n")

    
    w("private/fixtures/embedded.csv", HEADER + (
        '1,"Doe, John <john@example.com>",40,2024-01-01,true,8.0\n'
        '2,"multi\nline <x@example.com>",,,false,\n'
    ))
    
    w("private/fixtures/multiline_pos.csv", HEADER + (
        '1,"multi\nline@example.com",badage,2024-01-01,true,8.0\n'
    ))
    w("private/fixtures/type_errors.csv", HEADER + (
        "1,a@example.com,notanint,2024-01-01,maybe,8.0\n"
        "2,b@example.com,30,2024-13-45,true,abc\n"
    ))
    w("private/fixtures/missing_required.csv", HEADER + (
        "1,,30,2024-01-01,true,8.0\n"
        ",has@example.com,30,2024-01-01,true,8.0\n"
    ))
    long_email = "a" * 250 + "@example.com"  # 262 > 254
    w("private/fixtures/constraints.csv", HEADER + (
        "1,a@example.com,200,2024-01-01,true,8.0\n"
        "2,b@example.com,-5,2024-01-01,true,8.0\n"
        f"3,{long_email},30,2024-01-01,true,8.0\n"
    ))
    w("private/fixtures/unique_dup.csv", HEADER + (
        "1,a@example.com,30,2024-01-01,true,8.0\n"
        "1,b@example.com,25,2024-01-02,true,7.0\n"
        "2,a@example.com,40,2024-01-03,true,6.0\n"
    ))
    w("private/fixtures/nan_inf.csv", HEADER + (
        "1,a@example.com,30,2024-01-01,true,nan\n"
        "2,b@example.com,30,2024-01-01,true,inf\n"
        "3,c@example.com,30,2024-01-01,true,-Infinity\n"
    ))
    w("private/fixtures/bom.csv", clean, encoding="utf-8-sig")  # BOM + clean
    w("private/fixtures/empty.csv", "")
    w("private/fixtures/header_only.csv", HEADER)
    w("private/fixtures/extra_column.csv", "id,email,age,signup_date,active,score,notes\n"
      "1,a@example.com,30,2024-01-01,true,8.0,x\n")
    w("private/fixtures/missing_column.csv", "id,email,age,signup_date,active\n"
      "1,a@example.com,30,2024-01-01,true\n")
    w("private/fixtures/duplicate_header.csv", "id,id,age,signup_date,active,score\n"
      "1,2,30,2024-01-01,true,8.0\n")
    w("private/fixtures/malformed.csv", HEADER + '1,"unterminated,2,3\n')
    w("private/fixtures/mixed_valid_invalid.csv", HEADER + (
        "1,a@example.com,30,2024-01-01,true,8.0\n"
        "2,b@example.com,25,2024-01-02,true,7.0\n"
        "3,c@example.com,notanint,2024-01-03,true,6.0\n"
    ))
    
    w("private/fixtures/bad_schema_unknown_type.json", json.dumps({
        "primary_key": "id",
        "columns": [{"name": "id", "type": "integer", "required": True}]}))
    w("private/fixtures/bad_schema_pk_missing.json", json.dumps({
        "primary_key": "nope",
        "columns": [{"name": "id", "type": "int", "required": True}]}))
    w("private/fixtures/bad_schema_invalid.json", "{ this is not json ")

    print("fixtures written to:", os.path.relpath(FIX, PKG), "and public/")
    for name in sorted(os.listdir(FIX)):
        print("  -", name)


if __name__ == "__main__":
    main()
