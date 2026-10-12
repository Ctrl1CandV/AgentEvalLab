#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_impl as R  # noqa: E402


def needs_processing(rel, out_path, input_sha, journal):
    e = journal.get(rel)
    if not e:
        return True
    if not os.path.isfile(out_path):
        return True
    if R.sha256_file(out_path) != e.get("output_sha256"):
        return True
    return False  


R.needs_processing = needs_processing
sys.exit(R.main())
