#!/usr/bin/env python3
"""The anchors of every AE item (task 0.2.0), written to private/anchors.json:

- naive: the AtCoder performance of the item's naive reference (the simplest valid strategy), judged like a delivery;
- median-contestant: the performance of the contest's median ranked contestant;
- winner: the performance of the contest's winner.

They map to 0, 0.5 and 1 (docs/design/v2/TASK_LIBRARY.md §3.6). Usage: python3 private/anchors.py (from the package)."""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import ale  # noqa: E402
import grader  # noqa: E402

LAUNCHER = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "scripts", "sandbox_exec.py"))
NAIVE = {"ahc015": "forward.cpp", "ahc026": "naive.cpp", "ahc028": "naive.cpp", "ahc032": "naive.cpp", "ahc035": "first-seeds.cpp",
         "ahc039": "tiny.cpp", "ahc041": "naive.cpp", "ahc042": "hint.cpp", "ahc044": "naive.cpp", "ahc046": "moves.cpp"}


def main():
    anchors = {}
    for item_id, name in sorted(NAIVE.items()):
        with tempfile.TemporaryDirectory() as public, open(os.path.join(HERE, "references", item_id, name), encoding="utf-8") as source:
            with open(os.path.join(public, "main.cpp"), "w", encoding="utf-8") as target:
                target.write(source.read())
            results, evidence = grader.grade(item_id, public, LAUNCHER)
        directory = grader.problem_directory(item_id)
        human = ale.anchors_of(ale.load_table(os.path.join(directory, "standings_scores.csv"), "score"),
                               ale.load_table(os.path.join(directory, "performance.csv"), "performance"))
        if not results["accepted"]:
            raise SystemExit(f"{item_id}: the naive reference is not accepted on every case: {evidence['verdicts']}")
        if not evidence["performance"] < human["median-contestant"] < human["winner"]:
            raise SystemExit(f"{item_id}: anchors out of order: naive {evidence['performance']}, {human}")
        anchors[item_id] = {"naive": evidence["performance"], **human,
                            "naiveReference": f"references/{item_id}/{name}", "naiveTotal": evidence["total"], "naiveRank": evidence["rank"],
                            "contestants": evidence["contestants"]}
        print(f"{item_id}: naive {evidence['performance']} (total {evidence['total']}, rank {evidence['rank']}/{evidence['contestants']}), "
              f"median {human['median-contestant']}, winner {human['winner']}", flush=True)
    with open(os.path.join(HERE, "anchors.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(anchors, handle, indent=1, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
