#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ref_impl_a as R  # noqa: E402

_orig = R.write_db


def wd(db, schema, names, pk, recs):
    for r in recs:
        if r.get("email"):
            r["email"] = r["email"] + ".bad"  
    return _orig(db, schema, names, pk, recs)


R.write_db = wd
sys.exit(R.main())
