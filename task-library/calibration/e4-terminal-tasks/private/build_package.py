#!/usr/bin/env python3
"""Builds the E4 package: generated workspace files, the bisect culprit, and the manifest with every file hash.

Usage: python3 private/build_package.py   (run from the package directory)
Generation is seeded; the Git history uses fixed authors and dates, so its commit hashes are reproducible.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(".")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bisect_item import history  # noqa: E402
from migrate import data as migrate_data  # noqa: E402
from perf import data as perf_data  # noqa: E402
import grader  # noqa: E402

VERSION = grader.TASK_VERSION
GRADER_VERSION = grader.GRADER_VERSION


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def generate():
    shutil.copy(HERE / "perf" / "original.py", ROOT / "items" / "perf" / "public" / "report.py")
    (ROOT / "items" / "perf" / "public" / "events.csv").write_text(perf_data.events(*perf_data.WORKSPACE), encoding="utf-8")
    database = ROOT / "items" / "migrate" / "public" / "shop.db"
    database.unlink(missing_ok=True)
    migrate_data.generated(str(database), *migrate_data.WORKSPACE)
    with tempfile.TemporaryDirectory() as scratch:
        repository = os.path.join(scratch, "pricing")
        culprit = history.build(repository)
        bundle = ROOT / "items" / "bisect" / "public" / "history.bundle"
        bundle.unlink(missing_ok=True)
        subprocess.run(["git", "bundle", "create", str(bundle.resolve()), "main"], cwd=repository, check=True, capture_output=True)
    (HERE / "bisect_item" / "culprit.txt").write_text(culprit + "\n", encoding="utf-8")


def main():
    generate()
    trusted = ["calibration.md", "rubric.md"] + sorted(str(path.relative_to(ROOT)) for path in (ROOT / "private").rglob("*")
                                                     if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc"))
    requirements, items = [], []
    for item, checks in grader.CHECKS.items():
        ids = [f"REQ-{item.upper()}-{check.upper()}" for check in checks]
        requirements += [{"id": requirement, "critical": True, "introducedAt": f"e4-terminal-tasks {VERSION}", "checkIds": [f"{item}-{check}"]}
                         for requirement, check in zip(ids, checks)]
        files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "items" / item).rglob("*") if path.is_file())
        items.append({"id": item, "level": item, "files": [{"path": path, "sha256": digest(path)} for path in files], "activeRequirementIds": ids})
    manifest = {
        "schemaVersion": 1, "id": "e4-terminal-tasks", "version": VERSION, "familyId": "e4-terminal-tasks", "capability": "engineering", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md"]},
        "license": {"taskText": "Original project-authored tasks, data, programs and checks.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}], "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": requirements, "items": items, "toolProfiles": ["workspace-basic"],
        "grader": {"id": "e4-terminal-checks", "version": GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"]},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; git, make, cc and coreutils from the host; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
