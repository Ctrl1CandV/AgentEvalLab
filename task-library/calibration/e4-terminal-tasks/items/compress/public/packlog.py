#!/usr/bin/env python3
"""packlog: compress and restore edge request logs for the archive.

Usage:
    python3 packlog.py compress IN OUT
    python3 packlog.py decompress IN OUT
"""
import gzip
import sys


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("compress", "decompress"):
        sys.exit(__doc__)
    mode, source, target = sys.argv[1:]
    with open(source, "rb") as handle:
        data = handle.read()
    result = gzip.compress(data, compresslevel=6, mtime=0) if mode == "compress" else gzip.decompress(data)
    with open(target, "wb") as handle:
        handle.write(result)


if __name__ == "__main__":
    main()
