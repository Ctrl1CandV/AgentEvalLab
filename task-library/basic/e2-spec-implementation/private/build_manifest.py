#!/usr/bin/env python3
"""Writes the E2 manifest: items, requirements from each item's fixture groups, and every file hash."""
import hashlib
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(".")
ITEMS = {"sheet": "sheet", "ledger": "ledger", "recur": "recur", "query": "query", "routes": "routes"}
VERSION, GRADER_VERSION = "0.6.0", "2.0.0"
# Manifest v2 (PLAN-007 WP2.2). Each item is its own task and structure group, all dev. sheet, ledger, recur and query
# are contract items (basic): one critical group each. routes is the open-ended bridge: headlined by routeShare, the
# mean share of the way from the baseline's cost to the best known cost over its eight hidden instances (anchors at 0
# and 1 of that scale, uncapped); valid when it solves at least one instance (`routes-feasible`, critical); its rungs
# are labels in a non-critical group. The README is a diagnostic for every item (grader 1.7.0), never critical.
PUBLISHED = "2026-10-20"


def score_model(checks):
    groups = [{"id": item, "weight": 1, "critical": item != "routes", "rule": "fraction",
               "checkIds": [f"{item}-{check}" for check in checks[item] if check != "feasible"]} for item in ITEMS]
    groups.append({"id": "routes-valid", "weight": 1, "critical": True, "rule": "all", "checkIds": ["routes-feasible"]})
    groups.append({"id": "readme", "weight": 0.1, "critical": False, "rule": "all", "checkIds": ["readme"]})
    groups.append({"id": "routes-share", "weight": 1, "critical": False, "rule": "metric", "checkIds": [], "metric": "routeShare", "items": ["routes"]})
    return {
        "primary": {"kind": "resolved"},
        "primaryByItem": {"routes": {"kind": "metric", "metric": "routeShare"}},
        "groups": groups,
        "metrics": [{"id": "routeShare", "unit": "mean share of the way from baseline to best known", "direction": "higher", "items": ["routes"],
                     "anchors": {"version": "1", "points": [{"name": "baseline", "maps": 0}, {"name": "best-known", "maps": 1}]}},
                    {"id": "routeCost", "unit": "total route length", "direction": "lower", "items": ["routes"]},
                    {"id": "feasibleInstances", "unit": "of 8 instances", "direction": "higher", "items": ["routes"]},
                    {"id": "gradingLoad", "unit": "highest 1-minute load per core while graded", "direction": "lower", "items": ["routes"]}],
    }


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def checks_of(item):
    spec = importlib.util.spec_from_file_location(f"{item}_fixtures", ROOT / "private" / item / "fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return sorted({check for check, *_ in module.FIXTURES})


def routes_public():
    """The routes item's public samples and their baseline and best-known costs."""
    import sys
    sys.path.insert(0, str(ROOT / "private" / "routes"))
    import instances
    anchors = json.loads((ROOT / "private" / "routes" / "anchors.json").read_text(encoding="utf-8"))
    samples = ROOT / "items" / "routes" / "public" / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    for name in instances.SAMPLES:
        (samples / f"{name}.json").write_text(json.dumps(instances.instance(name), indent=1) + "\n", encoding="utf-8")
    costs = {name: {"baseline": round(anchors[name]["baseline"], 3), "best": round(anchors[name]["best"], 3)} for name in instances.SAMPLES}
    (samples / "costs.json").write_text(json.dumps(costs, indent=1) + "\n", encoding="utf-8")


def main():
    routes_public()
    trusted = ["calibration.md", "card.md", "rubric.md"] + sorted(str(path.relative_to(ROOT)) for path in (ROOT / "private").rglob("*")
                                                     if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc")
                                                     and not any(part.startswith(".") for part in path.parts))
    requirements, items, checks = [], [], {}
    for item, level in ITEMS.items():
        checks[item] = checks_of(item)
        ids = [f"REQ-{item.upper()}-{check.upper()}" for check in checks_of(item)]
        requirements += [{"id": requirement, "critical": True, "introducedAt": f"e2-spec-implementation {VERSION}", "checkIds": [f"{item}-{check}"]}
                         for requirement, check in zip(ids, checks_of(item))]
        files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "items" / item).rglob("*") if path.is_file() and not any(part.startswith(".") for part in path.parts))
        items.append({"id": item, "level": level, "files": [{"path": path, "sha256": digest(path)} for path in files], "activeRequirementIds": ids + ["REQ-README"],
                      "split": "dev", "structure": f"item:{item}",
                      "provenance": {"source": "project-authored specification, reference and fixtures (private/build_manifest.py)",
                                     "published": PUBLISHED, "license": "project-authored", "exposure": "private-to-runs"},
                      **({"anchors": {"routeShare": {"baseline": 0, "best-known": 1}}} if item == "routes" else {})})
    requirements.append({"id": "REQ-README", "critical": True, "introducedAt": f"e2-spec-implementation {VERSION}", "checkIds": ["readme"]})
    manifest = {
        "schemaVersion": 2, "id": "e2-spec-implementation", "version": VERSION, "familyId": "e2-spec-implementation", "capability": "engineering", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md"]},
        "license": {"taskText": "Original project-authored specifications, references and fixtures.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}], "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": requirements,
        "tier": "basic", "capabilities": ["engineering"], "card": "card.md", "scoreModel": score_model(checks),
        "items": items, "toolProfiles": ["workspace-basic"],
        "grader": {"id": "e2-fixtures", "version": GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"]},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
