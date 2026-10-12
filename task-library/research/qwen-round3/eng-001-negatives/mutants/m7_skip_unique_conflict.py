#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ref_impl_a as R  # noqa: E402

R.existing_unique_conflicts = lambda *a, **k: []  
sys.exit(R.main())
