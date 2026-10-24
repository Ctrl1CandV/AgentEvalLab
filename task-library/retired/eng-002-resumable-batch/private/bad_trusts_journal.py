#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_impl as R  # noqa: E402


def needs_processing(rel, out_path, input_sha, journal):
    e = journal.get(rel)
    
    return not (e and e.get("input_sha256") == input_sha)


R.needs_processing = needs_processing
sys.exit(R.main())
