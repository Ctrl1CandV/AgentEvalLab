#!/usr/bin/env python3
"""Writes anchors.json: each instance's baseline cost and best-known cost, the best of several long reference runs.
Usage: python3 compute_anchors.py SECONDS SEEDS   (runs in parallel; takes about SECONDS per batch of 20 runs)"""
import json
import multiprocessing
import os
import sys

import instances
import model
import reference

HERE = os.path.dirname(os.path.abspath(__file__))


def run(job):
    name, seconds, seed = job
    return name, seed, reference.solve(instances.instance(name), seconds, seed)[0]


def main():
    seconds, seeds = float(sys.argv[1]), int(sys.argv[2])
    names = list(instances.SAMPLES) + list(instances.HIDDEN)
    jobs = [(name, seconds, seed) for name in names for seed in range(1, seeds + 1)]
    with multiprocessing.Pool(min(18, len(jobs))) as pool:
        results = pool.map(run, jobs)
    anchors = {}
    for name in names:
        data = instances.instance(name)
        costs = sorted(cost for other, _, cost in results if other == name)
        anchors[name] = {"customers": len(data["customers"]), "vans": len(data["vans"]),
                         "baseline": model.check(data, model.baseline(data))[0], "best": costs[0], "runs": costs}
        print(name, anchors[name]["baseline"], costs, file=sys.stderr)
    with open(os.path.join(HERE, "anchors.json"), "w", encoding="utf-8") as handle:
        json.dump(anchors, handle, indent=1)
        handle.write("\n")


if __name__ == "__main__":
    main()
