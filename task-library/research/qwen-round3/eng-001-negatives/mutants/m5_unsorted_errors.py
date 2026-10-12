#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ref_impl_a as R  # noqa: E402

_o = R.validate


def v(*a, **k):
    e, p = _o(*a, **k)
    return list(reversed(e)), p  


R.validate = v
sys.exit(R.main())
