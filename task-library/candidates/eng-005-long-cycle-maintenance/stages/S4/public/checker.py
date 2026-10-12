#!/usr/bin/env python3
"""Public checker for this stage only; invoked from the pinned task package."""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

def run(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/cli.ts", *args], cwd=root,
                          text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=8, check=False)

def check_s4(root: Path, checker_dir: Path) -> tuple[bool, str, str]:
    fixture = json.loads((checker_dir / "v1-fixture.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="eng005-public-") as temp:
        copy = Path(temp)
        shutil.copytree(root / "src", copy / "src")
        (copy / "data").mkdir()
        state_path = copy / "data" / "work-orders.json"
        state_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        original = state_path.read_bytes()
        shown = run(copy, ["show", "FIX-01"])
        if shown.returncode != 0 or state_path.read_bytes() != original:
            return False, "READ_TRIGGERED_MIGRATION", "Read-only access must not rewrite the v1 store."
        first = run(copy, ["update", "FIX-01", "--title", "Updated server room inspection"])
        second = run(copy, ["update", "FIX-02", "--description", "Second update"])
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            migration_events = [event for event in state["events"] if event["type"] == "state_migrated"]
            sequences = [event["sequence"] for event in state["events"]]
            orders = {order["id"]: order for order in state["workOrders"]}
            exported = json.loads(run(copy, ["export", "json"]).stdout)
            valid = first.returncode == second.returncode == 0 and state["version"] == 2 and len(orders) == 2 and \
                orders["FIX-01"]["description"] == "" and orders["FIX-01"]["title"]== "Updated server room inspection" and \
                orders["FIX-02"]["description"] == "Second update" and len(migration_events) == 1 and \
                sequences == list(range(1, len(sequences) + 1)) and len(exported) == 2
            return valid, "MIGRATION_CONTRACT_MISMATCH", "Check v2 preservation, one-time migration history, contiguous sequences, and the legacy export shape."
        except (json.JSONDecodeError, KeyError, TypeError):
            return False, "V2_STORE_INVALID", "A successful v1 write must leave a valid v2 store and event array."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=["S4"])
    args = parser.parse_args()
    valid, code, feedback = check_s4(args.submission, Path(__file__).parent)
    output = {"schemaVersion": 1, "stageId": "S4", "status": "passed" if valid else "failed",
              "checks": [{"id": "public-s4", "passed": valid,
                          "reasonCode": "OK" if valid else code, "feedback": "Public contract passed." if valid else feedback}]}
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()

