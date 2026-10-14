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

def check_s5(root: Path) -> tuple[bool, str, str]:
    first = run(root, ["does-not-exist"])
    second = run(root, ["does-not-exist"])
    try:
        one = json.loads(first.stdout)
        two = json.loads(second.stdout)
        readme = (root / "README.md").read_text(encoding="utf-8")
        valid = first.returncode == second.returncode == 2 and one == two and one["ok"] is False and \
            one["error"]["code"] == "UNKNOWN_COMMAND" and bool(one["error"]["message"]) and not first.stderr.strip() and \
            all(term in readme for term in ("pagination", "dependencies", "error codes", "version 1", "version 2", "events"))
        return valid, "FINAL_PROTOCOL_OR_DOCS_MISMATCH", "The public error protocol, stable code, or final README coverage is incomplete."
    except (json.JSONDecodeError, KeyError, TypeError, OSError):
        return False, "FINAL_OUTPUT_INVALID", "Failures must use the one-line JSON protocol and the final README must cover migration."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=["S5"])
    parser.add_argument("--sandbox-launcher", default="")
    args = parser.parse_args()
    global SANDBOX_LAUNCHER
    SANDBOX_LAUNCHER = args.sandbox_launcher
    valid, code, feedback = check_s5(args.submission)
    output = {"schemaVersion": 1, "stageId": "S5", "status": "passed" if valid else "failed",
              "checks": [{"id": "public-s5", "passed": valid,
                          "reasonCode": "OK" if valid else code, "feedback": "Public contract passed." if valid else feedback}]}
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
