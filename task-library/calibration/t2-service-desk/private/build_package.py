#!/usr/bin/env python3
"""Builds the T2 package: one item per ticket, each with the desk tool, the policy and the starting data, and the
manifest with every file hash. Usage: python3 private/build_package.py (run from the package directory)."""
import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(".")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import importlib  # noqa: E402
import makegood  # noqa: E402
import tickets  # noqa: E402


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def visible(path):
    return path.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in path.parts) and not path.name.endswith(".pyc")


def generate_makegood():
    """Write the optimisation tickets, their catalogue, customers and orders, and reload the modules that read them."""
    global tickets, grader
    products, customers, orders, generated = makegood.generate(tickets.MAKEGOOD_SEED, tickets.BASE_DB)
    (HERE / "makegood.json").write_text(json.dumps({"seed": tickets.MAKEGOOD_SEED, "rates": makegood.RATES, "products": products,
                                                    "customers": customers, "orders": orders, "tickets": generated},
                                                   indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tickets = importlib.reload(tickets)
    grader = importlib.import_module("grader")
    grader = importlib.reload(grader)


def main():
    generate_makegood()
    if (ROOT / "items").exists():
        shutil.rmtree(ROOT / "items")
    requirements, items = {}, []
    for ticket_id in [*tickets.TICKETS, *tickets.MAKEGOOD]:
        public = ROOT / "items" / ticket_id / "public"
        (public / "data").mkdir(parents=True)
        shutil.copy(HERE / "desk.py", public / "desk.py")
        shutil.copy(HERE / "POLICY.md", public / "POLICY.md")
        (public / "data" / "db.json").write_text(json.dumps(tickets.BASE_DB, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        (public / "data" / "audit.log").write_text("", encoding="utf-8")
        (ROOT / "items" / ticket_id / "prompt.md").write_text(tickets.prompt(ticket_id), encoding="utf-8")
        ids = []
        for name in grader.check_names(ticket_id):
            requirement = grader.requirement(ticket_id, name)
            requirements[requirement] = {"id": requirement, "critical": True, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}",
                                         "checkIds": [f"{ticket_id}-{name}"]}
            ids.append(requirement)
        files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "items" / ticket_id).rglob("*") if visible(path))
        level = tickets.MAKEGOOD[ticket_id]["level"] if ticket_id in tickets.MAKEGOOD else ticket_id
        items.append({"id": ticket_id, "level": level, "files": [{"path": path, "sha256": digest(path)} for path in files],
                      "activeRequirementIds": ids + ["REQ-FORMAT"]})
    requirements["REQ-FORMAT"] = {"id": "REQ-FORMAT", "critical": False, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}", "checkIds": ["answer-format"]}
    trusted = ["calibration.md", "rubric.md"] + sorted(str(path.relative_to(ROOT)) for path in (ROOT / "private").rglob("*") if visible(path))
    manifest = {
        "schemaVersion": 1, "id": grader.TASK_ID, "version": grader.TASK_VERSION, "familyId": "t2-service-desk", "capability": "tool", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md", "tau-bench (Yao et al., 2024), as a model of the task form"]},
        "license": {"taskText": "Original project-authored policy, data, tool and tickets.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}], "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": list(requirements.values()),
        "scoring": {"formatCheckId": "answer-format", "formatPenalty": 0.2},
        "items": items, "toolProfiles": ["workspace-basic"],
        "grader": {"id": "t2-desk-state", "version": grader.GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"], "answerSource": "execution-output"},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
