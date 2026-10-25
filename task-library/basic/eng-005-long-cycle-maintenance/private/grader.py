#!/usr/bin/env python3
"""Independent checkpoint grader. It ignores candidate-authored tests and checkers.

Version 2.0.0 adds hidden checks for behaviour the stage briefs state but the public checkers do not exercise: sort
ties under descending order, defaults, empty results, every rejected list option, duplicate and unknown dependencies,
longer cycles, backward transitions, several prerequisites, atomicity of every rejected dependency or status change,
read-only commands and event details after migration, and every listed error code with clean output.

Version 2.1.0 (task 0.4.0) adds S6, scale (private/scale.py), and makes the untouched baseline earn nothing: the base
and seed checks guard against regressions, so they count only when some check of a stage's own requirement passes,
and the checks that a command is rejected also need the command to work where it should.

Version 2.2.0 (task 0.5.0) adds S7, planning (private/plan.py): valid plans on five hidden stores and the S6 scale
store, read-only planning, error codes, the new fields kept by earlier commands, and a quality ladder on the mean
place of the plans between the naive plan (0), the greedy plan (0.5) and the best plan known (1).

Version 2.3.0 (task 0.5.0 unchanged) stops wall-clock limits from failing correct deliveries on a busy machine: the
PLAN-007 success audit found plan.fields-preserved failing once and passing on two re-gradings of the same snapshot.
Commands that no brief bounds in time get 30 seconds instead of 6, a command whose sandbox could not be prepared is
started once more, and the plan's limit of 10 seconds on one CPU core (S7) is measured as the command's CPU time, with
30 seconds of wall time as a hard stop. The speed rungs of S6 still compare wall time with the reference, best of three.

Version 2.4.0 (task 0.5.0 unchanged; manifest v2, PLAN-007 WP2.2) times S6 by CPU time: the scale workload's time is the
CPU time (user and system) of every command it starts, the candidate's and the reference's alike, so a busy machine does
not move the speed rungs (PROTOCOL §9; `--noise` runs the noise test). It reports grader result v2 with raw values: the
CPU-time ratio to the reference (`scaleSpeedRatio`, when measured) and the plans' mean place on the quality scale
(`planQuality`, when computed); the rungs of both are labels.

Version 2.5.0 (task 0.5.0 unchanged; user decision before PLAN-007 Phase 4): speed is no longer scored. The speed rungs
are still measured and reported as labels with `scaleSpeedRatio`, but they belong to no score group; the diagnostic
weighs completion (the correctness checks) and quality (the plan ladder) equally. The checks themselves are unchanged.
"""
import os
import resource
import argparse
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKS = {
    "BASE_CLI": ["base.read", "base.create", "base.update", "base.export"],
    "BASE_DATA": ["data.preserves-seed"],
    "QUERY": ["query.filter", "query.order", "query.pagination", "query.invalid", "query.defaults", "query.desc-ties", "query.sort-keys",
              "query.empty-result", "query.page-size-bounds", "query.rejects-malformed"],
    "DEPENDENCY": ["dependency.self", "dependency.cycle", "dependency.transition", "dependency.prerequisite", "dependency.duplicate",
                   "dependency.unknown", "dependency.transitive-cycle", "dependency.backward", "dependency.all-prerequisites"],
    "NO_MUTATION": ["failure.no_mutation", "failure.no_mutation-prerequisite", "failure.no_mutation-dependency"],
    "MIGRATION": ["migration.schema", "migration.preserve", "migration.events", "migration.idempotent", "migration.read-only",
                  "migration.event-details", "migration.failed-no-write", "migration.cli-shape"],
    "ERRORS_DOCS": ["errors.protocol", "errors.codes", "docs.usage", "errors.codes-all", "errors.store-invalid", "errors.clean-output"],
    "SCALE": ["scale.list", "scale.dependencies", "scale.status"],
    # The speed rungs are a ladder against the reference, not acceptance, so their requirement is not critical.
    "SCALE_SPEED": ["scale.speed-3", "scale.speed-1.5", "scale.speed-1.1", "scale.speed-0.75"],
    "PLAN": ["plan.valid-small", "plan.valid-large", "plan.valid-scale", "plan.read-only", "plan.errors", "plan.fields-preserved"],
    # The quality rungs place plans between the naive, the greedy and the best known plan; like the speed rungs, a ladder.
    "PLAN_QUALITY": ["plan.quality-25", "plan.quality-50", "plan.quality-65", "plan.quality-80", "plan.quality-90", "plan.quality-97"],
}
PLAN_SECONDS = 10
GUARDS = {"BASE_CLI", "BASE_DATA"}
SCALE_SEED = "eng005-scale-hidden"
SPEED_LADDER = (("3", 3.0), ("1.5", 1.5), ("1.1", 1.1), ("0.75", 0.75))
ALL_CHECKS = {check: requirement for requirement, ids in CHECKS.items() for check in ids}
SANDBOX_LAUNCHER = None  # set from the grader request in main
GRADER_VERSION = "2.5.0"
RAW: dict[str, float] = {}  # raw values measured during this grading (grader result v2)


def sandboxed(command: list[str], root: Path) -> list[str]:
    """Prefix candidate commands with the harness sandbox launcher when the request supplies one."""
    return [sys.executable, SANDBOX_LAUNCHER, "--rw", str(root), "--", *command] if SANDBOX_LAUNCHER else command


COMMAND_SECONDS = 30  # a hard stop for commands no brief bounds in time; never a verdict on speed
SANDBOX_SETUP_FAILED = 125  # scripts/sandbox_exec.py: the sandbox could not be prepared, so the command never ran


def invoke(root: Path, args: list[str], timeout: float = COMMAND_SECONDS) -> subprocess.CompletedProcess[str]:
    command = ["node", "--disable-warning=ExperimentalWarning", "--experimental-strip-types", "src/cli.ts", *args]
    try:
        result = subprocess.run(sandboxed(command, root), cwd=root, text=True, encoding="utf-8", errors="replace",
                                capture_output=True, timeout=timeout, check=False)
        if result.returncode == SANDBOX_SETUP_FAILED and SANDBOX_LAUNCHER:
            # The command never started, so running it again cannot apply anything twice.
            result = subprocess.run(sandboxed(command, root), cwd=root, text=True, encoding="utf-8", errors="replace",
                                    capture_output=True, timeout=timeout, check=False)
        return result
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or "candidate command timed out"
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return subprocess.CompletedProcess(command, 124, stdout, stderr)


def invoke_cpu(root: Path, args: list[str], limit: float) -> tuple[subprocess.CompletedProcess[str], float]:
    """Runs a command and returns it with the CPU time it and its descendants used (S7's limit is on one core, so CPU
    time, not wall time, is what the brief bounds). A command over the limit counts as exit 124."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = invoke(root, args, timeout=COMMAND_SECONDS)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    seconds = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    if result.returncode == 0 and seconds > limit:
        result = subprocess.CompletedProcess(result.args, 124, result.stdout, f"over {limit} CPU seconds ({seconds:.2f})")
    return result, seconds


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
    first = invoke(root, ["depends", "add", "WO-101", "WO-102"])
    # A rejection counts only from a command that works: an unimplemented command is rejected too.
    checks["dependency.self"] = self_result.returncode != 0 and first.returncode == 0
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
    unchanged = shown.returncode == 0 and path.read_bytes() == original
    first = invoke(root, ["update", "FIX-01", "--title", "Updated server room inspection"])
    try:
        # A read keeps version 1; the first write migrates to version 2.
        checks["migration.schema"] = unchanged and first.returncode == 0 and load_store(root).get("version") == 2
    except (json.JSONDecodeError, OSError, AttributeError):
        checks["migration.schema"] = False
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


def ids(result: subprocess.CompletedProcess[str]) -> list[str] | None:
    try:
        return [row["id"] for row in json.loads(result.stdout)["items"]]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def rejected_unchanged(root: Path, args: list[str]) -> bool:
    """The command fails and leaves the state file byte for byte as it was."""
    path = root / "data" / "work-orders.json"
    before = path.read_bytes()
    return invoke(root, args).returncode != 0 and path.read_bytes() == before


def query_hidden_checks(root: Path) -> dict[str, bool]:
    """S1: defaults, ties broken by id ascending in both orders, every sort key, empty results, page-size bounds, rejections."""
    checks: dict[str, bool] = {}
    try:
        default = json.loads(invoke(root, ["list"]).stdout)
        checks["query.defaults"] = default["total"] == 4 and default["page"] == 1 and default["pageSize"] == 2 and default["pages"] == 2 and \
            [row["id"] for row in default["items"]] == ["WO-101", "WO-102"]
    except (json.JSONDecodeError, KeyError, TypeError):
        checks["query.defaults"] = False
    checks["query.desc-ties"] = ids(invoke(root, ["list", "--sort", "createdAt", "--order", "desc", "--page-size", "10"])) == ["WO-104", "WO-103", "WO-101", "WO-102"]
    checks["query.sort-keys"] = ids(invoke(root, ["list", "--sort", "title", "--page-size", "10"])) == ["WO-104", "WO-102", "WO-101", "WO-103"] and \
        ids(invoke(root, ["list", "--sort", "id", "--order", "desc", "--page-size", "10"])) == ["WO-104", "WO-103", "WO-102", "WO-101"]
    hundred = ids(invoke(root, ["list", "--page-size", "100"]))
    checks["query.page-size-bounds"] = hundred is not None and len(hundred) == 4 and rejected_unchanged(root, ["list", "--page-size", "101"]) and \
        rejected_unchanged(root, ["list", "--page-size", "0"])
    malformed = [["--page", "1.5"], ["--page", "abc"], ["--page", "-1"], ["--page-size", "2x"], ["--foo", "bar"], ["--status", "BLOCKED"],
                 ["--sort", "priority"], ["--order", "up"]]
    checks["query.rejects-malformed"] = all(rejected_unchanged(root, ["list", *option]) for option in malformed)
    # An empty result keeps the shape: write the seed without its only DONE order, then filter by DONE.
    path = root / "data" / "work-orders.json"
    store = json.loads(path.read_text(encoding="utf-8"))
    store["workOrders"] = [order for order in store["workOrders"] if order["status"] != "DONE"]
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        full = json.loads(invoke(root, ["list", "--page-size", "10"]).stdout)
        empty = json.loads(invoke(root, ["list", "--status", "DONE", "--page-size", "10"]).stdout)
        checks["query.empty-result"] = set(empty) == set(full) >= {"total", "page", "pageSize", "pages", "items"} and empty["total"] == 0 and \
            empty["items"] == [] and empty["page"] == 1 and empty["pageSize"] == 10
    except (json.JSONDecodeError, KeyError, TypeError):
        checks["query.empty-result"] = False
    return checks


def dependency_hidden_checks(temp: Path, submission: Path) -> dict[str, bool]:
    """S2: duplicates, unknown orders, longer cycles, no backward or skipped moves, and every prerequisite done."""
    checks: dict[str, bool] = {}
    root = clone(submission, temp / "duplicate")
    checks["dependency.duplicate"] = invoke(root, ["depends", "add", "WO-103", "WO-104"]).returncode == 0 and \
        invoke(root, ["depends", "add", "WO-103", "WO-104"]).returncode != 0
    root = clone(submission, temp / "unknown")
    checks["dependency.unknown"] = invoke(root, ["depends", "add", "WO-103", "WO-999"]).returncode != 0 and \
        invoke(root, ["depends", "add", "WO-999", "WO-103"]).returncode != 0 and invoke(root, ["depends", "add", "WO-103", "WO-104"]).returncode == 0
    root = clone(submission, temp / "transitive")
    checks["dependency.transitive-cycle"] = invoke(root, ["depends", "add", "WO-103", "WO-104"]).returncode == 0 and \
        invoke(root, ["depends", "add", "WO-104", "WO-101"]).returncode == 0 and invoke(root, ["depends", "add", "WO-101", "WO-103"]).returncode != 0
    root = clone(submission, temp / "backward")
    checks["dependency.backward"] = invoke(root, ["update", "WO-102", "--status", "IN_PROGRESS"]).returncode != 0 and \
        invoke(root, ["update", "WO-102", "--status", "OPEN"]).returncode != 0 and invoke(root, ["update", "WO-103", "--status", "OPEN"]).returncode != 0
    root = clone(submission, temp / "prerequisites")
    added = invoke(root, ["depends", "add", "WO-103", "WO-102"]).returncode == 0 and invoke(root, ["depends", "add", "WO-103", "WO-104"]).returncode == 0
    blocked = invoke(root, ["update", "WO-103", "--status", "DONE"]).returncode != 0
    finished = invoke(root, ["update", "WO-104", "--status", "IN_PROGRESS"]).returncode == 0 and \
        invoke(root, ["update", "WO-104", "--status", "DONE"]).returncode == 0
    checks["dependency.all-prerequisites"] = added and blocked and finished and invoke(root, ["update", "WO-103", "--status", "DONE"]).returncode == 0
    return checks


def no_mutation_hidden_checks(temp: Path, submission: Path) -> dict[str, bool]:
    """S3: a blocked completion, a duplicate or unknown dependency, and a longer cycle leave the file byte for byte unchanged."""
    root = clone(submission, temp / "no-mutation-prerequisite")
    prerequisite = invoke(root, ["depends", "add", "WO-103", "WO-104"]).returncode == 0 and \
        rejected_unchanged(root, ["update", "WO-103", "--status", "DONE"])
    root = clone(submission, temp / "no-mutation-dependency")
    dependency = invoke(root, ["depends", "add", "WO-103", "WO-104"]).returncode == 0 and \
        rejected_unchanged(root, ["depends", "add", "WO-103", "WO-104"]) and rejected_unchanged(root, ["depends", "add", "WO-101", "WO-999"]) and \
        invoke(root, ["depends", "add", "WO-104", "WO-101"]).returncode == 0 and rejected_unchanged(root, ["depends", "add", "WO-101", "WO-103"])
    return {"failure.no_mutation-prerequisite": prerequisite, "failure.no_mutation-dependency": dependency}


def iso_timestamp(value) -> bool:
    try:
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (AttributeError, ValueError):
        return False


def migration_hidden_checks(root: Path, fixture: dict) -> dict[str, bool]:
    """S4: read-only commands keep a version 1 file, events name their order, failures write nothing, the CLI keeps its shape."""
    checks: dict[str, bool] = {}
    path = root / "data" / "work-orders.json"
    path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    original = path.read_bytes()
    reads = [invoke(root, args) for args in (["list"], ["show", "FIX-02"], ["export", "json"])]
    checks["migration.read-only"] = all(result.returncode == 0 for result in reads) and path.read_bytes() == original and \
        rejected_unchanged(root, ["list", "--page", "0"])
    try:
        created = invoke(root, ["create", "MIG-NEW", "Migrated create"])
        first = invoke(root, ["update", "FIX-02", "--title", "First update"])
        second = invoke(root, ["update", "FIX-02", "--title", "Second update"])
        events = load_store(root)["events"]
        migrated = [event for event in events if event["type"] == "state_migrated"]
        checks["migration.event-details"] = created.returncode == first.returncode == second.returncode == 0 and len(events) == 4 and \
            len(migrated) == 1 and migrated[0]["orderId"] is None and [event["orderId"] for event in events[1:]] == ["MIG-NEW", "FIX-02", "FIX-02"] and \
            events[2]["type"] == events[3]["type"] and all(iso_timestamp(event["at"]) for event in events)
    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        checks["migration.event-details"] = False
    checks["migration.failed-no-write"] = rejected_unchanged(root, ["depends", "add", "FIX-01", "FIX-01"]) and \
        rejected_unchanged(root, ["update", "FIX-01", "--status", "DONE"])
    try:
        exported = json.loads(invoke(root, ["export", "json"]).stdout)
        listed = json.loads(invoke(root, ["list", "--page-size", "10"]).stdout)
        rows = {row["id"]: row for row in exported}
        checks["migration.cli-shape"] = isinstance(exported, list) and set(rows) == {"FIX-01", "FIX-02", "MIG-NEW"} and \
            rows["FIX-01"]["description"] == "" and listed["total"] == 3 and len(listed["items"]) == 3
    except (json.JSONDecodeError, KeyError, TypeError):
        checks["migration.cli-shape"] = False
    return checks


def error_payload(result: subprocess.CompletedProcess[str]) -> str | None:
    """The error code of a failed command that printed exactly one JSON line, nothing on stderr, and exited with 2."""
    lines = result.stdout.splitlines()
    if result.returncode != 2 or result.stderr.strip() or len(lines) != 1:
        return None
    try:
        payload = json.loads(lines[0])
        return payload["error"]["code"] if payload["ok"] is False and set(payload) == {"ok", "error"} else None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def errors_hidden_checks(temp: Path, submission: Path) -> dict[str, bool]:
    """S5: each listed code for its error class, STORE_INVALID for an unreadable store, and clean output for all of them."""
    root = clone(submission, temp / "error-codes")
    outcomes = []
    expected = [(["create", "WO-101", "Duplicate"], "DUPLICATE_ID"), (["list", "--page-size", "101"], "INVALID_ARGUMENT"),
                (["list", "--foo", "bar"], "INVALID_ARGUMENT"), (["update", "WO-999", "--title", "Missing"], "NOT_FOUND")]
    for args, code in expected:
        result = invoke(root, args)
        outcomes.append((result, code))
    invoke(root, ["depends", "add", "WO-101", "WO-102"])
    outcomes.append((invoke(root, ["depends", "add", "WO-102", "WO-101"]), "DEPENDENCY_CYCLE"))
    invoke(root, ["depends", "add", "WO-103", "WO-104"])
    outcomes.append((invoke(root, ["update", "WO-103", "--status", "DONE"]), "DEPENDENCY_NOT_COMPLETE"))
    codes_ok = all(error_payload(result) == code for result, code in outcomes)
    clean = all(error_payload(result) is not None for result, _ in outcomes)
    broken = clone(submission, temp / "store-invalid")
    (broken / "data" / "work-orders.json").write_text("{\"version\": 2, \"workOrders\": [", encoding="utf-8")
    store_result = invoke(broken, ["list"])
    return {"errors.codes-all": codes_ok, "errors.store-invalid": error_payload(store_result) == "STORE_INVALID",
            "errors.clean-output": clean and error_payload(store_result) is not None}


def scale_checks(temp: Path, submission: Path) -> dict[str, bool]:
    """S6: the workload on a 100,000-order store; outputs and final store against the reference, then time against it."""
    import scale
    names = CHECKS["SCALE"] + CHECKS["SCALE_SPEED"]
    if not (submission / "src" / "cli.ts").exists():
        return {name: False for name in names}
    cpus = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpus[os.getpid() % len(cpus)]})
    text = json.dumps(scale.store(SCALE_SEED), ensure_ascii=False, indent=2) + "\n"
    reference = Path(__file__).parent / "scale-reference"

    def prepared(name: str, source: Path) -> Path:
        root = temp / name
        shutil.copytree(source, root, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
        (root / "data").mkdir(exist_ok=True)
        (root / "data" / "work-orders.json").write_text(text, encoding="utf-8")
        return root

    def run(source: Path, name: str):
        root = prepared(name, source)
        try:
            # CPU time of every command of the workload (grader 2.4.0), not wall time.
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            results = [(label, group, invoke(root, args, timeout=30)) for label, args, group in scale.workload()]
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            seconds = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
            final = scale.final_state((root / "data" / "work-orders.json").read_text(encoding="utf-8"))
            return results, seconds, final
        finally:
            shutil.rmtree(root, ignore_errors=True)

    expected, reference_time, expected_final = run(reference, "scale-reference-1")
    actual, candidate_time, actual_final = run(submission, "scale-candidate-1")
    same = {"list": True, "dependencies": True, "status": True}
    for (label, group, want), (_, _, got) in zip(expected, actual):
        if group == "list":
            same[group] &= got.returncode == want.returncode and scale.listing(got.stdout) == scale.listing(want.stdout)
        else:
            same[group] &= scale.outcome(got.returncode, got.stdout) == scale.outcome(want.returncode, want.stdout)
    finals = actual_final is not None and expected_final is not None
    orders_same = finals and actual_final["version"] == 2 and \
        {key: order.get("dependsOn") for key, order in actual_final["orders"].items()} == {key: order.get("dependsOn") for key, order in expected_final["orders"].items()}
    # Status, titles and descriptions match the reference; the events record exactly this run's successful writes, so a
    # dependency failure, which status-group commands do not cause, is not counted twice.
    fields = lambda final: {key: (order.get("status"), order.get("title"), order.get("description")) for key, order in final["orders"].items()}
    writes = sum(1 for _, group, result in actual if result.returncode == 0 and group != "list")
    status_same = finals and fields(actual_final) == fields(expected_final) and actual_final["contiguous"] and \
        len(actual_final["eventOrders"]) - 1_000 == writes
    checks = {"scale.list": same["list"], "scale.dependencies": same["dependencies"] and orders_same, "scale.status": same["status"] and status_same}
    ratio = float("inf")
    if all(checks.values()):
        for repetition in (2, 3):
            reference_time = min(reference_time, run(reference, f"scale-reference-{repetition}")[1])
            candidate_time = min(candidate_time, run(submission, f"scale-candidate-{repetition}")[1])
        ratio = candidate_time / reference_time
        RAW["scaleSpeedRatio"] = round(ratio, 4)
    for label, factor in SPEED_LADDER:
        checks[f"scale.speed-{label}"] = all(checks[name] for name in ("scale.list", "scale.dependencies", "scale.status")) and ratio <= factor
    print(json.dumps({"scale": {"ratio": None if ratio == float("inf") else round(ratio, 3), "reference": round(reference_time, 2),
                                "candidate": round(candidate_time, 2)}}), file=sys.stderr)
    return checks


def plan_checks(temp: Path, submission: Path) -> dict[str, bool]:
    """S7: plans on the hidden stores and the scale store, validated and placed on the quality scale; read-only planning;
    error codes; and hours and priority kept by earlier commands."""
    import plan as planning
    import scale
    names = CHECKS["PLAN"] + CHECKS["PLAN_QUALITY"]
    if not (submission / "src" / "cli.ts").exists():
        return {name: False for name in names}
    cpus = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpus[os.getpid() % len(cpus)]})
    anchors = planning.anchors()

    def planned(name: str, value: dict, crews: int):
        root = clone(submission, temp / f"plan-{name}")
        path = root / "data" / "work-orders.json"
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before = path.read_bytes()
        result, _ = invoke_cpu(root, ["plan", "--crews", str(crews)], PLAN_SECONDS)
        cost, reason = planning.check(value, crews, result.stdout) if result.returncode == 0 else (None, f"exit {result.returncode}")
        return cost, reason, path.read_bytes() == before

    valid, unchanged, places, report = {}, [], {}, {}
    for name, anchor in anchors.items():
        cost, reason, same = planned(name, planning.store(name), anchor["crews"])
        valid[name], places[name] = cost is not None, planning.place(cost, anchor)
        unchanged.append(same)
        report[name] = {"cost": cost, "reason": reason, "place": round(places[name], 4), **{key: anchor[key] for key in ("naive", "greedy", "best")}}
    scale_value = scale.store(SCALE_SEED)
    scale_cost, scale_reason, scale_same = planned("scale", scale_value, 8)
    report["scale"] = {"cost": scale_cost, "reason": scale_reason}
    unchanged.append(scale_same)
    mean = sum(places.values()) / len(places)
    checks = {"plan.valid-small": all(valid[name] for name in ("tiny", "small", "chains")),
              "plan.valid-large": all(valid[name] for name in ("general", "large")),
              "plan.valid-scale": scale_cost is not None}
    # Read-only: no plan wrote its store, and a version 1 store is not migrated by planning.
    v1 = clone(submission, temp / "plan-v1")
    v1_path = v1 / "data" / "work-orders.json"
    v1_store = json.loads((Path(__file__).parent / "v1-fixture.json").read_text(encoding="utf-8"))
    v1_path.write_text(json.dumps(v1_store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    v1_before = v1_path.read_bytes()
    v1_plan, _ = invoke_cpu(v1, ["plan", "--crews", "2"], PLAN_SECONDS)
    checks["plan.read-only"] = all(unchanged) and v1_plan.returncode == 0 and v1_path.read_bytes() == v1_before and any(valid.values())
    # Errors: bad crews and options; invalid hours or priority in the store.
    errors = clone(submission, temp / "plan-errors")
    codes = [error_payload(invoke(errors, args)) == "INVALID_ARGUMENT"
             for args in (["plan"], ["plan", "--crews", "0"], ["plan", "--crews", "51"], ["plan", "--crews", "two"], ["plan", "--crews", "2", "--fast", "1"])]
    for field, value in (("hours", 0), ("hours", "3"), ("priority", 6), ("priority", 2.5)):
        broken = clone(submission, temp / f"plan-invalid-{field}-{value}")
        store_value = json.loads((Path(__file__).parent / "base-fixture.json").read_text(encoding="utf-8"))
        store_value["workOrders"][0][field] = value
        (broken / "data" / "work-orders.json").write_text(json.dumps(store_value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        codes.append(error_payload(invoke(broken, ["plan", "--crews", "2"])) == "STORE_INVALID")
    checks["plan.errors"] = all(codes) and any(valid.values())
    # Earlier commands keep hours and priority; create sets neither.
    kept = clone(submission, temp / "plan-fields")
    kept_path = kept / "data" / "work-orders.json"
    store_value = json.loads(kept_path.read_text(encoding="utf-8"))
    for index, order in enumerate(store_value["workOrders"]):
        order["hours"], order["priority"] = index + 2, 5 - index % 5
    kept_path.write_text(json.dumps(store_value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    steps = [invoke(kept, args).returncode == 0 for args in (["update", "WO-101", "--title", "Kept fields"], ["depends", "add", "WO-103", "WO-104"],
                                                              ["update", "WO-102", "--description", "Still kept"], ["create", "PLAN-NEW", "No fields"])]
    try:
        after = {order["id"]: order for order in load_store(kept)["workOrders"]}
        fields_kept = all(after[order["id"]].get("hours") == order["hours"] and after[order["id"]].get("priority") == order["priority"]
                          for order in store_value["workOrders"])
        checks["plan.fields-preserved"] = all(steps) and fields_kept and "hours" not in after["PLAN-NEW"] and "priority" not in after["PLAN-NEW"] \
            and any(valid.values())
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        checks["plan.fields-preserved"] = False
    for label, threshold in planning.RUNGS:
        checks[f"plan.quality-{label}"] = mean >= threshold - 1e-9
    RAW["planQuality"] = round(mean, 6)
    print(json.dumps({"plan": {"mean": round(mean, 4), "stores": report}}), file=sys.stderr)
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


def noise(launcher: str | None, tolerance: float = 0.15) -> int:
    """PROTOCOL §9 noise test of S6 (grader 2.4.0): each reference judged by the scale checks on a quiet machine and with
    every core busy must get identical verdicts and a speed ratio that changes by at most `tolerance`."""
    global SANDBOX_LAUNCHER
    SANDBOX_LAUNCHER = launcher
    rows = []
    cores = sorted(os.sched_getaffinity(0))  # scale_checks pins this process to one core; the load spreads over all
    for name in ("ref-a", "ref-b"):
        submission = Path(__file__).resolve().parent.parent / "references" / name
        judged = []
        for loaded in (False, True):
            load = [subprocess.Popen([sys.executable, "-c", "while True: pass"], preexec_fn=lambda: os.sched_setaffinity(0, cores))
                    for _ in range(os.cpu_count() or 1)] if loaded else []
            RAW.clear()
            try:
                with tempfile.TemporaryDirectory(prefix="eng005-noise-") as temp:
                    checks = scale_checks(Path(temp) / "scale", submission)
            finally:
                for process in load:
                    process.kill()
                    process.wait()
            judged.append(({check for check, ok in checks.items() if ok}, RAW.get("scaleSpeedRatio")))
        (quiet, quiet_ratio), (busy, busy_ratio) = judged
        change = abs(busy_ratio / quiet_ratio - 1) if quiet_ratio and busy_ratio else None
        ok = quiet == busy and change is not None and change <= tolerance
        print(f"S6 {name}: quiet {quiet_ratio} {sorted(quiet)}; busy ({os.cpu_count()} cores loaded) {busy_ratio} {sorted(busy)}; "
              f"ratio change {None if change is None else round(change, 3)}" + ("" if ok else "  NOT STABLE"))
        rows.append(ok)
    print(f"RESULT: {'PASS' if all(rows) else 'FAIL'} ({sum(rows)}/{len(rows)}), tolerance {tolerance}")
    return 0 if all(rows) else 1


def main() -> None:
    global SANDBOX_LAUNCHER
    if "--noise" in sys.argv[1:]:
        launcher = sys.argv[sys.argv.index("--launcher") + 1] if "--launcher" in sys.argv else None
        raise SystemExit(noise(launcher))
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    sandbox = request.get("sandbox")
    SANDBOX_LAUNCHER = sandbox.get("launcher") if isinstance(sandbox, dict) else None
    submission = Path(request["submission"]["directory"])
    active = request["context"]["activeRequirementIds"]
    selected = [check for requirement in active for check in CHECKS.get(requirement, [])]
    preservation_fixture = json.loads((Path(__file__).parent / "base-fixture.json").read_text(encoding="utf-8"))
    outcomes: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="eng005-hidden-") as temp:
        temp_path = Path(temp)
        for group in active:
            group_root = clone(submission, temp_path / group)
            hidden = temp_path / f"{group}-hidden"
            if group == "BASE_CLI": outcomes.update(base_checks(group_root))
            elif group == "BASE_DATA": outcomes["data.preserves-seed"] = data_preservation_check(submission, preservation_fixture)
            elif group == "QUERY":
                outcomes.update(query_checks(group_root))
                outcomes.update(query_hidden_checks(clone(submission, hidden)))
            elif group == "DEPENDENCY":
                outcomes.update(dependency_checks(group_root))
                outcomes.update(dependency_hidden_checks(hidden, submission))
            elif group == "NO_MUTATION":
                outcomes["failure.no_mutation"] = no_mutation_check(group_root)
                outcomes.update(no_mutation_hidden_checks(hidden, submission))
            elif group == "MIGRATION":
                fixture = json.loads((Path(__file__).parent / "v1-fixture.json").read_text(encoding="utf-8"))
                migration_root = clone(submission, temp_path / "migration-fixture")
                outcomes.update(migration_checks(migration_root, fixture))
                outcomes.update(migration_hidden_checks(clone(submission, hidden), fixture))
            elif group == "ERRORS_DOCS":
                outcomes.update(errors_docs_checks(group_root))
                outcomes.update(errors_hidden_checks(hidden, submission))
            elif group == "SCALE":
                outcomes.update(scale_checks(temp_path / "scale", submission))
            elif group == "PLAN":
                outcomes.update(plan_checks(temp_path / "plan", submission))
    # The base and seed checks guard against regressions: an untouched project passes them, so they count only when
    # some check of a stage's own requirement passes.
    if not any(outcomes.get(check, False) for requirement in active if requirement not in GUARDS for check in CHECKS.get(requirement, [])):
        for requirement in GUARDS:
            for check in CHECKS[requirement]:
                outcomes[check] = False
    checks = [{"id": check_id, "requirementId": ALL_CHECKS[check_id], "status": "pass" if outcomes.get(check_id, False) else "fail", "evidenceRefs": []}
              for check_id in selected]
    units = {"scaleSpeedRatio": "x reference CPU time", "planQuality": "mean place, naive 0, greedy 0.5, best known 1"}
    metrics = [{"id": name, "value": value, "unit": units[name]} for name, value in sorted(RAW.items())]
    result = {"schemaVersion": 2, "requestId": request["requestId"], "taskId": request["task"]["id"],
              "taskVersion": request["task"]["version"], "graderVersion": GRADER_VERSION, "gradingStatus": "completed",
              "checks": checks, "dimensions": [], "unscoredCheckIds": [], "reason": None, "error": None, "metrics": metrics}
    args.result.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
