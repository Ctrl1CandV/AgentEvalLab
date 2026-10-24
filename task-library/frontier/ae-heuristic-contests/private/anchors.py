#!/usr/bin/env python3
"""The anchors of every AE item (task 0.2.0), written to private/anchors.json:

- naive: the AtCoder performance of the item's naive reference (the simplest valid strategy), judged like a delivery;
- median-contestant: the performance of the contest's median ranked contestant;
- winner: the performance of the contest's winner.

They map to 0, 0.5 and 1 (docs/design/v2/TASK_LIBRARY.md §3.6). Grader 2.1.0 adds, per item, the greedy reference's
performance, and the fresh-seed totals of the naive and greedy references: the anchors of `freshTotal` (naive 0,
greedy 1). Usage: python3 private/anchors.py (from the package)."""
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
GREEDY = {"ahc015": "by-flavour.cpp", "ahc026": "greedy.cpp", "ahc028": "greedy.cpp", "ahc032": "greedy.cpp", "ahc035": "top-value.cpp",
          "ahc039": "grid.cpp", "ahc041": "greedy.cpp", "ahc042": "greedy.cpp", "ahc044": "greedy.cpp", "ahc046": "greedy.cpp"}


def judged(item_id, name):
    with tempfile.TemporaryDirectory() as public, open(os.path.join(HERE, "references", item_id, name), encoding="utf-8") as source:
        with open(os.path.join(public, "main.cpp"), "w", encoding="utf-8") as target:
            target.write(source.read())
        return grader.grade(item_id, public, LAUNCHER)


def main():
    anchors = {}
    for item_id, name in sorted(NAIVE.items()):
        results, evidence = judged(item_id, name)
        greedy_results, greedy = judged(item_id, GREEDY[item_id])
        directory = grader.problem_directory(item_id)
        human = ale.anchors_of(ale.load_table(os.path.join(directory, "standings_scores.csv"), "score"),
                               ale.load_table(os.path.join(directory, "performance.csv"), "performance"))
        if not results["accepted"]:
            raise SystemExit(f"{item_id}: the naive reference is not accepted on every case: {evidence['verdicts']}")
        if not evidence["performance"] < human["median-contestant"] < human["winner"]:
            raise SystemExit(f"{item_id}: anchors out of order: naive {evidence['performance']}, {human}")
        if not greedy_results["accepted"] or not greedy["freshTotal"] > evidence["freshTotal"] > 0:
            raise SystemExit(f"{item_id}: the greedy reference does not beat the naive one on the fresh seeds: {greedy['freshTotal']} vs {evidence['freshTotal']}")
        anchors[item_id] = {"naive": evidence["performance"], **human,
                            "naiveReference": f"references/{item_id}/{name}", "naiveTotal": evidence["total"], "naiveRank": evidence["rank"],
                            "contestants": evidence["contestants"], "greedy": greedy["performance"], "greedyReference": f"references/{item_id}/{GREEDY[item_id]}",
                            "greedyTotal": greedy["total"], "freshNaive": evidence["freshTotal"], "freshGreedy": greedy["freshTotal"]}
        print(f"{item_id}: naive {evidence['performance']} (total {evidence['total']}, rank {evidence['rank']}/{evidence['contestants']}), "
              f"greedy {greedy['performance']}, median {human['median-contestant']}, winner {human['winner']}; fresh naive {evidence['freshTotal']}, "
              f"fresh greedy {greedy['freshTotal']}", flush=True)
    with open(os.path.join(HERE, "anchors.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(anchors, handle, indent=1, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
