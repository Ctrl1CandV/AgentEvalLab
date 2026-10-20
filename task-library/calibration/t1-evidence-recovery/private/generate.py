#!/usr/bin/env python3
"""Builds the T1 package from a seed: one snapshot and question set per item, private keys, and the manifest.

Usage: python3 private/generate.py --seed SEED --per-level N   (run from the package directory)
The same seed and arguments always produce the same snapshots, questions, keys and manifest.
"""
import argparse
import hashlib
import json
import os
import random
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snapshot  # noqa: E402

TASK_ID = "t1-evidence-recovery"
TASK_VERSION = "0.3.0"
GRADER_VERSION = "1.4.0"
TRUSTED = ["calibration.md", "rubric.md", "private/generate.py", "private/grader.py", "private/keys.json", "private/snapshot.py"]


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
    for level in snapshot.LEVELS:
        for index in range(1, args.per_level + 1):
            item_id = f"{level}-{index:02d}"
            snap, project, questions = snapshot.build(level, random.Random(f"{args.seed}:{item_id}"))
            files = []
            for path in sorted(snap.files):
                target = f"items/{item_id}/public/snapshot/{path}"
                write_text(target, snap.text(path))
                files.append({"path": target, "sha256": digest(target)})
            prompt_path = f"items/{item_id}/prompt.md"
            write_text(prompt_path, snapshot.prompt(item_id, project, questions))
            files.insert(0, {"path": prompt_path, "sha256": digest(prompt_path)})
            keys[item_id] = {"project": project, "questions": questions}
            items.append({"id": item_id, "level": level, "files": files,
                          "activeRequirementIds": [f"REQ-Q{number}" for number in range(1, len(questions) + 1)] + ["REQ-FORMAT"]})
            size = sum(len(snap.text(path)) for path in snap.files)
            print(f"{item_id}: {len(snap.files)} files, {size} characters, questions {[question['kind'] for question in questions]}", file=sys.stderr)
    write_text("private/keys.json", json.dumps(keys, indent=1, ensure_ascii=False) + "\n")
    requirements = [{"id": f"REQ-Q{number}", "critical": True, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": [f"q{number}"]}
                    for number in range(1, snapshot.MAX_QUESTIONS + 1)]
    requirements.append({"id": "REQ-FORMAT", "critical": False, "introducedAt": f"{TASK_ID} {TASK_VERSION}", "checkIds": ["answer-format"]})
    manifest = {
        "schemaVersion": 1, "id": TASK_ID, "version": TASK_VERSION, "familyId": "t1-evidence-recovery", "capability": "tool", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md", "task-library/calibration/tool-001-doc-evidence-recovery"]},
        "license": {"taskText": "Original project-authored generator and snapshots; generalises tool-001, and no text is copied.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}],
                  "trusted": [{"path": path, "sha256": digest(path)} for path in TRUSTED]},
        "requirements": requirements,
        "scoring": {"formatCheckId": "answer-format", "formatPenalty": 0.2},
        "items": items,
        "generator": {"entryPoint": "private/generate.py", "seed": args.seed, "perLevel": args.per_level},
        "toolProfiles": ["doc-evidence"],
        "grader": {"id": "t1-evidence-trace", "version": GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"], "answerSource": "execution-output", "requiresTrace": True},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    write_text("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
