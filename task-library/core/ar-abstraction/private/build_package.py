#!/usr/bin/env python3
"""Builds the AR package from the public ARC-AGI evaluation sets: one item per task (its training pairs and test inputs
in the prompt and in public/task.json), the private keys (the test outputs), and the manifest with every file hash.

Usage: python3 private/build_package.py   (run from the package directory)
Sources: the ARC-AGI-1 and ARC-AGI-2 repositories (Apache-2.0), cloned under ~/.cache/agenteval/sources/ at the commits
below. The selection and the splits are drawn by a fixed seed, by task (the structure group is the task), and only task
ids and counts are read while building: the validation and holdout tasks are not opened while designing.
"""
import hashlib
import json
import os
import pathlib
import random
import shutil
import subprocess
import sys

ROOT = pathlib.Path(".")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grader  # noqa: E402

SOURCES = {
    "a1": {"path": pathlib.Path.home() / ".cache/agenteval/sources/arc-agi-1", "commit": "399030444e0ab0cc8b4e199870fb20b863846f34",
           "name": "ARC-AGI-1 public evaluation (fchollet/ARC-AGI)", "published": "2019-11", "level": "arc1"},
    "a2": {"path": pathlib.Path.home() / ".cache/agenteval/sources/arc-agi-2", "commit": "f3283f727488ad98fe575ea6a5ac981e4a188e49",
           "name": "ARC-AGI-2 public evaluation (arcprize/ARC-AGI-2)", "published": "2025-03", "level": "arc2"},
}
SEED = "ar-2026-10"
# TASK_LIBRARY §3.2: dev 20 + 20, validation 30 + 50, holdout 30 + 50 (ARC-1 + ARC-2); every ARC-2 evaluation task.
COUNTS = {"a1": {"dev": 20, "validation": 30, "holdout": 30}, "a2": {"dev": 20, "validation": 50, "holdout": 50}}
MAX_TESTS = 3


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def write_text(path, text):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def render(item_id, task):
    def block(label, grid):
        return [f"{label} ({len(grid)} rows, {len(grid[0])} columns):", *(" ".join(str(cell) for cell in row) for row in grid), ""]
    lines = [f"## Task {item_id}", "", "### Examples", ""]
    for index, pair in enumerate(task["train"], 1):
        lines += block(f"Example {index}, input", pair["input"]) + block(f"Example {index}, output", pair["output"])
    lines += ["### Test inputs", ""]
    for index, pair in enumerate(task["test"], 1):
        lines += block(f"Test input {index}", pair["input"])
    count = len(task["test"])
    lines.append(f"Answer for the {count} test input{'s' if count > 1 else ''} above, in order.")
    return "\n".join(lines) + "\n"


def selection():
    """{item id: (source key, task id, split)}, drawn by the seed from the task ids only."""
    ids = {key: sorted(path.stem for path in (source["path"] / "data" / "evaluation").glob("*.json")) for key, source in SOURCES.items()}
    # Six ARC-AGI-1 evaluation tasks are also ARC-AGI-2 evaluation tasks: they count once, as ARC-2.
    ids["a1"] = [task for task in ids["a1"] if task not in set(ids["a2"])]
    chosen = {}
    for key, counts in COUNTS.items():
        order = list(ids[key])
        random.Random(f"{SEED}:{key}").shuffle(order)
        position = 0
        for split in ("dev", "validation", "holdout"):
            for task in order[position:position + counts[split]]:
                chosen[f"{key}-{task}"] = (key, task, split)
            position += counts[split]
    return chosen


def main():
    for key, source in SOURCES.items():
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source["path"], capture_output=True, text=True, check=True).stdout.strip()
        if head != source["commit"]:
            raise SystemExit(f"{key}: the source is at {head}, not {source['commit']}")
    if (ROOT / "items").exists():
        shutil.rmtree(ROOT / "items")
    (ROOT / "private" / "licenses").mkdir(parents=True, exist_ok=True)
    shutil.copy(SOURCES["a1"]["path"] / "LICENSE", ROOT / "private" / "licenses" / "ARC-AGI-1-LICENSE")
    shutil.copy(SOURCES["a2"]["path"] / "LICENSE", ROOT / "private" / "licenses" / "ARC-AGI-2-LICENSE")
    keys, items = {}, []
    for item_id, (key, task_id, split) in sorted(selection().items()):
        source = SOURCES[key]
        task = json.loads((source["path"] / "data" / "evaluation" / f"{task_id}.json").read_text(encoding="utf-8"))
        if not 1 <= len(task["test"]) <= MAX_TESTS:
            raise SystemExit(f"{item_id}: {len(task['test'])} test inputs")
        keys[item_id] = [pair["output"] for pair in task["test"]]
        write_text(f"items/{item_id}/prompt.md", render(item_id, task))
        public = {"train": task["train"], "test": [{"input": pair["input"]} for pair in task["test"]]}
        write_text(f"items/{item_id}/public/task.json", json.dumps(public, separators=(",", ":")) + "\n")
        files = [f"items/{item_id}/prompt.md", f"items/{item_id}/public/task.json"]
        items.append({"id": item_id, "level": source["level"], "files": [{"path": path, "sha256": digest(path)} for path in files],
                      "activeRequirementIds": [f"REQ-TEST-{index}" for index in range(1, len(task["test"]) + 1)] + ["REQ-FORMAT"],
                      "split": split, "structure": f"task:{item_id}",
                      "provenance": {"source": f"{source['name']} @{source['commit'][:7]}, task {task_id}", "published": source["published"],
                                     "license": "Apache-2.0", "exposure": "public"}})
    write_text("private/keys.json", json.dumps(keys, separators=(",", ":")) + "\n")
    requirements = [{"id": f"REQ-TEST-{index}", "critical": True, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}", "checkIds": [f"test-{index}"]}
                    for index in range(1, MAX_TESTS + 1)]
    requirements.append({"id": "REQ-FORMAT", "critical": False, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}", "checkIds": ["answer-format"]})
    trusted = ["calibration.md", "card.md", "rubric.md", "private/build_package.py", "private/grader.py", "private/keys.json",
               "private/licenses/ARC-AGI-1-LICENSE", "private/licenses/ARC-AGI-2-LICENSE"]
    manifest = {
        "schemaVersion": 2, "id": grader.TASK_ID, "version": grader.TASK_VERSION, "familyId": "ar-abstraction", "capability": "reasoning", "usage": "development",
        "source": {"kind": "open-source", "references": ["https://github.com/fchollet/ARC-AGI", "https://github.com/arcprize/ARC-AGI-2",
                                                         "https://arxiv.org/abs/1911.01547"]},
        "license": {"taskText": "Instruction and rendering project-authored; tasks from ARC-AGI-1 and ARC-AGI-2, unmodified.",
                    "thirdPartyContent": ["ARC-AGI-1 (Apache-2.0, François Chollet)", "ARC-AGI-2 (Apache-2.0, ARC Prize Foundation)"]},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}],
                  "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": requirements,
        "tier": "core", "capabilities": ["reasoning"], "card": "card.md",
        "scoreModel": {
            "primary": {"kind": "resolved"},
            "groups": [{"id": "outputs", "weight": 1, "critical": True, "rule": "fraction", "checkIds": [f"test-{index}" for index in range(1, MAX_TESTS + 1)]}],
            "metrics": [{"id": "testShare", "unit": "share of test outputs matched", "direction": "higher"},
                        {"id": "wellFormed", "unit": "0 or 1", "direction": "higher"}],
            "format": {"checkId": "answer-format", "penalty": 0.1},
        },
        "items": items,
        "toolProfiles": ["none", "workspace-basic"],
        "grader": {"id": "ar-pass-at-2", "version": grader.GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"], "answerSource": "execution-output"},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    write_text("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    counts = {}
    for item in items:
        counts[(item["level"], item["split"])] = counts.get((item["level"], item["split"]), 0) + 1
    print(json.dumps({f"{level} {split}": count for (level, split), count in sorted(counts.items())}), file=sys.stderr)


if __name__ == "__main__":
    main()
