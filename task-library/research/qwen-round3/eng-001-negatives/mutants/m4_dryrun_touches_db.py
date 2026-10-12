#!/usr/bin/env python3
import os
import sqlite3
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ref_impl_a as R  # noqa: E402

av = sys.argv
if "--db" in av:  
    db = av[av.index("--db") + 1]
    d = os.path.dirname(db)
    if d:
        os.makedirs(d, exist_ok=True)
    sqlite3.connect(db).close()
sys.exit(R.main())
