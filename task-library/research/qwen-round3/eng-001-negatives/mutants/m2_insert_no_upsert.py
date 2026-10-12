#!/usr/bin/env python3
import os
import sqlite3
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ref_impl_a as R  # noqa: E402


def wd(db, schema, names, pk, recs):
    con = sqlite3.connect(db)
    cur = con.cursor()
    coldefs = []
    for c in schema["columns"]:
        d = f'{c["name"]} {R.TYPE_MAP[c["type"]]}'
        if c["name"] == pk:
            d += " PRIMARY KEY"
        if c.get("unique") and c["name"] != pk:
            d += " UNIQUE"
        coldefs.append(d)
    cur.execute(f'CREATE TABLE IF NOT EXISTS records ({", ".join(coldefs)})')
    ph = ",".join("?" * len(names))
    
    cur.executemany(f'INSERT INTO records ({",".join(names)}) VALUES ({ph})',
                    [tuple(r[n] for n in names) for r in recs])
    con.commit()
    con.close()


R.write_db = wd
sys.exit(R.main())
