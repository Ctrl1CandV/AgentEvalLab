#!/usr/bin/env python3
"""Public checker for this stage only; invoked from the pinned task package."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SANDBOX_LAUNCHER = ""  # set from --sandbox-launcher in main


def run(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    command = ["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/cli.ts", *args]
    if SANDBOX_LAUNCHER:
        command = [sys.executable, SANDBOX_LAUNCHER, "--rw", str(root), "--", *command]
    return subprocess.run(command, cwd=root,
                          text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=8, check=False)

def check_s2(root: Path) -> tuple[bool, str, str]:
    with tempfile.TemporaryDirectory(prefix="eng005-public-") as temp:
        copy = Path(temp)
        shutil.copytree(root / "src", copy / "src")
        shutil.copytree(root / "data", copy / "data")
        self_dep = run(copy, ["depends", "add", "WO-101", "WO-101"])
        first = run(copy, ["depends", "add", "WO-101", "WO-102"])
        cycle = run(copy, ["depends", "add", "WO-102", "WO-101"])
        dep_open = run(copy, ["depends", "add", "WO-103", "WO-104"])
        premature = run(copy, ["update", "WO-103", "--status", "DONE"])
        valid = all(result.returncode != 0 for result in (self_dep, cycle, premature)) and \
            first.returncode == dep_open.returncode == 0
        return valid, "DEPENDENCY_RULE_MISMATCH", "Check self/cycle rejection, forward-only states, and incomplete prerequisites."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=["S2"])
    parser.add_argument("--sandbox-launcher", default="")
    args = parser.parse_args()
    global SANDBOX_LAUNCHER
    SANDBOX_LAUNCHER = args.sandbox_launcher
    valid, code, feedback = check_s2(args.submission)
    output = {"schemaVersion": 1, "stageId": "S2", "status": "passed" if valid else "failed",
              "checks": [{"id": "public-s2", "passed": valid,
                          "reasonCode": "OK" if valid else code, "feedback": "Public contract passed." if valid else feedback}]}
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
