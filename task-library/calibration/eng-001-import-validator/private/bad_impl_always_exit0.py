#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_impl_a  # noqa: E402

try:
    ref_impl_a.main()
except SystemExit:
    pass
sys.exit(0)  
