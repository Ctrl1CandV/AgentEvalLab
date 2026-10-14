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

def check_s3(root: Path) -> tuple[bool, str, str]:
    with tempfile.TemporaryDirectory(prefix="eng005-public-") as temp:
        copy = Path(temp)
        shutil.copytree(root / "src", copy / "src")
        shutil.copytree(root / "data", copy / "data")
        state_path = copy / "data" / "work-orders.json"
        before = state_path.read_bytes()
        self_dep = run(copy, ["depends", "add", "WO-101", "WO-101"])
        unchanged_self = state_path.read_bytes() == before
        setup = run(copy, ["depends", "add", "WO-101", "WO-102"])
        if setup.returncode != 0:
            return False, "DEPENDENCY_SETUP_FAILED", "The public cycle reproduction could not establish its documented first edge."
        before_cycle = state_path.read_bytes()
        cycle = run(copy, ["depends", "add", "WO-102", "WO-101"])
        unchanged_cycle = state_path.read_bytes() == before_cycle
        before_transition = state_path.read_bytes()
        transition = run(copy, ["update", "WO-101", "--status", "DONE"])
        unchanged_transition = state_path.read_bytes() == before_transition
        valid = self_dep.returncode != 0 and cycle.returncode != 0 and transition.returncode != 0 and \
            unchanged_self and unchanged_cycle and unchanged_transition
        return valid, "REJECTED_OPERATION_MUTATED_STORE", "The rejected public reproduction changed persistent bytes."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=["S3"])
    parser.add_argument("--sandbox-launcher", default="")
    args = parser.parse_args()
    global SANDBOX_LAUNCHER
    SANDBOX_LAUNCHER = args.sandbox_launcher
    valid, code, feedback = check_s3(args.submission)
    output = {"schemaVersion": 1, "stageId": "S3", "status": "passed" if valid else "failed",
              "checks": [{"id": "public-s3", "passed": valid,
                          "reasonCode": "OK" if valid else code, "feedback": "Public contract passed." if valid else feedback}]}
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
