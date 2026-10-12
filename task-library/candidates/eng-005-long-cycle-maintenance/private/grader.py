#!/usr/bin/env python3
"""Independent checkpoint grader. It ignores candidate-authored tests and checkers."""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

CHECKS = {
    "BASE_CLI": ["base.read", "base.create", "base.update", "base.export"],
    "BASE_DATA": ["data.preserves-seed"],
    "QUERY": ["query.filter", "query.order", "query.pagination", "query.invalid"],
    "DEPENDENCY": ["dependency.self", "dependency.cycle", "dependency.transition", "dependency.prerequisite"],
    "NO_MUTATION": ["failure.no_mutation"],
    "MIGRATION": ["migration.schema", "migration.preserve", "migration.events", "migration.idempotent"],
    "ERRORS_DOCS": ["errors.protocol", "errors.codes", "docs.usage"],
}
ALL_CHECKS = {check: requirement for requirement, ids in CHECKS.items() for check in ids}


def invoke(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    command = ["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/cli.ts", *args]
    try:
        return subprocess.run(command, cwd=root, text=True, encoding="utf-8", errors="replace",
                              capture_output=True, timeout=6, check=False)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or "candidate command timed out"
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return subprocess.CompletedProcess(command, 124, stdout, stderr)


def load_store(root: Path) -> dict:
    return json.loads((root / "data" / "work-orders.json").read_text(encoding="utf-8"))


def clone(root: Path, temp: Path) -> Path:
    temp.mkdir(parents=True, exist_ok=True)
    target = temp / "submission"
    shutil.copytree(root, target, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
    fixture = json.loads((Path(__file__).parent / "base-fixture.json").read_text(encoding="utf-8"))
    (target / "data" / "work-orders.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def base_checks(root: Path) -> dict[str, bool]:
    result = {}
    shown = invoke(root, ["show", "WO-101"])
    try:
        order = json.loads(shown.stdout)
        result["base.read"] = shown.returncode == 0 and order["title"] == "Repair east entrance access reader" and order["description"] == "Card reader intermittently fails"
    except (json.JSONDecodeError, KeyError, TypeError):
        result["base.read"] = False
    created = invoke(root, ["create", "GRADER-NEW", "grader-created"])
    result["base.create"] = created.returncode == 0 and invoke(root, ["show", "GRADER-NEW"]).returncode == 0
    updated = invoke(root, ["update", "WO-101", "--description", "Updated value"])
    try:
        result["base.update"] = updated.returncode == 0 and json.loads(invoke(root, ["show", "WO-101"]).stdout)["description"] == "Updated value"
    except (json.JSONDecodeError, KeyError, TypeError):
        result["base.update"] = False
    try:
        exported = json.loads(invoke(root, ["export", "json"]).stdout)
        result["base.export"] = isinstance(exported, list) and len(exported) >= 4 and exported[1]["description"] == ""
    except (json.JSONDecodeError, KeyError, TypeError):
        result["base.export"] = False
    return result


def query_checks(root: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    try:
        filtered = json.loads(invoke(root, ["list", "--status", "OPEN", "--sort", "createdAt", "--order", "asc", "--page", "1", "--page-size", "10"]).stdout)
        checks["query.filter"] = filtered["total"] == 2 and [row["id"] for row in filtered["items"]] == ["WO-101", "WO-104"]
        ordered = json.loads(invoke(root, ["list", "--sort", "createdAt", "--order", "asc", "--page-size", "10"]).stdout)
        checks["query.order"] = [row["id"] for row in ordered["items"][:2]] == ["WO-101", "WO-102"]
        page = json.loads(invoke(root, ["list", "--sort", "createdAt", "--order", "asc", "--page", "2", "--page-size", "1"]).stdout)
        checks["query.pagination"] = page["total"] == 4 and page["pages"] == 4 and [row["id"] for row in page["items"]] == ["WO-102"]
    except (json.JSONDecodeError, KeyError, TypeError):
        checks.update({"query.filter": False, "query.order": False, "query.pagination": False})
    before = (root / "data" / "work-orders.json").read_bytes()
    invalid = invoke(root, ["list", "--page", "0"])
    checks["query.invalid"] = invalid.returncode != 0 and (root / "data" / "work-orders.json").read_bytes() == before
    return checks


def dependency_checks(root: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    self_result = invoke(root, ["depends", "add", "WO-101", "WO-101"])
    checks["dependency.self"] = self_result.returncode != 0
    first = invoke(root, ["depends", "add", "WO-101", "WO-102"])
    cycle = invoke(root, ["depends", "add", "WO-102", "WO-101"])
    checks["dependency.cycle"] = first.returncode == 0 and cycle.returncode != 0
    invalid_jump = invoke(root, ["update", "WO-101", "--status", "DONE"])
    forward_one = invoke(root, ["update", "WO-101", "--status", "IN_PROGRESS"])
    forward_two = invoke(root, ["update", "WO-101", "--status", "DONE"])
    checks["dependency.transition"] = invalid_jump.returncode != 0 and forward_one.returncode == 0 and forward_two.returncode == 0
    block_root = root
    dep = invoke(block_root, ["depends", "add", "WO-103", "WO-104"])
    blocked = invoke(block_root, ["update", "WO-103", "--status", "DONE"])
    checks["dependency.prerequisite"] = dep.returncode == 0 and blocked.returncode != 0
    return checks


def no_mutation_check(root: Path) -> bool:
    path = root / "data" / "work-orders.json"
    before = path.read_bytes()
    rejected = invoke(root, ["depends", "add", "WO-101", "WO-101"])
    same_self = path.read_bytes() == before
    if invoke(root, ["depends", "add", "WO-101", "WO-102"]).returncode != 0:
        return False
    before_cycle = path.read_bytes()
    cycle = invoke(root, ["depends", "add", "WO-102", "WO-101"])
    same_cycle = path.read_bytes() == before_cycle
    before_transition = path.read_bytes()
    jump = invoke(root, ["update", "WO-101", "--status", "DONE"])
    same_transition = path.read_bytes() == before_transition
    return rejected.returncode != 0 and same_self and cycle.returncode != 0 and same_cycle and jump.returncode != 0 and same_transition


def migration_checks(root: Path, fixture: dict) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    path = root / "data" / "work-orders.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    original = path.read_bytes()
    shown = invoke(root, ["show", "FIX-01"])
    checks["migration.schema"] = shown.returncode == 0 and path.read_bytes() == original
    first = invoke(root, ["update", "FIX-01", "--title", "Updated server room inspection"])
    try:
        state = load_store(root)
        orders = {order["id"]: order for order in state["workOrders"]}
        checks["migration.preserve"] = state["version"] == 2 and len(orders) == len(fixture["workOrders"]) and \
            orders["FIX-01"]["description"] == "" and orders["FIX-02"]["description"] == "Preserve the original value" and \
            orders["FIX-01"]["title"] == "Updated server room inspection"
        events_before = list(state["events"])
        second = invoke(root, ["update", "FIX-02", "--description", "Second successful update"])
        updated = load_store(root)
        migration_events = [event for event in updated["events"] if event["type"] == "state_migrated"]
        sequences = [event["sequence"] for event in updated["events"]]
        event_shape = all(set(event) == {"sequence", "type", "orderId", "at"} and isinstance(event["type"], str) for event in updated["events"])
        checks["migration.events"] = len(updated["events"]) >= 2 and event_shape and sequences == list(range(1, len(sequences) + 1)) and \
            all(event.get("type") for event in events_before)
        checks["migration.idempotent"] = first.returncode == second.returncode == 0 and len(migration_events) == 1
    except (json.JSONDecodeError, KeyError, TypeError):
        checks.update({"migration.preserve": False, "migration.events": False, "migration.idempotent": False})
    return checks


def errors_docs_checks(root: Path) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    unknown = invoke(root, ["not-a-command"])
    try:
        payload = json.loads(unknown.stdout)
        checks["errors.protocol"] = unknown.returncode == 2 and not unknown.stderr.strip() and \
            set(payload) == {"ok", "error"} and payload["ok"] is False and set(payload["error"]) == {"code", "message"} and payload["error"]["code"] == "UNKNOWN_COMMAND"
    except (json.JSONDecodeError, KeyError, TypeError):
        checks["errors.protocol"] = False
    examples = [(["show", "MISSING"], "NOT_FOUND"), (["update", "WO-101", "--status", "DONE"], "INVALID_STATUS_TRANSITION"),
                (["depends", "add", "WO-101", "WO-101"], "SELF_DEPENDENCY"), (["list", "--page", "0"], "INVALID_ARGUMENT")]
    stable = True
    for args, expected in examples:
        first = invoke(root, args)
        second = invoke(root, args)
        try:
            stable &= first.returncode == second.returncode == 2 and json.loads(first.stdout)["error"]["code"] == expected and \
                json.loads(first.stdout)["error"]["code"] == json.loads(second.stdout)["error"]["code"]
        except (json.JSONDecodeError, KeyError, TypeError):
            stable = False
    checks["errors.codes"] = stable
    try:
        text = (root / "README.md").read_text(encoding="utf-8")
        documented_runtime = "node --experimental-strip-types" in text or "node --disable-warning=ExperimentalWarning --experimental-strip-types" in text
        checks["docs.usage"] = documented_runtime and all(term in text for term in ("pagination", "dependencies", "error codes", "version 1", "version 2", "events"))
    except OSError:
        checks["docs.usage"] = False
    return checks


def data_preservation_check(submission: Path, fixture: dict) -> bool:
    try:
        state = load_store(submission)
        current = {order["id"]: order for order in state["workOrders"]}
        for original in fixture["workOrders"]:
            if original["id"] not in current:
                return False
            row = current[original["id"]]
            for key, value in original.items():
                if row.get(key) != value:
                    return False
        return True
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    submission = Path(request["submission"]["directory"])
    active = request["context"]["activeRequirementIds"]
    selected = [check for requirement in active for check in CHECKS.get(requirement, [])]
    preservation_fixture = json.loads((Path(__file__).parent / "base-fixture.json").read_text(encoding="utf-8"))
    outcomes: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="eng005-hidden-") as temp:
        temp_path = Path(temp)
        for group in active:
            group_root = clone(submission, temp_path / group)
            if group == "BASE_CLI": outcomes.update(base_checks(group_root))
            elif group == "BASE_DATA": outcomes["data.preserves-seed"] = data_preservation_check(submission, preservation_fixture)
            elif group == "QUERY": outcomes.update(query_checks(group_root))
            elif group == "DEPENDENCY": outcomes.update(dependency_checks(group_root))
            elif group == "NO_MUTATION": outcomes["failure.no_mutation"] = no_mutation_check(group_root)
            elif group == "MIGRATION":
                fixture = json.loads((Path(__file__).parent / "v1-fixture.json").read_text(encoding="utf-8"))
                migration_root = clone(submission, temp_path / "migration-fixture")
                outcomes.update(migration_checks(migration_root, fixture))
            elif group == "ERRORS_DOCS": outcomes.update(errors_docs_checks(group_root))
    checks = [{"id": check_id, "requirementId": ALL_CHECKS[check_id], "status": "pass" if outcomes.get(check_id, False) else "fail", "evidenceRefs": []}
              for check_id in selected]
    result = {"schemaVersion": 1, "requestId": request["requestId"], "taskId": request["task"]["id"],
              "taskVersion": request["task"]["version"], "graderVersion": "1.0.1", "gradingStatus": "completed",
              "checks": checks, "dimensions": [], "unscoredCheckIds": [], "reason": None, "error": None}
    args.result.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
