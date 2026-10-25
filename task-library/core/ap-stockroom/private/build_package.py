#!/usr/bin/env python3
"""Builds the AP stockroom package: ten dev items (seeds), their anchors (the myopic and the tuned strong policy's
profits on the item's own draws) and hindsight bounds, and the manifest. Usage: python3 private/build_package.py
(from the package directory). Deterministic: the same seeds give the same items, anchors and manifest."""
import hashlib
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(".")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grader  # noqa: E402
import policies  # noqa: E402
import stockroom as sr  # noqa: E402

SEEDS = {f"store-{index:02d}": f"ap-2026-10:{index}" for index in range(1, 11)}
SIMULATOR_DESCRIPTION = ("The stockroom simulator (see public/RULES.md). command: \"observe\" | \"order\" | \"advance\" | \"day\" | \"result\"; "
                         "for \"order\", arguments {\"product\": name, \"supplier\": \"local\" | \"import\", \"quantity\": integer, \"ref\": unique string}. "
                         "\"day\" takes {\"orders\": [order arguments, ...]}, places them and ends the day in one call. "
                         "Returns a JSON reply. \"advance\" and \"day\" end the current day and return the next morning's compact view.")


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    catalogue = {}
    # Anchors depend only on the scenario and the policies; an unchanged seed keeps its computed anchors (0.2.0 changed
    # only how the model talks to the simulator).
    known = json.loads((HERE / "items.json").read_text(encoding="utf-8")) if (HERE / "items.json").exists() else {}
    for item_id, seed in SEEDS.items():
        found = {key: value for key, value in known[item_id].items() if key != "seed"} if known.get(item_id, {}).get("seed") == seed else policies.anchors(seed)
        catalogue[item_id] = {"seed": seed, **found}
        print(item_id, json.dumps(found), file=sys.stderr, flush=True)
    (HERE / "items.json").write_text(json.dumps(catalogue, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    items = []
    for item_id, entry in catalogue.items():
        path = f"items/{item_id}/prompt.md"
        (ROOT / path).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / path).write_text(f"## Store {item_id}\n\nStart with `observe`.\n", encoding="utf-8")
        items.append({"id": item_id, "level": "stockroom", "files": [{"path": path, "sha256": digest(path)}],
                      "activeRequirementIds": ["REQ-COMPLETED", "REQ-NO-INVALID", "REQ-NO-DUPLICATES", "REQ-NO-OVERFLOW"],
                      "split": "dev", "structure": "env:stockroom",
                      "provenance": {"source": f"project simulator private/stockroom.py, seed {entry['seed']}", "published": "2026-10-24",
                                     "license": "project-authored", "exposure": "generated"},
                      "anchors": {"profit": {"myopic": entry["myopic"], "strong": entry["strong"]}}})
    trusted = ["calibration.md", "card.md", "rubric.md", "private/build_package.py", "private/grader.py", "private/items.json", "private/policies.py",
               "private/stockroom.py"]
    requirements = [{"id": requirement, "critical": requirement == "REQ-COMPLETED", "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}", "checkIds": [check]}
                    for check, requirement in grader.REQUIREMENTS.items()]
    manifest = {
        "schemaVersion": 2, "id": grader.TASK_ID, "version": grader.TASK_VERSION, "familyId": "ap-stockroom", "capability": "tool", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/v2/TASK_LIBRARY.md"]},
        "license": {"taskText": "Original project-authored simulator, rules and policies.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}, {"path": "public/RULES.md", "sha256": digest("public/RULES.md")}],
                  "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": requirements,
        "tier": "core", "capabilities": ["agentic"], "card": "card.md",
        "scoreModel": {
            "primary": {"kind": "metric", "metric": "profit"},
            "groups": [{"id": "run", "weight": 1, "critical": True, "rule": "all", "checkIds": ["completed"]},
                       {"id": "discipline", "weight": 0.5, "critical": False, "rule": "fraction", "checkIds": ["no-invalid-actions", "no-duplicate-orders", "no-overflow"]},
                       {"id": "profit", "weight": 1, "critical": False, "rule": "metric", "checkIds": [], "metric": "profit"}],
            "metrics": [{"id": "profit", "unit": "money", "direction": "higher",
                         "anchors": {"version": "1", "points": [{"name": "myopic", "maps": 0}, {"name": "strong", "maps": 1}]}},
                        {"id": "bound", "unit": "money", "direction": "higher"}, {"id": "regret", "unit": "money", "direction": "lower"}],
        },
        "items": items,
        "toolProfiles": ["workspace-simulator"],
        "simulator": {"entryPoint": "private/stockroom.py", "executable": "python3", "description": SIMULATOR_DESCRIPTION, "timeoutMs": 30000},
        "grader": {"id": "ap-stockroom-replay", "version": grader.GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"]},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
