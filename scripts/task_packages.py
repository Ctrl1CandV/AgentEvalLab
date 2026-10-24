#!/usr/bin/env python3
"""Check or refresh task-package integrity without Node.js.

Mirrors the preflight rules in src/evaluation/manifest.ts:
- every file listed in a manifest exists and matches its SHA-256 digest;
- public/, private/ (excluding Python caches), stages/, items/, runtime/ and assets/ contain exactly the declared files
  (assets/ holds external archives outside Git, restored by scripts/prepare-assets.mjs);
- example and experiment plans pin the current manifest digest;
- for a v2 manifest (CODE §3.1): the capability card is hashed, every task has a split and a structure group, no
  structure group spans two splits, every anchored metric a task is scored on has a raw value for every anchor, the score
  model's groups cover every check a task is graded on, runtime mounts and repository archives are hashed.

Usage:
  python3 scripts/task_packages.py check [--plans <plan.eval.json> ...]
  python3 scripts/task_packages.py rehash <package-dir> [<package-dir> ...]

check --plans checks every package but only the named plans' pins (a suite's
preflight); historical plans that pin earlier package versions are left out.

rehash rewrites digests for files already listed in a manifest, refreshes
metadata.json "content_hashes_sha256_16" prefixes, then updates example- and
experiment-plan pins. It never adds or removes manifest entries; a file-set mismatch is an error
that needs a deliberate manifest edit.
"""
import argparse
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    # Matches the existing two-space, trailing-newline format byte for byte.
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def list_files(package, directory, skip_python_caches=False):
    base = os.path.join(package, directory)
    if not os.path.isdir(base):
        return []
    found = []
    for current, directories, files in os.walk(base):
        # Hidden entries are never package material; the harness skips them too.
        directories[:] = [name for name in directories if not name.startswith(".")]
        if skip_python_caches:
            directories[:] = [name for name in directories if name != "__pycache__"]
        for name in files:
            if name.startswith(".") or (skip_python_caches and name.endswith(".pyc")):
                continue
            found.append(os.path.relpath(os.path.join(current, name), package).replace(os.sep, "/"))
    return sorted(found)


def manifest_entries(manifest):
    entries = manifest["files"]["public"] + manifest["files"]["trusted"]
    for stage in manifest.get("stages", []):
        entries = entries + stage["files"]
    for item in manifest.get("items", []):
        entries = entries + item["files"]
    return entries


def package_dirs():
    return sorted(os.path.dirname(path) for path in glob.glob(os.path.join(ROOT, "task-library", "*", "*", "manifest.json")))


def relative(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def check_package(package):
    problems = []
    manifest = load_json(os.path.join(package, "manifest.json"))
    for entry in manifest_entries(manifest):
        if any(part.startswith(".") for part in entry["path"].split("/")):
            problems.append("hidden file declared: " + entry["path"])
        path = os.path.join(package, *entry["path"].split("/"))
        if not os.path.isfile(path) or os.path.islink(path):
            problems.append("missing or linked: " + entry["path"])
        elif sha256_file(path) != entry["sha256"].lower():
            problems.append("hash mismatch: " + entry["path"])
    declared_public = sorted(e["path"] for e in manifest["files"]["public"] if e["path"].startswith("public/"))
    declared_private = sorted(e["path"] for e in manifest["files"]["trusted"] if e["path"].startswith("private/"))
    declared_stages = sorted(e["path"] for stage in manifest.get("stages", []) for e in stage["files"])
    declared_items = sorted(e["path"] for item in manifest.get("items", []) for e in item["files"])
    declared_runtime = sorted(e["path"] for e in manifest["files"]["trusted"] if e["path"].startswith("runtime/"))
    for label, declared, actual in (
        ("public", declared_public, list_files(package, "public")),
        ("private", declared_private, list_files(package, "private", skip_python_caches=True)),
        ("stages", declared_stages, list_files(package, "stages")),
        ("items", declared_items, list_files(package, "items")),
        ("runtime", declared_runtime, list_files(package, "runtime")),
        ("assets", sorted(e["path"] for e in manifest["files"]["trusted"] if e["path"].startswith("assets/")), list_files(package, "assets")),
    ):
        for path in sorted(set(actual) - set(declared)):
            problems.append("undeclared %s file: %s" % (label, path))
        for path in sorted(set(declared) - set(actual)):
            problems.append("declared %s file missing: %s" % (label, path))
    if manifest.get("schemaVersion") == 2:
        problems += check_v2(manifest)
    return manifest, problems


def metrics_of(model, item_id):
    """The metrics a task is normalised on: its headline metric and those of the metric groups applying to it."""
    headline = (model.get("primaryByItem") or {}).get(item_id) or model.get("primary") or {}
    used = {headline["metric"]} if headline.get("kind") == "metric" else set()
    for group in model.get("groups", []):
        if group.get("rule") == "metric" and (group.get("items") is None or item_id in group["items"]):
            used.add(group["metric"])
    return used


def check_v2(manifest):
    """The v2 rules the harness also enforces, mirrored without Node.js."""
    problems = []
    trusted = {entry["path"] for entry in manifest["files"]["trusted"]}
    if manifest.get("card") not in trusted:
        problems.append("capability card not hashed: %s" % manifest.get("card"))
    model = manifest.get("scoreModel") or {}
    anchored = {metric["id"]: [point["name"] for point in metric["anchors"]["points"]] for metric in model.get("metrics", []) if metric.get("anchors")}
    grouped = {check for group in model.get("groups", []) for check in group.get("checkIds", [])}
    if model.get("format"):
        grouped.add(model["format"]["checkId"])
    requirements = {requirement["id"]: requirement["checkIds"] for requirement in manifest["requirements"]}
    tasks = [(item["id"], item, item["activeRequirementIds"]) for item in manifest.get("items", [])]
    if not tasks:
        active = manifest["stages"][-1]["activeRequirementIds"] if manifest.get("stages") else list(requirements)
        tasks = [("(package)", manifest.get("task") or {}, active)]
    splits = {}
    for name, placement, active in tasks:
        split, structure = placement.get("split"), placement.get("structure")
        if split not in ("dev", "validation", "holdout") or not structure:
            problems.append("task %s has no split or structure group" % name)
            continue
        if splits.setdefault(structure, split) != split:
            problems.append("structure group %s spans splits %s and %s" % (structure, splits[structure], split))
        for metric, names in anchored.items():
            if metric not in metrics_of(model, None if name == "(package)" else name):
                continue
            values = (placement.get("anchors") or {}).get(metric) or {}
            missing = [anchor for anchor in names if not isinstance(values.get(anchor), (int, float))]
            if missing:
                problems.append("task %s lacks anchors %s of %s" % (name, ", ".join(missing), metric))
        for requirement in active:
            for check in requirements.get(requirement, []):
                if check not in grouped:
                    problems.append("task %s: check %s is in no score group" % (name, check))
    mounts = {mount["path"] for mount in (manifest.get("runtime") or {}).get("mounts", [])}
    archives = {mount["path"]: mount.get("archive") for mount in (manifest.get("runtime") or {}).get("mounts", [])}
    for mount in sorted(mounts):
        if archives.get(mount):
            if archives[mount] not in trusted or not archives[mount].startswith("assets/"):
                problems.append("runtime mount %s: archive not a hashed asset: %s" % (mount, archives[mount]))
        elif not any(path.startswith(mount + "/") for path in trusted):
            problems.append("runtime mount %s has no hashed files" % mount)
    for item in manifest.get("items", []):
        repository = item.get("repository")
        if repository and repository.get("archive") not in trusted:
            problems.append("task %s: repository archive not hashed: %s" % (item["id"], repository.get("archive")))
        for mount in item.get("mounts", []):
            if mount not in mounts:
                problems.append("task %s: unknown runtime mount %s" % (item["id"], mount))
    return problems


def example_pins(plan_paths=None):
    pins = []
    if plan_paths is None:
        plan_paths = glob.glob(os.path.join(ROOT, "examples", "*.eval.json")) + \
            glob.glob(os.path.join(ROOT, "experiments", "**", "*.eval.json"), recursive=True)
    for plan_path in sorted(plan_paths):
        plan = load_json(plan_path)
        for index, case in enumerate(plan.get("cases", [])):
            if isinstance(case.get("packagePath"), str):
                package = os.path.normpath(os.path.join(ROOT, case["packagePath"]))
                pins.append((plan_path, index, package, case.get("packageManifestSha256")))
    return pins


def check(args):
    failed = False
    for package in package_dirs():
        manifest, problems = check_package(package)
        status = "ok" if not problems else "FAILED"
        print("%-6s %s %s" % (status, relative(package), manifest["version"]))
        for problem in problems:
            print("         " + problem)
        failed = failed or bool(problems)
    plans = [os.path.abspath(path) for path in args.plans] if getattr(args, "plans", None) else None
    for plan_path, index, package, pinned in example_pins(plans):
        manifest_path = os.path.join(package, "manifest.json")
        if not os.path.isfile(manifest_path):
            print("FAILED %s case %d: package has no manifest" % (relative(plan_path), index))
            failed = True
        elif sha256_file(manifest_path) != (pinned or "").lower():
            print("FAILED %s case %d: stale manifest pin" % (relative(plan_path), index))
            failed = True
    if not failed:
        print("All manifests, package file sets and plan pins are consistent.")
    return 1 if failed else 0


def refresh_metadata_hashes(package):
    path = os.path.join(package, "metadata.json")
    if not os.path.isfile(path):
        return
    metadata = load_json(path)
    hashes = metadata.get("content_hashes_sha256_16")
    if not isinstance(hashes, dict):
        return
    for name in hashes:
        target = os.path.join(package, *name.split("/"))
        if os.path.isfile(target) and name != "metadata.json":
            hashes[name] = sha256_file(target)[:16]
    write_json(path, metadata)


def rehash(args):
    targets = [os.path.normpath(os.path.abspath(path)) for path in args.packages]
    for package in targets:
        manifest_path = os.path.join(package, "manifest.json")
        if not os.path.isfile(manifest_path):
            print("not a manifest package: " + relative(package), file=sys.stderr)
            return 2
        refresh_metadata_hashes(package)
        manifest = load_json(manifest_path)
        for entry in manifest_entries(manifest):
            path = os.path.join(package, *entry["path"].split("/"))
            if not os.path.isfile(path):
                print("missing listed file %s in %s" % (entry["path"], relative(package)), file=sys.stderr)
                return 2
            entry["sha256"] = sha256_file(path)
        write_json(manifest_path, manifest)
        _, problems = check_package(package)
        if problems:
            print("file-set problems remain in %s:" % relative(package), file=sys.stderr)
            for problem in problems:
                print("  " + problem, file=sys.stderr)
            return 2
        print("rehashed %s %s -> %s" % (relative(package), manifest["version"], sha256_file(manifest_path)))
    updated = {}
    for plan_path, index, package, _ in example_pins():
        if package in targets:
            plan = updated.setdefault(plan_path, load_json(plan_path))
            plan["cases"][index]["packageManifestSha256"] = sha256_file(os.path.join(package, "manifest.json"))
    for plan_path, plan in updated.items():
        write_json(plan_path, plan)
        print("updated pin in " + relative(plan_path))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--plans", nargs="+")
    rehash_parser = commands.add_parser("rehash")
    rehash_parser.add_argument("packages", nargs="+")
    args = parser.parse_args()
    return check(args) if args.command == "check" else rehash(args)


if __name__ == "__main__":
    sys.exit(main())
