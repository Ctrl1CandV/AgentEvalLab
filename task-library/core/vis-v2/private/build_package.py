#!/usr/bin/env python3
"""Builds the VIS v2 package: the eight briefs' items (prompt and content), the anchor pages' content scripts, and the
manifest. Usage: python3 task-library/core/vis-v2/private/build_package.py (from any directory). Deterministic."""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import briefs  # noqa: E402
import grader  # noqa: E402


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    briefs.main()
    checks = briefs.COMMON_CHECKS + [check for brief in briefs.CHECKS.values() for check in brief if check not in briefs.COMMON_CHECKS]
    checks = list(dict.fromkeys(checks))
    items = []
    for brief, own in briefs.CHECKS.items():
        files = [f"items/{brief}/prompt.md", f"items/{brief}/public/content.json"]
        items.append({"id": brief, "level": "brief", "files": [{"path": path, "sha256": digest(path)} for path in files],
                      "activeRequirementIds": [grader.requirement(check) for check in briefs.COMMON_CHECKS + own],
                      "split": briefs.SPLITS[brief], "structure": f"brief:{brief}",
                      "provenance": {"source": "project-authored brief (private/briefs.py)", "published": "2026-10-25", "license": "project-authored",
                                     "exposure": "private-to-runs"}})
    trusted = ["calibration.md", "card.md", "rubric.md", "private/briefs.py", "private/build_package.py", "private/calibrate.py", "private/grader.py",
               "private/scenarios.mjs", "private/judge/SKILL.md", "private/anchors/plain.css"]
    trusted += sorted(str(path.relative_to(ROOT)) for path in (ROOT / "private" / "anchors").glob("*/*") if path.is_file())
    behaviour = [check for check in checks if check not in briefs.COMMON_CHECKS]
    manifest = {
        "schemaVersion": 2, "id": grader.TASK_ID, "version": grader.TASK_VERSION, "familyId": "vis-v2", "capability": "aesthetics", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/v2/TASK_LIBRARY.md", "https://www.w3.org/TR/WCAG22/"]},
        "license": {"taskText": "Original project-authored briefs, content, anchor pages and checks.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}],
                  "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": [{"id": grader.requirement(check), "critical": True, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}", "checkIds": [check]}
                         for check in checks],
        "tier": "core", "capabilities": ["visual"], "card": "card.md",
        "scoreModel": {
            "primary": {"kind": "rating"},
            "groups": [{"id": "basics", "weight": 1, "critical": True, "rule": "all", "checkIds": list(briefs.COMMON_CHECKS)},
                       {"id": "behaviour", "weight": 2, "critical": True, "rule": "fraction", "checkIds": behaviour}],
            "metrics": [{"id": "checksPassed", "unit": "checks", "direction": "higher"}, {"id": "checks", "unit": "checks", "direction": "higher"}],
        },
        "items": items,
        "toolProfiles": ["workspace-augmented"],
        "grader": {"id": "vis-v2-functional", "version": grader.GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"]},
        "environment": {"runtime": "Python 3.13 and Node 22", "dependencies": "playwright-core and its headless Chromium shell (the repository's renderer); no network",
                        "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
