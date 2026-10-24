#!/usr/bin/env python3
"""Builds the T2 finance desk package: the close days (days.json), one item per day with the ledger tool, the manual and
the books, and the manifest. Usage: python3 private/build_package.py [--reuse-days] (from the package directory).
--reuse-days keeps private/days.json as it is (the days and their best plans known) and rebuilds the items and the
manifest from it: for a grader change that leaves the task unchanged."""
import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(".")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import finance  # noqa: E402

# Manifest v2 (PLAN-007 WP2.2): resolved means every request handled and the day consistent (both critical groups);
# the payment plan's rungs are a diagnostic group, about a quarter of the diagnostic. The four days share one generator
# template, so they are one structure group; all are dev (a basic family has no other split).
GROUP_WEIGHTS = {"requests": 2, "day": 1, "plan": 1}
STRUCTURE = "generator:finance-day"
PUBLISHED = "2026-10-23"
DAYS = {"fn1": "t2-finance-2026-10:fn1", "fn2": "t2-finance-2026-10:fn2", "fn3": "t2-finance-2026-10:fn3", "fn4": "t2-finance-2026-10:fn4"}


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def visible(path):
    return path.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in path.parts) and not path.name.endswith(".pyc")


def main():
    if "--reuse-days" in sys.argv[1:]:
        days = json.loads((HERE / "days.json").read_text(encoding="utf-8"))
        if {item_id: day["seed"] for item_id, day in days.items()} != DAYS:
            raise SystemExit("days.json was built from other seeds; rebuild without --reuse-days")
    else:
        days = {}
        for item_id, seed in DAYS.items():
            books, requests, effects = finance.build(seed)
            problem = finance.PlanProblem(books)
            value, slots = finance.best_plan(problem)
            days[item_id] = {"seed": seed, "books": books, "requests": requests, "effects": effects, "prompt": finance.prompt(item_id, requests),
                             "plan_best": {"signature": problem.signature(), "value": value, "slots": slots}}
        (HERE / "days.json").write_text(json.dumps(days, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    import grader
    grader.DAYS = grader.load_days()
    grader.known_plans(grader.DAYS)
    if (ROOT / "items").exists():
        shutil.rmtree(ROOT / "items")
    requirements, items, groups = {}, [], {"requests": [], "day": [], "plan": []}
    for item_id, day in days.items():
        public = ROOT / "items" / item_id / "public"
        (public / "data").mkdir(parents=True)
        shutil.copy(HERE / "ledger.py", public / "ledger.py")
        shutil.copy(HERE / "MANUAL.md", public / "MANUAL.md")
        (public / "data" / "books.json").write_text(json.dumps(day["books"], indent=1, sort_keys=True) + "\n", encoding="utf-8")
        (public / "data" / "audit.log").write_text("", encoding="utf-8")
        (ROOT / "items" / item_id / "prompt.md").write_text(day["prompt"], encoding="utf-8")
        ids = []
        for name in grader.check_names(item_id):
            requirement = grader.requirement(item_id, name)
            requirements[requirement] = {"id": requirement, "critical": True, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}",
                                         "checkIds": [f"{item_id}-{name}"]}
            ids.append(requirement)
            groups["plan" if "-plan-" in name else "day" if name in finance.DAY_CHECKS else "requests"].append(f"{item_id}-{name}")
        files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "items" / item_id).rglob("*") if visible(path))
        items.append({"id": item_id, "level": "close", "files": [{"path": path, "sha256": digest(path)} for path in files],
                      "activeRequirementIds": ids + ["REQ-FORMAT"], "split": "dev", "structure": STRUCTURE,
                      "provenance": {"source": f"project generator private/finance.py, seed {day['seed']}", "published": PUBLISHED,
                                     "license": "project-authored", "exposure": "generated"}})
    requirements["REQ-FORMAT"] = {"id": "REQ-FORMAT", "critical": False, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}", "checkIds": ["answer-format"]}
    trusted = ["calibration.md", "card.md", "rubric.md"] + sorted(str(path.relative_to(ROOT)) for path in (ROOT / "private").rglob("*") if visible(path))
    manifest = {
        "schemaVersion": 2, "id": grader.TASK_ID, "version": grader.TASK_VERSION, "familyId": "t2-service-desk", "capability": "tool", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md", "tau-bench (Yao et al., 2024) and tau2-bench (Barres et al., 2025), as models of the task form"]},
        "license": {"taskText": "Original project-authored manual, books, tool and requests.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}], "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": list(requirements.values()),
        "tier": "basic", "capabilities": ["agentic"], "card": "card.md",
        "scoreModel": {
            "primary": {"kind": "resolved"},
            "groups": [{"id": group, "weight": GROUP_WEIGHTS[group], "critical": group != "plan", "rule": "fraction", "checkIds": checks}
                       for group, checks in groups.items()],
            "format": {"checkId": "answer-format", "penalty": 0.2},
        },
        "items": items, "toolProfiles": ["workspace-basic"],
        "grader": {"id": "t2-finance-ledger", "version": grader.GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"], "answerSource": "execution-output"},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
