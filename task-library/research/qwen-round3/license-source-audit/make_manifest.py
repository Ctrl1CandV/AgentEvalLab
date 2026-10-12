#!/usr/bin/env python3
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  
EXCLUDE_DIRS = {"__pycache__", "logs"}
SELF = "manifest.sha256.json"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    entries = {}
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fn in files:
            if fn == SELF or fn.endswith(".pyc"):
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, ROOT).replace("\\", "/")
            entries[rel] = {"sha256": sha256(fp), "bytes": os.path.getsize(fp)}
    out = {"generated_by": "license-source-audit/make_manifest.py", "root": "task-library/research/qwen-round3",
           "excluded": sorted(EXCLUDE_DIRS) + [SELF, "*.pyc"], "file_count": len(entries), "files": entries}
    with open(os.path.join(ROOT, SELF), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"manifest written: {SELF}  files={len(entries)}")


if __name__ == "__main__":
    main()
