#!/usr/bin/env python3
"""Builds the R1 package from a seed: item prompts, private keys, and the manifest with every file hash.

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
import roster  # noqa: E402

TASK_ID = "r1-rostering"
TASK_VERSION = "0.1.0"
GRADER_VERSION = "1.0.0"
TRUSTED = ["calibration.md", "rubric.md", "private/generate.py", "private/grader.py", "private/keys.json", "private/roster.py"]
RULE_REQUIREMENTS = ["REQ-COVERAGE"] + ["REQ-" + rule.upper().replace("_", "-") for rule in roster.RULES]


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
    for level in roster.LEVELS:
        kinds = [True] * (args.per_level // 2) + [False] * (args.per_level - args.per_level // 2)
        random.Random(f"{args.seed}:{level}:order").shuffle(kinds)
        for index, feasible in enumerate(kinds, 1):
            item_id = f"{level}-{index:02d}"
            record = roster.generate(level, feasible, random.Random(f"{args.seed}:{item_id}"))
            keys[item_id] = record
            path = f"items/{item_id}/prompt.md"
            write_text(path, roster.prompt(item_id, record))
            active = (["REQ-COVERAGE"] + ["REQ-" + rule.upper().replace("_", "-") for rule in record["rules"]] if feasible
                      else ["REQ-VERDICT", "REQ-CONFLICT"]) + ["REQ-FORMAT"]
            items.append({"id": item_id, "level": level, "files": [{"path": path, "sha256": digest(path)}], "activeRequirementIds": active})
            print(f"{item_id}: {'feasible' if feasible else 'infeasible'}, rules {record['rules']}", file=sys.stderr)
    write_text("private/keys.json", json.dumps(keys, indent=1, ensure_ascii=False) + "\n")
    requirements = [{"id": requirement, "critical": True, "introducedAt": f"{TASK_ID} {TASK_VERSION}",
                     "checkIds": ["rule-" + requirement[len("REQ-"):].lower()]} for requirement in RULE_REQUIREMENTS]
    requirements += [{"id": "REQ-VERDICT", "critical": True, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": ["verdict"]},
                     {"id": "REQ-CONFLICT", "critical": True, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": ["conflict"]}]
    requirements.append({"id": "REQ-FORMAT", "critical": False, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": ["answer-format"]})
    manifest = {
        "schemaVersion": 1, "id": TASK_ID, "version": TASK_VERSION, "familyId": "r1-rostering", "capability": "reasoning", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md", "task-library/calibration/rsn-001-shift-scheduling"]},
        "license": {"taskText": "Original project-authored generator and instances; generalises rsn-001, and no text is copied.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}],
                  "trusted": [{"path": path, "sha256": digest(path)} for path in TRUSTED]},
        "requirements": requirements,
        "scoring": {"formatCheckId": "answer-format", "formatPenalty": 0.2},
        "items": items,
        "generator": {"entryPoint": "private/generate.py", "seed": args.seed, "perLevel": args.per_level},
        "toolProfiles": ["workspace-basic"],
        "grader": {"id": "r1-rostering-rules", "version": GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"], "answerSource": "execution-output"},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    write_text("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
