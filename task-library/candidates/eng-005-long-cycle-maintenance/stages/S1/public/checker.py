#!/usr/bin/env python3
"""Public checker for this stage only; invoked from the pinned task package."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SANDBOX_LAUNCHER = ""  # set from --sandbox-launcher in main


def run(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    command = ["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/cli.ts", *args]
    if SANDBOX_LAUNCHER:
        command = [sys.executable, SANDBOX_LAUNCHER, "--rw", str(root), "--", *command]
    return subprocess.run(command, cwd=root,
                          text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=8, check=False)

def check_s1(root: Path) -> tuple[bool, str, str]:
    result = run(root, ["list", "--status", "OPEN", "--sort", "createdAt", "--order", "asc", "--page", "1", "--page-size", "10"])
    try:
        value = json.loads(result.stdout)
        valid = result.returncode == 0 and value["total"] == 2 and value["page"] == 1 and value["pageSize"] == 10 and \
            [item["id"] for item in value["items"]] == ["WO-101", "WO-104"]
        return valid, "QUERY_MISMATCH", "Filtered results, ordering, or response shape do not match the public contract."
    except (json.JSONDecodeError, KeyError, TypeError):
        return False, "QUERY_OUTPUT_INVALID", "`list` must return the documented paginated JSON object."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=["S1"])
    parser.add_argument("--sandbox-launcher", default="")
    args = parser.parse_args()
    global SANDBOX_LAUNCHER
    SANDBOX_LAUNCHER = args.sandbox_launcher
    valid, code, feedback = check_s1(args.submission)
    output = {"schemaVersion": 1, "stageId": "S1", "status": "passed" if valid else "failed",
              "checks": [{"id": "public-s1", "passed": valid,
                          "reasonCode": "OK" if valid else code, "feedback": "Public contract passed." if valid else feedback}]}
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
