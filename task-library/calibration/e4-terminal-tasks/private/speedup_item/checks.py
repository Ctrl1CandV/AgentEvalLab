#!/usr/bin/env python3
"""Hidden checks of the speedup item, run inside the sandbox from a directory holding a copy of the delivered workspace's
public/ directory, with data.py, naive.py and reference.py beside this script. Prints {check: true/false}.

- `small`, `large`: analyze.py prints exactly the original's output on a normal day and on a day of 200,000 events,
  both of well-formed rows (timestamps in several offsets).
- `quirks`: the same on a day full of malformed and unusual rows.
- `speed-8`, `speed-3`, `speed-1.5`, `speed-1.1`, `speed-0.75`: on the large day, analyze.py takes at most that many times
  as long as the reference (best of three runs each, interleaved, on one CPU core). They need `small` and `large` right.
- Guards: `small`, `large` and `quirks` count only when `speed-8` passes, so the untouched original (about 70 times the
  reference's time) earns nothing.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data  # noqa: E402

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
SOURCES = {}
for name in ("naive.py", "reference.py", "data.py"):
    with open(os.path.join(HERE, name), encoding="utf-8") as handle:
        SOURCES[name] = handle.read()
    os.remove(os.path.join(HERE, name))
# One core for everything this script starts; checks running side by side get different cores.
CPUS = sorted(os.sched_getaffinity(0))
os.sched_setaffinity(0, {CPUS[os.getpid() % len(CPUS)]})
CANDIDATE_TIMEOUT = 60


def run(program, dataset, source=None):
    """(stdout or None, seconds). A program given as source is written just for the run and removed after it."""
    scratch = None
    if source is not None:
        scratch = tempfile.mkdtemp(dir=ROOT)
        program = os.path.join(scratch, program)
        with open(program, "w", encoding="utf-8") as handle:
            handle.write(source)
    try:
        started = time.perf_counter()
        result = subprocess.run([sys.executable, program, dataset], cwd=ROOT, capture_output=True, timeout=CANDIDATE_TIMEOUT)
        seconds = time.perf_counter() - started
        return (result.stdout if result.returncode == 0 else None), seconds
    except subprocess.TimeoutExpired:
        return None, float("inf")
    finally:
        if scratch:
            for name in os.listdir(scratch):
                os.remove(os.path.join(scratch, name))
            os.rmdir(scratch)


def main():
    candidate = os.path.join(ROOT, "analyze.py")
    with tempfile.TemporaryDirectory(dir=ROOT) as days:
        paths = {}
        # Malformed and unusual rows appear only on the quirks day, so mishandling one costs that check, not the speed checks.
        for name, seed, rows, quirks in (("small", "speedup-hidden-small", 5_000, 0.0), ("quirks", "speedup-hidden-quirks", 4_000, 0.5),
                                         ("large", "speedup-hidden-large", 200_000, 0.0)):
            paths[name] = os.path.join(days, f"{name}.csv")
            with open(paths[name], "w", encoding="utf-8", newline="") as handle:
                handle.write(data.events(seed, rows, quirks))
        right = {}
        for name in ("small", "quirks"):
            expected, _ = run("naive.py", paths[name], SOURCES["naive.py"])
            actual, _ = run(candidate, paths[name])
            right[name] = actual is not None and actual == expected
        expected, reference_time = run("reference.py", paths["large"], SOURCES["reference.py"])
        actual, candidate_time = run(candidate, paths["large"])
        right["large"] = actual is not None and actual == expected
        ratio = float("inf")
        if right["small"] and right["large"] and candidate_time <= 8 * reference_time * 1.5:
            for _ in range(2):
                reference_time = min(reference_time, run("reference.py", paths["large"], SOURCES["reference.py"])[1])
                output, seconds = run(candidate, paths["large"])
                if output == expected:
                    candidate_time = min(candidate_time, seconds)
            ratio = candidate_time / reference_time
    gate = right["small"] and right["large"]
    verdicts = {f"speed-{label}": gate and ratio <= factor for label, factor in (("8", 8), ("3", 3), ("1.5", 1.5), ("1.1", 1.1), ("0.75", 0.75))}
    fast = verdicts["speed-8"]
    verdicts.update({"small": right["small"] and fast, "large": right["large"] and fast, "quirks": right["quirks"] and fast})
    print(json.dumps({**verdicts, "ratio": None if ratio == float("inf") else round(ratio, 3)}, sort_keys=True))


if __name__ == "__main__":
    main()
