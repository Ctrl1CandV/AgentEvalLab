#!/usr/bin/env python3
"""Hidden checks of the pipeline item, run inside the sandbox with the delivered workspace's public/ directory as the
argument. Each check copies the delivered pipeline, replaces raw/ with hidden data, runs make and compares report.csv
with a report written by hand from README.md. Prints one JSON object {check: true/false}.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
HEADER = "month,region,revenue\n"


class Run:
    def __init__(self, files):
        self.directory = tempfile.mkdtemp(prefix="pipeline-check-", dir=ROOT)
        for name in os.listdir(ROOT):
            if name in ("raw", "build", "report.csv") or name.startswith("pipeline-check-"):
                continue
            source = os.path.join(ROOT, name)
            (shutil.copytree if os.path.isdir(source) else shutil.copy)(source, os.path.join(self.directory, name))
        os.makedirs(os.path.join(self.directory, "raw"))
        for name, data in files.items():
            self.write(name, data)

    def write(self, name, data):
        with open(os.path.join(self.directory, "raw", name), "wb") as handle:
            handle.write(data.encode("utf-8"))

    def make(self, *targets):
        try:
            return subprocess.run(["make", *targets], cwd=self.directory, capture_output=True, timeout=120).returncode
        except subprocess.TimeoutExpired:
            return 124

    def report(self):
        if self.make() != 0:
            return None
        try:
            with open(os.path.join(self.directory, "report.csv"), encoding="utf-8") as handle:
                return handle.read().replace("\r\n", "\n")
        except FileNotFoundError:
            return None


STORES = "store_id,name,region\n1,Harbour Street,North\n2,Old Mill,North\n7,Station Square,South\n12,Riverside,South\n31,Canal Gate,EU\n"


def check(function):
    try:
        return bool(function())
    except Exception:
        return False


def line_ends():
    run = Run({"stores.csv": STORES,
               "sales-a.csv": "date,amount,store\r\n2026-10-01,10.00,1\r\n2026-10-02,20.00,7",
               "sales-b.csv": "date,amount,store\n2026-10-03,5.50,2\n2026-10-04,4.50,12",
               "sales-c.csv": "date,amount,store\n2026-11-01,1.00,1"})
    return run.report() == HEADER + "2026-10,North,15.50\n2026-10,South,24.50\n2026-11,North,1.00\n"


def store_ids():
    run = Run({"stores.csv": "store_id,name,region\n001,Harbour Street,North\n0007,Station Square,South\n12,Riverside,South\n",
               "sales-a.csv": "date,amount,store\n2026-10-01,10.00,1\n2026-10-02,20.00,07\n2026-10-03,3.00,012\n2026-10-04,1.25,001\n"})
    return run.report() == HEADER + "2026-10,North,11.25\n2026-10,South,23.00\n"


def eu_format():
    run = Run({"stores.csv": STORES,
               "sales-eu.csv": "date;amount;store\n2026-10-02;19,90;31\n2026-10-05;0,10;31\n2026-10-06;100;7\n",
               "sales-eu-west.csv": "date;amount;store\r\n2026-10-07;1,005;31\r\n",
               "sales-a.csv": "date,amount,store\n2026-10-01,10.00,1\n"})
    return run.report() == HEADER + "2026-10,EU,21.01\n2026-10,North,10.00\n2026-10,South,100.00\n"


def rebuild():
    run = Run({"stores.csv": STORES, "sales-a.csv": "date,amount,store\n2026-10-01,10.00,1\n2026-10-02,20.00,7\n"})
    if run.report() != HEADER + "2026-10,North,10.00\n2026-10,South,20.00\n":
        return False
    time.sleep(1.1)
    run.write("stores.csv", STORES.replace("7,Station Square,South", "7,Station Square,North"))
    if run.report() != HEADER + "2026-10,North,30.00\n":
        return False
    time.sleep(1.1)
    run.write("sales-b.csv", "date,amount,store\n2026-10-03,1.00,12\n")
    return run.report() == HEADER + "2026-10,North,30.00\n2026-10,South,1.00\n"


def combined():
    run = Run({"stores.csv": "store_id,name,region\n001,Harbour Street,North\n002,Old Mill,North\n007,Station Square,South\n12,Riverside,South\n031,Canal Gate,EU\n",
               "sales-north.csv": "date,amount,store\r\n2026-09-28,120.50,1\r\n2026-10-01,80.25,2\r\n2026-10-31,0.005,1",
               "sales-south.csv": "date,amount,store\n2026-09-30,60.00,7\n2026-10-01,33.30,12",
               "sales-eu.csv": "date;amount;store\r\n2026-09-15;12,345;31\r\n2026-10-15;0,005;031"})
    return run.report() == HEADER + "2026-09,EU,12.35\n2026-09,North,120.50\n2026-09,South,60.00\n2026-10,EU,0.01\n2026-10,North,80.26\n2026-10,South,33.30\n"


def regression():
    """The shipped tests pass, a plain export still works, and make clean removes the build."""
    run = Run({"stores.csv": STORES, "sales-a.csv": "date,amount,store\n2026-10-01,10.00,1\n2026-10-02,2.50,12\n"})
    if run.report() != HEADER + "2026-10,North,10.00\n2026-10,South,2.50\n" or run.make("test") != 0:
        return False
    return run.make("clean") == 0 and not os.path.exists(os.path.join(run.directory, "build")) and not os.path.exists(os.path.join(run.directory, "report.csv"))


CHECKS = {"line-ends": line_ends, "store-ids": store_ids, "eu-format": eu_format, "rebuild": rebuild, "combined": combined, "regression": regression}

if __name__ == "__main__":
    results = {name: check(function) for name, function in CHECKS.items()}
    # The regression check guards the fixes, so it counts only once some other check passes: the shipped pipeline passes it.
    results["regression"] = results["regression"] and any(value for name, value in results.items() if name != "regression")
    print(json.dumps(results))
