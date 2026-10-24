#!/usr/bin/env python3
"""Public checker for this stage only; invoked from the pinned task package. It copies the submission, writes public
sample stores into the copy, and checks that plan produces valid plans in time without writing the store, and that
invalid arguments are rejected. It reports each plan's cost beside the naive and the greedy plan's; the hidden quality
scale also places plans against the best plan known."""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# The package declares its files exactly, so importing the stage's modules must not leave a bytecode cache beside them.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_plan_store  # noqa: E402
import plan_tools  # noqa: E402

SANDBOX_LAUNCHER = ""  # set from --sandbox-launcher in main
COMMAND_SECONDS = 10


def run(root: Path, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    command = ["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/cli.ts", *args]
    if SANDBOX_LAUNCHER:
        command = [sys.executable, SANDBOX_LAUNCHER, "--rw", str(root), "--", *command]
    try:
        return subprocess.run(command, cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True,
                              timeout=COMMAND_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return None


def code(result: subprocess.CompletedProcess[str] | None) -> str | None:
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])["error"]["code"] if result is not None and result.returncode == 2 else None
    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        return None


def check_s7(submission: Path) -> tuple[bool, str, str]:
    with tempfile.TemporaryDirectory(prefix="eng005-s7-public-") as temp:
        root = Path(temp) / "submission"
        shutil.copytree(submission, root, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
        (root / "data").mkdir(exist_ok=True)
        path = root / "data" / "work-orders.json"
        notes = []
        for kind in ("tiny", "chains", "general"):
            value = make_plan_store.store(kind, f"eng005-plan-public:{kind}")
            crews = make_plan_store.STORES[kind]["crews"]
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            before = path.read_bytes()
            started = time.perf_counter()
            result = run(root, ["plan", "--crews", str(crews)])
            seconds = time.perf_counter() - started
            if result is None:
                return False, "PLAN_TIMEOUT", f"plan --crews {crews} on the public {kind} store did not finish within {COMMAND_SECONDS} seconds."
            cost, reason = plan_tools.check(value, crews, result.stdout) if result.returncode == 0 else (None, f"exit code {result.returncode}")
            if cost is None:
                return False, "PLAN_INVALID", f"plan --crews {crews} on the public {kind} store is not a valid plan: {reason}."
            if path.read_bytes() != before:
                return False, "PLAN_WROTE_STORE", "plan must not write the store."
            work = plan_tools.jobs(value)
            notes.append(f"{kind}: cost {cost} (naive {plan_tools.cost_of(plan_tools.naive(work, crews), work)}, "
                         f"greedy {plan_tools.cost_of(plan_tools.greedy(work, crews), work)}), {seconds:.2f} s")
        for args in (["plan"], ["plan", "--crews", "0"], ["plan", "--crews", "51"], ["plan", "--crews", "2", "--fast", "1"]):
            if code(run(root, args)) != "INVALID_ARGUMENT":
                return False, "PLAN_ARGUMENTS", f"{' '.join(args)} must fail with INVALID_ARGUMENT."
        return True, "OK", "Valid plans; " + "; ".join(notes) + "."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=["S7"])
    parser.add_argument("--sandbox-launcher", default="")
    args = parser.parse_args()
    global SANDBOX_LAUNCHER
    SANDBOX_LAUNCHER = args.sandbox_launcher
    valid, reason, feedback = check_s7(args.submission)
    output = {"schemaVersion": 1, "stageId": "S7", "status": "passed" if valid else "failed",
              "checks": [{"id": "public-s7", "passed": valid, "reasonCode": reason, "feedback": feedback}]}
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
