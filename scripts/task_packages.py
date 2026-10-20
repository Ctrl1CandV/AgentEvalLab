#!/usr/bin/env python3
"""Check or refresh task-package integrity without Node.js.

Mirrors the preflight rules in src/evaluation/manifest.ts:
- every file listed in a manifest exists and matches its SHA-256 digest;
- public/, private/ (excluding Python caches) and stages/ contain exactly the declared files;
- example and experiment plans pin the current manifest digest.

Usage:
  python3 scripts/task_packages.py check
  python3 scripts/task_packages.py rehash <package-dir> [<package-dir> ...]

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
    for label, declared, actual in (
        ("public", declared_public, list_files(package, "public")),
        ("private", declared_private, list_files(package, "private", skip_python_caches=True)),
        ("stages", declared_stages, list_files(package, "stages")),
        ("items", declared_items, list_files(package, "items")),
    ):
        for path in sorted(set(actual) - set(declared)):
            problems.append("undeclared %s file: %s" % (label, path))
        for path in sorted(set(declared) - set(actual)):
            problems.append("declared %s file missing: %s" % (label, path))
    return manifest, problems


def example_pins():
    pins = []
    plan_paths = glob.glob(os.path.join(ROOT, "examples", "*.eval.json")) + \
        glob.glob(os.path.join(ROOT, "experiments", "**", "*.eval.json"), recursive=True)
    for plan_path in sorted(plan_paths):
        plan = load_json(plan_path)
        for index, case in enumerate(plan.get("cases", [])):
            if isinstance(case.get("packagePath"), str):
                package = os.path.normpath(os.path.join(ROOT, case["packagePath"]))
                pins.append((plan_path, index, package, case.get("packageManifestSha256")))
    return pins


def check(_args):
    failed = False
    for package in package_dirs():
        manifest, problems = check_package(package)
        status = "ok" if not problems else "FAILED"
        print("%-6s %s %s" % (status, relative(package), manifest["version"]))
        for problem in problems:
            print("         " + problem)
        failed = failed or bool(problems)
    for plan_path, index, package, pinned in example_pins():
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
    commands.add_parser("check")
    rehash_parser = commands.add_parser("rehash")
    rehash_parser.add_argument("packages", nargs="+")
    args = parser.parse_args()
    return check(args) if args.command == "check" else rehash(args)


if __name__ == "__main__":
    sys.exit(main())
