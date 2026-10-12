#!/usr/bin/env python3
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if "--db" in sys.argv:  
    db = sys.argv[sys.argv.index("--db") + 1]
    d = os.path.dirname(db)
    if d:
        os.makedirs(d, exist_ok=True)
    sqlite3.connect(db).close()

import ref_impl_a  # noqa: E402

try:
    sys.exit(ref_impl_a.main())
except SystemExit:
    raise
