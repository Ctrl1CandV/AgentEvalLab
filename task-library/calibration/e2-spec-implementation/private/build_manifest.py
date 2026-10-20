#!/usr/bin/env python3
"""Writes the E2 manifest: items, requirements from each item's fixture groups, and every file hash."""
import hashlib
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(".")
ITEMS = {"sheet": "sheet", "ledger": "ledger", "recur": "recur", "query": "query"}
VERSION, GRADER_VERSION = "0.4.0", "1.4.0"


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def checks_of(item):
    spec = importlib.util.spec_from_file_location(f"{item}_fixtures", ROOT / "private" / item / "fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return sorted({check for check, *_ in module.FIXTURES})


def main():
    trusted = ["calibration.md", "rubric.md"] + sorted(str(path.relative_to(ROOT)) for path in (ROOT / "private").rglob("*")
                                                     if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc")
                                                     and not any(part.startswith(".") for part in path.parts))
    requirements, items = [], []
    for item, level in ITEMS.items():
        ids = [f"REQ-{item.upper()}-{check.upper()}" for check in checks_of(item)]
        requirements += [{"id": requirement, "critical": True, "introducedAt": f"e2-spec-implementation {VERSION}", "checkIds": [f"{item}-{check}"]}
                         for requirement, check in zip(ids, checks_of(item))]
        files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "items" / item).rglob("*") if path.is_file() and not any(part.startswith(".") for part in path.parts))
        items.append({"id": item, "level": level, "files": [{"path": path, "sha256": digest(path)} for path in files], "activeRequirementIds": ids + ["REQ-README"]})
    requirements.append({"id": "REQ-README", "critical": True, "introducedAt": f"e2-spec-implementation {VERSION}", "checkIds": ["readme"]})
    manifest = {
        "schemaVersion": 1, "id": "e2-spec-implementation", "version": VERSION, "familyId": "e2-spec-implementation", "capability": "engineering", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md"]},
        "license": {"taskText": "Original project-authored specifications, references and fixtures.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}], "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": requirements, "items": items, "toolProfiles": ["workspace-basic"],
        "grader": {"id": "e2-fixtures", "version": GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"]},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
