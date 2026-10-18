#!/usr/bin/env python3
"""Builds the R3 package from a seed: item prompts, private keys, and the manifest with every file hash.

Usage: python3 private/generate.py --seed SEED --per-level N   (run from the package directory)
The same seed and arguments always produce the same items, keys and manifest.
"""
import argparse
import hashlib
import json
import os
import random
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logic_grid  # noqa: E402

LEVELS = [("L1", 4), ("L2", 5), ("L3", 6), ("L4", 7), ("L5", 8)]
MAX_SIZE = max(size for _, size in LEVELS)
TASK_ID = "r3-logic-grid"
TASK_VERSION = "0.1.0"
GRADER_VERSION = "1.0.0"
TRUSTED = ["calibration.md", "rubric.md", "private/generate.py", "private/grader.py", "private/keys.json", "private/logic_grid.py"]


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True)
    parser.add_argument("--per-level", type=int, required=True)
    args = parser.parse_args()
    if os.path.isdir("items"):
        shutil.rmtree("items")
    keys, items = {}, []
    for level, size in LEVELS:
        for index in range(1, args.per_level + 1):
            item_id = f"{level}-{index:02d}"
            puzzle = logic_grid.generate(size, size, random.Random(f"{args.seed}:{item_id}"))
            keys[item_id] = puzzle
            path = f"items/{item_id}/prompt.md"
            write_text(path, logic_grid.prompt(item_id, puzzle))
            cells = [f"REQ-H{h}-A{a}" for h in range(1, size + 1) for a in range(1, size + 1)]
            items.append({"id": item_id, "level": level, "files": [{"path": path, "sha256": digest(path)}],
                          "activeRequirementIds": cells + ["REQ-FORMAT"]})
            print(f"{item_id}: {size}x{size}, {len(puzzle['clues'])} clues", file=sys.stderr)
    write_text("private/keys.json", json.dumps(keys, indent=1, ensure_ascii=False) + "\n")
    requirements = [{"id": f"REQ-H{h}-A{a}", "critical": True, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": [f"cell-h{h}-a{a}"]}
                    for h in range(1, MAX_SIZE + 1) for a in range(1, MAX_SIZE + 1)]
    requirements.append({"id": "REQ-FORMAT", "critical": False, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": ["answer-format"]})
    manifest = {
        "schemaVersion": 1, "id": TASK_ID, "version": TASK_VERSION, "familyId": "r3-logic-grid", "capability": "reasoning", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md", "https://arxiv.org/pdf/2502.01100"]},
        "license": {"taskText": "Original project-authored generator and puzzles; ZebraLogic inspired the form, and no text is copied.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}],
                  "trusted": [{"path": path, "sha256": digest(path)} for path in TRUSTED]},
        "requirements": requirements,
        "scoring": {"formatCheckId": "answer-format", "formatPenalty": 0.2},
        "items": items,
        "generator": {"entryPoint": "private/generate.py", "seed": args.seed, "perLevel": args.per_level},
        "toolProfiles": ["workspace-basic"],
        "grader": {"id": "r3-logic-grid-cells", "version": GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"], "answerSource": "execution-output"},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    write_text("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
