#!/usr/bin/env python3
"""Public checker for this stage only; invoked from the pinned task package. It copies the submission, writes the
public scale store into the copy, and runs a few commands that must be correct and finish in time at this size."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# The package declares its files exactly, so importing the generator must not leave a bytecode cache beside it.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_store  # noqa: E402

SANDBOX_LAUNCHER = ""  # set from --sandbox-launcher in main
COMMAND_SECONDS = 10


def run(root: Path, args: list[str]) -> tuple[subprocess.CompletedProcess[str] | None, float]:
    command = ["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/cli.ts", *args]
    if SANDBOX_LAUNCHER:
        command = [sys.executable, SANDBOX_LAUNCHER, "--rw", str(root), "--", *command]
    started = time.perf_counter()
    try:
        result = subprocess.run(command, cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True,
                                timeout=COMMAND_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        result = None
    return result, time.perf_counter() - started


def code(result: subprocess.CompletedProcess[str] | None) -> str | None:
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])["error"]["code"] if result is not None and result.returncode == 2 else None
    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        return None


def check_s6(submission: Path) -> tuple[bool, str, str]:
    with tempfile.TemporaryDirectory(prefix="eng005-s6-public-") as temp:
        root = Path(temp) / "submission"
        shutil.copytree(submission, root, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
        (root / "data").mkdir(exist_ok=True)
        (root / "data" / "work-orders.json").write_text(json.dumps(make_store.store("eng005-scale-public"), ensure_ascii=False, indent=2) + "\n",
                                                         encoding="utf-8")
        cycle, cycle_time = run(root, ["depends", "add", "SC-000001", "SC-050000"])
        if code(cycle) != "DEPENDENCY_CYCLE":
            return False, "SCALE_CYCLE", f"depends add SC-000001 SC-050000 must fail with DEPENDENCY_CYCLE through the 50,000-deep chain within {COMMAND_SECONDS} seconds."
        added, added_time = run(root, ["depends", "add", "SC-080001", "SC-050000"])
        if added is None or added.returncode != 0:
            return False, "SCALE_DEPENDENCY", f"depends add SC-080001 SC-050000 creates no cycle and must succeed within {COMMAND_SECONDS} seconds."
        hub, hub_time = run(root, ["update", "SC-069001", "--status", "DONE"])
        if code(hub) != "DEPENDENCY_NOT_COMPLETE":
            return False, "SCALE_PREREQUISITES", "update SC-069001 --status DONE must fail with DEPENDENCY_NOT_COMPLETE: one of its 2,001 prerequisites is OPEN."
        listed, list_time = run(root, ["list", "--status", "OPEN", "--sort", "id", "--order", "desc", "--page", "3", "--page-size", "100"])
        try:
            page = json.loads(listed.stdout)
            ids = [row["id"] for row in page["items"]]
            ok = listed.returncode == 0 and len(ids) == 100 and ids == sorted(ids, reverse=True) and page["page"] == 3
        except (AttributeError, json.JSONDecodeError, KeyError, TypeError):
            ok = False
        if not ok:
            return False, "SCALE_LIST", "list --status OPEN --sort id --order desc --page 3 --page-size 100 must return 100 OPEN orders in descending id order."
        slowest = max(cycle_time, added_time, hub_time, list_time)
        return True, "OK", f"Scale contract passed; the slowest of four commands took {slowest:.2f} seconds."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=["S6"])
    parser.add_argument("--sandbox-launcher", default="")
    args = parser.parse_args()
    global SANDBOX_LAUNCHER
    SANDBOX_LAUNCHER = args.sandbox_launcher
    valid, reason, feedback = check_s6(args.submission)
    output = {"schemaVersion": 1, "stageId": "S6", "status": "passed" if valid else "failed",
              "checks": [{"id": "public-s6", "passed": valid, "reasonCode": reason, "feedback": feedback}]}
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
