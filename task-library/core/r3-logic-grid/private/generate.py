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

LEVELS = [("L1", 4), ("L2", 5), ("L3", 6), ("L4", 7), ("L5", 8), ("L6", 9), ("L7", 10)]
MAX_SIZE = max(size for _, size in LEVELS)
# Validation and holdout (0.4.0, PLAN-007 WP2.3): new structure groups, never piloted: rectangular grids of 7 to 10
# houses by 7 to 10 attributes (the dev levels are all square). The twelve shapes are dealt to the two splits by a
# seeded shuffle, six each, with SHAPE_ITEMS puzzles per shape; their contents are not read while designing.
SHAPES = [(houses, attributes) for houses in range(7, 11) for attributes in range(7, 11) if houses != attributes]
SPLIT_SEED = "r3-2026-10-splits"
SHAPE_ITEMS = 4
TASK_ID = "r3-logic-grid"
TASK_VERSION = "0.4.0"
GRADER_VERSION = "2.1.0"
TRUSTED = ["calibration.md", "card.md", "rubric.md", "private/generate.py", "private/grader.py", "private/keys.json", "private/logic_grid.py"]
# Manifest v2 (grader 2.0.0): every item of L1-L7 has been seen in pilots, so all of them are dev; a structure group is
# a grid size, since a level's items share the generator template (VALIDATION §3).
SPLIT = "dev"
PUBLISHED = "2026-10-20"
SHAPES_PUBLISHED = "2026-10-24"


def shape_splits():
    """{(houses, attributes): split} for the validation and holdout shapes."""
    shapes = list(SHAPES)
    random.Random(SPLIT_SEED).shuffle(shapes)
    half = len(shapes) // 2
    return {shape: "validation" if index < half else "holdout" for index, shape in enumerate(shapes)}


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
                          "activeRequirementIds": cells + ["REQ-FORMAT"], "split": SPLIT, "structure": f"size:{size}x{size}",
                          "provenance": {"source": f"project generator private/generate.py, seed {args.seed}", "published": PUBLISHED,
                                         "license": "project-authored", "exposure": "generated"}})
            print(f"{item_id}: {size}x{size}, {len(puzzle['clues'])} clues", file=sys.stderr)
    for (houses, attributes), split in sorted(shape_splits().items()):
        for index in range(1, SHAPE_ITEMS + 1):
            item_id = f"P{houses}x{attributes}-{index:02d}"
            puzzle = logic_grid.generate(houses, attributes, random.Random(f"{args.seed}:{item_id}"))
            keys[item_id] = puzzle
            path = f"items/{item_id}/prompt.md"
            write_text(path, logic_grid.prompt(item_id, puzzle))
            cells = [f"REQ-H{h}-A{a}" for h in range(1, houses + 1) for a in range(1, attributes + 1)]
            items.append({"id": item_id, "level": f"{houses}x{attributes}", "files": [{"path": path, "sha256": digest(path)}],
                          "activeRequirementIds": cells + ["REQ-FORMAT"], "split": split, "structure": f"size:{houses}x{attributes}",
                          "provenance": {"source": f"project generator private/generate.py, seed {args.seed}", "published": SHAPES_PUBLISHED,
                                         "license": "project-authored", "exposure": "generated"}})
            # Structure metadata only: the contents of validation and holdout items are not read while designing.
            print(f"{item_id}: {houses}x{attributes} {split}, {len(puzzle['clues'])} clues", file=sys.stderr)
    write_text("private/keys.json", json.dumps(keys, indent=1, ensure_ascii=False) + "\n")
    requirements = [{"id": f"REQ-H{h}-A{a}", "critical": True, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": [f"cell-h{h}-a{a}"]}
                    for h in range(1, MAX_SIZE + 1) for a in range(1, MAX_SIZE + 1)]
    requirements.append({"id": "REQ-FORMAT", "critical": False, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": ["answer-format"]})
    cell_checks = [f"cell-h{h}-a{a}" for h in range(1, MAX_SIZE + 1) for a in range(1, MAX_SIZE + 1)]
    manifest = {
        "schemaVersion": 2, "id": TASK_ID, "version": TASK_VERSION, "familyId": "r3-logic-grid", "capability": "reasoning", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md", "https://arxiv.org/pdf/2502.01100"]},
        "license": {"taskText": "Original project-authored generator and puzzles; ZebraLogic inspired the form, and no text is copied.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}],
                  "trusted": [{"path": path, "sha256": digest(path)} for path in TRUSTED]},
        "requirements": requirements,
        "tier": "core", "capabilities": ["reasoning"], "card": "card.md",
        "scoreModel": {
            "primary": {"kind": "resolved"},
            "groups": [{"id": "cells", "weight": 1, "critical": True, "rule": "fraction", "checkIds": cell_checks}],
            "metrics": [{"id": "cellAccuracy", "unit": "share of cells", "direction": "higher"},
                        {"id": "constraintValidity", "unit": "share of clues", "direction": "higher"},
                        {"id": "wellFormed", "unit": "0 or 1", "direction": "higher"}],
            "format": {"checkId": "answer-format", "penalty": 0.1},
        },
        "items": items,
        "generator": {"entryPoint": "private/generate.py", "seed": args.seed, "perLevel": args.per_level},
        "toolProfiles": ["none"],
        "grader": {"id": "r3-logic-grid-cells", "version": GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"], "answerSource": "execution-output"},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    write_text("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
