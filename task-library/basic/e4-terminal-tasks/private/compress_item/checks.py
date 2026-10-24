#!/usr/bin/env python3
"""Hidden checks of the compress item, run inside the sandbox from a directory holding a copy of the delivered workspace's
public/ directory, with logdata.py and packref.py beside this script. Prints {check: true/false, "progress": p}.

- `roundtrip`: two normal logs (days a and b) come back byte for byte, each run within the time limit (60 seconds, or
  40 times the reference's time on day a when the machine is busy).
- `roundtrip-quirks`: a damaged log, an empty file, a log whose last line has no newline and random bytes come back
  byte for byte, each run within the time limit.
- `ratio-50`, `ratio-80`, `ratio-90`, `ratio-97`: the total compressed size of days a and b, on the scale from LZMA at
  preset 9 with PRESET_EXTREME (0) to the reference compressor written for the format (1), reaches that share of the way.
  They need `roundtrip`.
- Guards: `roundtrip` and `roundtrip-quirks` count only when `ratio-50` passes, so gzip or LZMA alone earns nothing.

Trust boundary: the generator and the reference are imported, then their files are deleted before any candidate runs.
Compression and decompression run in separate fresh copies of the delivered workspace, made from a copy taken before any
run whose hashes are checked; decompression gets only the compressed file, and whatever a run leaves in /tmp or the
scratch area is removed, so nothing but the compressed file passes between them.
"""
import json
import lzma
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logdata  # noqa: E402
import packref  # noqa: E402

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
for name in ("logdata.py", "packref.py", "baseline.py"):
    if os.path.exists(os.path.join(HERE, name)):
        os.remove(os.path.join(HERE, name))
shutil.rmtree(os.path.join(HERE, "__pycache__"), ignore_errors=True)
CPUS = sorted(os.sched_getaffinity(0))
os.sched_setaffinity(0, {CPUS[os.getpid() % len(CPUS)]})
# The stated limit is 60 seconds. The reference compresses day a in about 1.2 seconds on an idle machine, so on a busy
# one the limit grows with the reference's measured time, and a run is never failed for the machine's load.
TIME_LIMIT = 60
LOAD_FACTOR = 40
THRESHOLDS = (("50", 0.5), ("80", 0.8), ("90", 0.9), ("97", 0.97))
SCRATCH = os.path.join(ROOT, ".compress-check")
PRISTINE = os.path.join(SCRATCH, "pristine")
OWN = {"hidden_checks.py", ".compress-check"}


def digest_tree(directory):
    import hashlib
    entries = []
    for current, folders, files in os.walk(directory):
        folders.sort()
        for name in sorted(files):
            path = os.path.join(current, name)
            with open(path, "rb") as handle:
                entries.append((os.path.relpath(path, directory), hashlib.sha256(handle.read()).hexdigest()))
    return entries


def copy_tree(source, target):
    shutil.copytree(source, target, symlinks=True)


def prepare():
    """The delivered workspace as it was, copied once; every run starts from a copy of this."""
    os.makedirs(PRISTINE)
    for name in os.listdir(ROOT):
        if name in OWN:
            continue
        path = os.path.join(ROOT, name)
        if os.path.isdir(path) and not os.path.islink(path):
            copy_tree(path, os.path.join(PRISTINE, name))
        else:
            shutil.copy2(path, os.path.join(PRISTINE, name), follow_symlinks=False)
    return digest_tree(PRISTINE)


def tmp_entries():
    tmp = tempfile.gettempdir()
    try:
        return {os.path.join(tmp, name) for name in os.listdir(tmp)}
    except OSError:
        return set()


def remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            os.remove(path)
        except OSError:
            pass


def run(mode, directory, source, target):
    before = tmp_entries()
    started = time.perf_counter()
    try:
        result = subprocess.run([sys.executable, "packlog.py", mode, source, target], cwd=directory, capture_output=True, timeout=TIME_LIMIT)
        ok = result.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    for path in tmp_entries() - before:
        remove(path)
    return ok and time.perf_counter() - started <= TIME_LIMIT


def roundtrip(raw, pristine):
    """(restored exactly, compressed size or None). Only the compressed file passes from the compressing run to the other."""
    compressor = os.path.join(SCRATCH, "compress")
    decompressor = os.path.join(SCRATCH, "decompress")
    transfer = os.path.join(SCRATCH, "transfer.plg")
    try:
        copy_tree(PRISTINE, compressor)
        with open(os.path.join(compressor, "input.log"), "wb") as handle:
            handle.write(raw)
        ok = run("compress", compressor, "input.log", "input.plg")
        packed = os.path.join(compressor, "input.plg")
        if not ok or not os.path.isfile(packed):
            return False, None
        size = os.path.getsize(packed)
        shutil.move(packed, transfer)
        for name in os.listdir(SCRATCH):
            if name not in ("pristine", "transfer.plg"):
                remove(os.path.join(SCRATCH, name))
        if digest_tree(PRISTINE) != pristine:
            return False, size
        copy_tree(PRISTINE, decompressor)
        shutil.move(transfer, os.path.join(decompressor, "input.plg"))
        ok = run("decompress", decompressor, "input.plg", "restored.log")
        restored = os.path.join(decompressor, "restored.log")
        if not ok or not os.path.isfile(restored):
            return False, size
        with open(restored, "rb") as handle:
            return handle.read() == raw, size
    finally:
        for path in (compressor, decompressor, transfer):
            remove(path)


def main():
    if not os.path.isfile(os.path.join(ROOT, "packlog.py")):
        print(json.dumps({check: False for check in ("roundtrip", "roundtrip-quirks", *(f"ratio-{label}" for label, _ in THRESHOLDS))}))
        return
    days = [logdata.events(*logdata.HIDDEN[name]) for name in ("day-a", "day-b")]
    rng = random.Random("compress-hidden-bytes")
    odd = [logdata.events(*logdata.HIDDEN["quirks"]), b"", days[1][: len(days[1]) // 7].rstrip(b"\n"),
           bytes(rng.randrange(256) for _ in range(65_536))]
    global TIME_LIMIT
    lower = sum(len(lzma.compress(day, preset=9 | lzma.PRESET_EXTREME)) for day in days)
    started = time.perf_counter()
    upper = len(packref.compress(days[0]))
    TIME_LIMIT = max(TIME_LIMIT, LOAD_FACTOR * (time.perf_counter() - started))
    upper += len(packref.compress(days[1]))
    pristine = prepare()
    results = []
    for day in days:
        results.append(roundtrip(day, pristine))
        if not results[-1][0]:
            break
    normal = len(results) == len(days) and all(exact for exact, _ in results)
    progress = (lower - sum(size for _, size in results)) / (lower - upper) if normal else None
    # The damaged inputs only count once ratio-50 passes; they are not run otherwise.
    quirks = progress is not None and progress >= THRESHOLDS[0][1] and all(roundtrip(raw, pristine)[0] for raw in odd)
    verdicts = {f"ratio-{label}": progress is not None and progress >= share for label, share in THRESHOLDS}
    verdicts["roundtrip"] = normal and verdicts["ratio-50"]
    verdicts["roundtrip-quirks"] = quirks and verdicts["ratio-50"]
    print(json.dumps({**verdicts, "progress": None if progress is None else round(progress, 4)}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)
