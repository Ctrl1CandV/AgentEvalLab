#!/usr/bin/env python3
"""Hidden checks of the codec item, run inside the sandbox from a directory holding a copy of the delivered workspace's
public/ directory, with lgz.py and cases.py beside this script. Prints one JSON object {check: true/false}: each hidden
group passes when `python3 decode.py IN OUT` restores every file of the group exactly; `restore` checks restored/.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cases  # noqa: E402
import lgz  # noqa: E402

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
HIDDEN = {group: files for group, files in cases.hidden().items()}
ARCHIVE = cases.archive()
# The expected files now live only in this process; the candidate's decoder runs after their sources are gone.
for name in ("cases.py", "lgz.py"):
    if os.path.exists(os.path.join(HERE, name)):
        os.remove(os.path.join(HERE, name))
shutil.rmtree(os.path.join(HERE, "__pycache__"), ignore_errors=True)


def decodes(original):
    with tempfile.TemporaryDirectory(dir=ROOT) as scratch:
        source, target = os.path.join(scratch, "in.lgz"), os.path.join(scratch, "out.log")
        with open(source, "wb") as handle:
            handle.write(lgz.encode(original))
        try:
            run = subprocess.run([sys.executable, "decode.py", source, target], cwd=ROOT, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            return False
        if run.returncode != 0 or not os.path.isfile(target):
            return False
        with open(target, "rb") as handle:
            return handle.read() == original


def restored(name, original):
    path = os.path.join(ROOT, "restored", name)
    if not os.path.isfile(path):
        return False
    with open(path, "rb") as handle:
        return handle.read() == original


def main():
    verdicts = {}
    has_decoder = os.path.isfile(os.path.join(ROOT, "decode.py"))
    for group, files in HIDDEN.items():
        verdicts[group] = has_decoder and all(decodes(original) for original in files.values())
    verdicts["restore"] = all(restored(name, original) for name, original in ARCHIVE.items())
    print(json.dumps(verdicts, sort_keys=True))


if __name__ == "__main__":
    main()
