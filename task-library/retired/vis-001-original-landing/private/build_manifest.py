#!/usr/bin/env python3
"""Writes the vis-001 manifest: hashes every public and trusted file. Run from the package directory."""
import hashlib
import json
import pathlib

ROOT = pathlib.Path(".")
PUBLIC = ["instruction.md", "public/content.json", "public/content_long.json"]
CHECKS = [("REQ-ROLES", "roles"), ("REQ-FEATURES", "features"), ("REQ-COPY", "copy"), ("REQ-FORM", "form"), ("REQ-STATES", "states"), ("REQ-CONTRAST", "contrast")]


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    trusted = ["calibration.md", "rubric.md", "environment/README.md"] + sorted(
        str(path.relative_to(ROOT)) for path in (ROOT / "private").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc"))
    manifest = {
        "schemaVersion": 1, "id": "vis-001-original-landing", "version": "0.3.1", "familyId": "vis-original-frontend", "capability": "aesthetics", "usage": "development",
        "source": {"kind": "original-design", "references": ["https://www.w3.org/TR/WCAG22/", "docs/design/TASK_SET_V2.md"]},
        "license": {"taskText": "Original project-authored task material; no third-party text is copied.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": path, "sha256": digest(path)} for path in PUBLIC], "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": [{"id": requirement, "critical": True, "introducedAt": "vis-001-original-landing 0.3.0", "checkIds": [check]} for requirement, check in CHECKS],
        "toolProfiles": ["workspace-basic"],
        "grader": {"id": "vis001-structure", "version": "1.0.1", "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"]},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
