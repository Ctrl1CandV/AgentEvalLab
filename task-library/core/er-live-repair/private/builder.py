#!/usr/bin/env python3
"""Builds ER tasks: real issues in Python repositories, fixed by a merged change with tests (TASK_LIBRARY §3.1).

Instances come from SWE-bench-Live (dev) and from our own mining of recent merged fixes (validation, holdout). Each
candidate is admitted only when, on this machine, in the sandbox, with its dependencies installed from wheels into a
read-only runtime:

- the base commit with the gold tests fails every FAIL_TO_PASS test and passes every PASS_TO_PASS test;
- the gold fix with the gold tests passes all of them, three times in a row (flaky tests are dropped first);
- the selected test files run in under five minutes.

Every candidate's outcome, admitted or rejected with its reason, is recorded under the work directory and summarised in
`private/selection.json`. Repositories and runtimes are stored as external assets (content-addressed cache,
`scripts/prepare-assets.mjs`), never in Git.

Usage (from the package directory):
  python3 private/builder.py pool-candidates [--since 2025-06]       # list SWE-bench-Live candidates
  python3 private/builder.py prepare <instance-id> [--source pool|mined]
  python3 private/builder.py mine <owner/repo> --since YYYY-MM-DD [--limit N]
  python3 private/builder.py package
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
REPO_ROOT = os.path.abspath(os.path.join(PACKAGE, "..", "..", ".."))
WORK = os.environ.get("AGENTEVAL_ER_WORK", os.path.expanduser("~/.cache/agenteval/er"))
ASSETS = os.environ.get("AGENTEVAL_ASSET_CACHE", os.path.expanduser("~/.cache/agenteval/assets"))
POOL = os.path.join(WORK, "swe-bench-live-full.jsonl")
LAUNCHER = os.path.join(REPO_ROOT, "scripts", "sandbox_exec.py")
sys.path.insert(0, HERE)
import grader  # noqa: E402  (one parser of test results for admission and grading)
PYTHON = sys.executable
TEST_TIMEOUT = 300  # five minutes for the selected test files
MAX_RUNTIME_BYTES = 400_000_000  # CODE §4: runtimes of about 200 MB; a GPU stack of several GB is refused
EXTRAS = ("test", "tests", "testing", "dev")
REQUIREMENT_FILES = ("requirements-dev.txt", "requirements-test.txt", "requirements_test.txt", "test-requirements.txt", "dev-requirements.txt",
                     "requirements/test.txt", "requirements/tests.txt", "requirements/dev.txt", "requirements/testing.txt")
PERMISSIVE = ("MIT", "BSD", "Apache", "ISC", "Python Software Foundation", "PSF", "Unlicense", "Zlib", "MPL")


def log(message):
    print(time.strftime("%H:%M:%S"), message, file=sys.stderr, flush=True)


def run(command, cwd, timeout=600, env=None, check=False):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(command[:4])}... failed: {result.stderr[-800:]}")
    return result


def record_path(instance_id):
    return os.path.join(WORK, "records", f"{instance_id}.json")


def save_record(record):
    os.makedirs(os.path.join(WORK, "records"), exist_ok=True)
    with open(record_path(record["instance_id"]), "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)


def reject(instance, stage, reason, **extra):
    record = {"instance_id": instance["instance_id"], "repo": instance["repo"], "source": instance.get("source", "pool"), "status": "rejected",
              "stage": stage, "reason": reason[:2000], "created_at": instance.get("created_at"), **extra}
    save_record(record)
    log(f"{instance['instance_id']}: rejected at {stage}: {reason[:200]}")
    return record


# Patches and test files ---------------------------------------------------------------------------------------------

def patch_files(patch):
    return sorted(set(re.findall(r"^diff --git a/(\S+) b/", patch, re.M)))


def test_node_file(node):
    return node.split("::", 1)[0]


# Repository ---------------------------------------------------------------------------------------------------------

def checkout(repo, commit):
    """Fetches the commit into a bare mirror of the repository (shallow, cached per repository)."""
    mirror = os.path.join(WORK, "mirrors", repo.replace("/", "__"))
    if not os.path.isdir(mirror):
        os.makedirs(os.path.dirname(mirror), exist_ok=True)
        run(["git", "init", "--quiet", "--bare", mirror], WORK, check=True)
        run(["git", "-C", mirror, "remote", "add", "origin", f"https://github.com/{repo}.git"], WORK, check=True)
    if run(["git", "-C", mirror, "cat-file", "-e", f"{commit}^{{commit}}"], WORK).returncode != 0:
        run(["git", "-C", mirror, "fetch", "--quiet", "--depth", "1", "origin", commit], WORK, timeout=900, check=True)


def export_tree(repo, commit, destination):
    """The working tree at the commit, without .git, into destination."""
    mirror = os.path.join(WORK, "mirrors", repo.replace("/", "__"))
    data = subprocess.run(["git", "-C", mirror, "archive", "--format=tar", commit], capture_output=True, timeout=600, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(destination, filter="tar")


def deterministic_tar(source, target):
    """A tar of a directory with sorted entries, fixed times and owners: its bytes depend only on the contents."""
    with tarfile.open(target, "w", format=tarfile.GNU_FORMAT) as tar:
        for current, folders, files in os.walk(source):
            folders.sort()
            for name in sorted(folders) + sorted(files):
                path = os.path.join(current, name)
                info = tar.gettarinfo(path, arcname=os.path.relpath(path, source))
                info.mtime, info.uid, info.gid, info.uname, info.gname = 1790000000, 0, 0, "", ""
                if info.isfile():
                    with open(path, "rb") as handle:
                        tar.addfile(info, handle)
                elif not os.path.isdir(path) or info.isdir():
                    tar.addfile(info)


def store_asset(path):
    """Copies a file into the content-addressed asset cache; returns its sha256."""
    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    os.makedirs(ASSETS, exist_ok=True)
    target = os.path.join(ASSETS, digest)
    if not os.path.exists(target):
        shutil.copy(path, target + ".partial")
        os.replace(target + ".partial", target)
    return digest


def licence_of(tree):
    # LICENSE first; then dual-licence files (LICENSE.APACHE, LICENSE-MIT, ...), whose permissive half suffices.
    names = ["LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "COPYING", "LICENSE.rst"]
    names += sorted(name for name in os.listdir(tree) if re.match(r"LICEN[CS]E[-._]", name) and name not in names)
    for name in names:
        path = os.path.join(tree, name)
        if os.path.isfile(path):
            text = open(path, encoding="utf-8", errors="replace").read(4000)
            if re.search(r"terms of \*?either\*? of the licenses", text, re.I):
                continue
            if re.search(r"MIT License|Permission is hereby granted, free of charge", text):
                return "MIT"
            if re.search(r"Apache License", text):
                return "Apache-2.0"
            if re.search(r"Redistribution and use in source and binary forms", text):
                return "BSD-3-Clause" if "Neither the name" in text or "neither the name" in text else "BSD-2-Clause"
            if re.search(r"Mozilla Public License", text):
                return "MPL-2.0"
            if re.search(r"ISC License|Permission to use, copy, modify, and(/or)? distribute", text):
                return "ISC"
            if re.search(r"GNU (Affero |Lesser )?General Public License", text):
                return "GPL-family"
            return "unknown"
    return "none"


# Runtime --------------------------------------------------------------------------------------------------------------

def declared_test_requirements(tree):
    """Requirement strings a project declares for its tests outside its extras: PEP 735 dependency groups, Poetry
    groups, Hatch and PDM environments, tox deps. Poetry version syntax is dropped (names only)."""
    import tomllib
    found = []
    path = os.path.join(tree, "pyproject.toml")
    if os.path.isfile(path):
        try:
            data = tomllib.load(open(path, "rb"))
        except tomllib.TOMLDecodeError:
            data = {}
        wanted = lambda name: re.search(r"test|dev|ci", name, re.I)
        for name, entries in (data.get("dependency-groups") or {}).items():
            if wanted(name):
                found += [entry for entry in entries if isinstance(entry, str)]
        poetry = (data.get("tool") or {}).get("poetry") or {}
        groups = {name: group.get("dependencies", {}) for name, group in (poetry.get("group") or {}).items()}
        groups["dev-dependencies"] = poetry.get("dev-dependencies") or {}
        for name, entries in groups.items():
            if wanted(name):
                found += [package for package in entries if package.lower() != "python"]
        for name, environment in (((data.get("tool") or {}).get("hatch") or {}).get("envs") or {}).items():
            if wanted(name) or name == "default":
                found += [entry for entry in environment.get("dependencies", []) + environment.get("extra-dependencies", []) if isinstance(entry, str)]
        for name, entries in (((data.get("tool") or {}).get("pdm") or {}).get("dev-dependencies") or {}).items():
            if wanted(name):
                found += [entry for entry in entries if isinstance(entry, str)]
    tox = os.path.join(tree, "tox.ini")
    if os.path.isfile(tox):
        for block in re.findall(r"^deps\s*=\s*((?:.*\n(?:[ \t]+.*\n)*))", open(tox, encoding="utf-8", errors="replace").read(), re.M):
            found += [line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith(("-", "{", "#", "."))]
    # Plain names and PEP 508 requirements only; local paths, includes and environment markers that pip cannot read go.
    cleaned = []
    for entry in found:
        # Without its marker and its spaces ("pytest >= 9.0" is "pytest>=9.0"): markers here are platform choices.
        entry = re.sub(r"\s+", "", entry.split(";")[0])
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?([<>=!~]=?[^,]+(,[<>=!~]=?[^,]+)*)?", entry):
            cleaned.append(entry)
    return sorted(set(cleaned))


def released_version(tree):
    """The latest version of the project on PyPI (by its declared name), or 0.0.0."""
    import configparser
    import tomllib
    import urllib.request
    name = None
    try:
        name = ((tomllib.load(open(os.path.join(tree, "pyproject.toml"), "rb")).get("project") or {}).get("name"))
    except (OSError, tomllib.TOMLDecodeError):
        pass
    if not name and os.path.isfile(os.path.join(tree, "setup.cfg")):
        config = configparser.ConfigParser(interpolation=None)
        try:
            config.read(os.path.join(tree, "setup.cfg"), encoding="utf-8")
            name = config.get("metadata", "name", fallback=None)
        except configparser.Error:
            pass
    if not name or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        return "0.0.0"
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=30) as response:
            version = json.load(response)["info"]["version"]
        return version if re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", version) else "0.0.0"
    except Exception:  # noqa: BLE001
        return "0.0.0"


def build_runtime(tree, site):
    """Installs the project's test dependencies from wheels only into site, then removes the project itself so that
    the workspace copy is the one imported. Returns (ok, detail)."""
    os.makedirs(site, exist_ok=True)
    # The tree's own files before the build: a build backend may write its generated module into the tree itself.
    original = {os.path.relpath(os.path.join(current, name), tree) for current, _, files in os.walk(tree) for name in files}
    requirements = [f"-r{os.path.join(tree, name)}" for name in REQUIREMENT_FILES if os.path.isfile(os.path.join(tree, name))]
    report = os.path.join(os.path.dirname(site), "pip-report.json")
    declared = declared_test_requirements(tree)
    # The archive has no Git history, so version plugins (setuptools-scm, hatch-vcs, pdm) get a stated version: the
    # project's latest release, so that test dependencies requiring the project (pytest needs pluggy >= 1.5) resolve.
    version = released_version(tree)
    dropped_early = []
    env = {**os.environ, "SETUPTOOLS_SCM_PRETEND_VERSION": version, "PDM_BUILD_SCM_VERSION": version}
    # Each declared test requirement alone must be installable from wheels here; the others go (a Windows-only loop,
    # a package whose dependency has no wheel), so that one of them cannot take the test plugins down with it.
    probed = []
    for requirement in declared:
        probe = run([PYTHON, "-m", "pip", "install", "--dry-run", "--quiet", "--disable-pip-version-check", "--only-binary=:all:", "--ignore-installed",
                     requirement], tree, timeout=600, env=env)
        (probed if probe.returncode == 0 else dropped_early).append(requirement)
    declared = probed
    attempts = [(EXTRAS, declared), (EXTRAS, []), (EXTRAS[:3], declared), (EXTRAS[:3], [])]
    errors = []
    dropped = list(dropped_early)
    for extras, extra_requirements in attempts:
        extra_requirements = list(extra_requirements)
        # A declared test requirement without a wheel (or for another platform) is dropped by name, the rest kept:
        # a test plugin named in the pytest configuration (pytest-mock, say) must not go with it.
        for _ in range(8):
            shutil.rmtree(site, ignore_errors=True)
            os.makedirs(site)
            command = [PYTHON, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-compile", "--target", site,
                       "--only-binary=:all:", "--report", report, f"{tree}[{','.join(extras)}]", "pytest", *requirements, *extra_requirements]
            result = run(command, tree, timeout=1800, env=env)
            if result.returncode == 0:
                break
            message = result.stderr or result.stdout
            errors.append(message[-600:])
            failing = re.findall(r"(?:No matching distribution found for|satisfies the requirement|Cannot install) ([A-Za-z0-9_.\-\[\]]+)", message)
            names = {re.sub(r"[-_.]+", "-", re.split(r"[\[<>=!~; ]", name, maxsplit=1)[0]).lower() for name in failing}
            keep = [entry for entry in extra_requirements if re.sub(r"[-_.]+", "-", re.split(r"[\[<>=!~; ]", entry.strip(), maxsplit=1)[0]).lower() not in names]
            if not names or len(keep) == len(extra_requirements):
                break
            dropped += [entry for entry in extra_requirements if entry not in keep]
            extra_requirements = keep
        if result.returncode == 0:
            break
    else:
        return False, "pip: " + " | ".join(errors)[-1500:]
    # The project itself: its distribution from the local path, removed by its RECORD.
    generated = {}
    with open(report, encoding="utf-8") as handle:
        installed = json.load(handle).get("install", [])
    local = [entry["metadata"]["name"] for entry in installed if entry.get("download_info", {}).get("url", "").startswith("file://")]
    for name in local:
        normalized = re.sub(r"[-_.]+", "_", name).lower()
        for info in os.listdir(site):
            if info.endswith(".dist-info") and re.sub(r"[-_.]+", "_", info[:-len(".dist-info")].rsplit("-", 1)[0]).lower() == normalized:
                record = os.path.join(site, info, "RECORD")
                # Entry points stay registered (a project shipping a pytest plugin, as anyio does, needs its pytest11
                # entry point); the modules they name resolve to the workspace copy, which comes first on the path.
                kept = {name: open(os.path.join(site, info, name), encoding="utf-8").read() for name in ("METADATA", "entry_points.txt")
                        if os.path.isfile(os.path.join(site, info, name))}
                for line in open(record, encoding="utf-8"):
                    relative = line.split(",")[0]
                    path = os.path.join(site, relative)
                    if not os.path.isfile(path):
                        continue
                    # A module the build generated (a setuptools-scm _version.py): the repository needs it too.
                    if relative.endswith(".py") and not relative.startswith("..") and ".dist-info/" not in relative and \
                            not any(candidate in original for candidate in (relative, os.path.join("src", relative))):
                        generated[relative] = open(path, encoding="utf-8", errors="replace").read()
                    os.remove(path)
                shutil.rmtree(os.path.join(site, info), ignore_errors=True)
                if "entry_points.txt" in kept and "METADATA" in kept:
                    os.makedirs(os.path.join(site, info))
                    for name, text in kept.items():
                        with open(os.path.join(site, info, name), "w", encoding="utf-8") as handle:
                            handle.write(text)
    # Whatever the project's own packages are called, the workspace copy must be the only one importable.
    for root in (tree, os.path.join(tree, "src")):
        if os.path.isdir(root):
            for name in os.listdir(root):
                if os.path.isfile(os.path.join(root, name, "__init__.py")) and os.path.isdir(os.path.join(site, name)):
                    shutil.rmtree(os.path.join(site, name))
    # Empty directories left by the removal, and bytecode caches.
    for current, folders, files in os.walk(site, topdown=False):
        if os.path.basename(current) == "__pycache__":
            shutil.rmtree(current, ignore_errors=True)
        elif current != site and not os.listdir(current):
            os.rmdir(current)
    # Generated modules go beside the runtime, to be added to every tree that uses it (only where the package exists).
    generated = {path: text for path, text in generated.items() if os.path.isdir(os.path.join(tree, os.path.dirname(path)))
                 or os.path.isdir(os.path.join(tree, "src", os.path.dirname(path)))}
    with open(os.path.join(os.path.dirname(site), "generated.json"), "w", encoding="utf-8") as handle:
        json.dump(generated, handle)
    return True, f"{len(installed)} distributions, project {local} {version}, generated {sorted(generated)}, dropped {sorted(set(dropped))}"


def add_generated(tree, site):
    """Adds the build's generated modules (recorded beside the runtime) to a tree that lacks them."""
    path = os.path.join(os.path.dirname(site), "generated.json")
    if not os.path.isfile(path):
        return
    for relative, text in json.load(open(path, encoding="utf-8")).items():
        for root in (tree, os.path.join(tree, "src")):
            if os.path.isdir(os.path.join(root, os.path.dirname(relative))) and not os.path.exists(os.path.join(root, relative)):
                with open(os.path.join(root, relative), "w", encoding="utf-8") as handle:
                    handle.write(text)
                break


# Tests ----------------------------------------------------------------------------------------------------------------

def run_tests(tree, site, files, timeout=TEST_TIMEOUT):
    """{node id: status} from pytest -rA on the given test files, in the sandbox with the runtime bound read-only."""
    command = [PYTHON, "-m", "pytest", "-rA", "-p", "no:cacheprovider", "--no-header", "-q", *files]
    # The repository first, as in the package's runtime environment: its own code is the code under test.
    sandboxed = [PYTHON, LAUNCHER, "--rw", tree, "--mount", f"{site}:/runtime/site", "--env", f"PYTHONPATH={tree}/src:{tree}:/runtime/site", "--env",
                 "PYTHONDONTWRITEBYTECODE=1", "--", *command]
    started = time.monotonic()
    try:
        result = subprocess.run(sandboxed, cwd=tree, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, time.monotonic() - started, "timeout"
    return grader.parse_results(result.stdout), time.monotonic() - started, (result.stdout if result.stdout.strip() else result.stderr)[-3000:]


def apply(tree, patch):
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as handle:
        handle.write(patch)
    try:
        return run(["git", "apply", "--whitespace=nowarn", handle.name], tree).returncode == 0
    finally:
        os.remove(handle.name)


def passed(status):
    return status in ("PASSED", "XFAIL")


def cut(node):
    """A test id as SWE-bench-style log parsers record it: up to the first space."""
    return node.split(" ", 1)[0]


# Prepare (validate) one instance --------------------------------------------------------------------------------------

def prepare(instance, site=None, detail=None):
    """Validates one candidate; writes its record and, when admitted, its repository and runtime archives. A mined
    candidate (no FAIL_TO_PASS yet) gets its tests from the runs: FAIL_TO_PASS fail at the base and pass with the fix,
    PASS_TO_PASS pass in both. `site` is a runtime already built for the repository (mining); otherwise one is built at
    the base commit."""
    instance_id = instance["instance_id"]
    base = os.path.join(WORK, "build", instance_id)
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    try:
        checkout(instance["repo"], instance["base_commit"])
    except Exception as error:  # noqa: BLE001
        return reject(instance, "clone", str(error))
    tree = os.path.join(base, "tree")
    export_tree(instance["repo"], instance["base_commit"], tree)
    licence = licence_of(tree)
    if not any(licence.startswith(name) for name in ("MIT", "BSD", "Apache", "ISC", "MPL")):
        return reject(instance, "licence", f"licence {licence}")
    test_files = patch_files(instance["test_patch"])
    gold_files = patch_files(instance["patch"])
    if not test_files or not gold_files or set(test_files) & set(gold_files):
        return reject(instance, "patches", f"test files {test_files}, gold files {gold_files}")
    mined = instance.get("FAIL_TO_PASS") is None
    f2p, p2p_all = ([], []) if mined else (list(instance["FAIL_TO_PASS"]), list(instance["PASS_TO_PASS"]))
    run_files = sorted(file for file in test_files if file.endswith(".py") and re.search(r"(^|/)test", file)) if mined else \
        sorted({test_node_file(node) for node in f2p})
    if not run_files or any(not file.endswith(".py") for file in run_files):
        return reject(instance, "tests", f"test files to run {run_files}")
    p2p = [node for node in p2p_all if test_node_file(node) in run_files]
    if site is None:
        site = os.path.join(base, "runtime", "site")
        ok, detail = build_runtime(tree, site)
        if not ok:
            return reject(instance, "runtime", detail)
    add_generated(tree, site)
    # Base with the gold tests: every FAIL_TO_PASS fails.
    pristine = os.path.join(base, "pristine")
    shutil.copytree(tree, pristine, symlinks=True)

    def fresh(name, patches):
        directory = os.path.join(base, name)
        shutil.rmtree(directory, ignore_errors=True)
        shutil.copytree(pristine, directory, symlinks=True)
        for patch in patches:
            if not apply(directory, patch):
                return None
        return directory

    base_tree = fresh("base-run", [instance["test_patch"]])
    if base_tree is None:
        return reject(instance, "apply", "the test patch does not apply to the base")
    statuses, seconds, tail = run_tests(base_tree, site, run_files)
    if statuses is None:
        return reject(instance, "base-run", f"timeout after {seconds:.0f} s")
    if mined:
        # The fix decides which tests it makes pass: one gold run first.
        gold_tree = fresh("gold-probe", [instance["patch"], instance["test_patch"]])
        if gold_tree is None:
            return reject(instance, "apply", "the fix does not apply")
        gold, _, gold_tail = run_tests(gold_tree, site, run_files)
        if gold is None:
            return reject(instance, "gold-run", "timeout")
        f2p = sorted(node for node, status in gold.items() if passed(status) and not passed(statuses.get(node, "")))
        p2p = sorted(node for node, status in gold.items() if passed(status) and passed(statuses.get(node, "")))
        if not f2p:
            return reject(instance, "tests", "no test fails at the base and passes with the fix", tail=gold_tail[-1500:])
    else:
        # The dataset names tests as its log parser saw them, cut at the first space: match them to a gold run's ids.
        gold_tree = fresh("gold-probe", [instance["patch"], instance["test_patch"]])
        if gold_tree is None:
            return reject(instance, "apply", "the fix does not apply")
        gold, _, gold_tail = run_tests(gold_tree, site, run_files)
        if gold is None:
            return reject(instance, "gold-run", "timeout")
        wanted_f2p, wanted_p2p = set(f2p), set(p2p)
        f2p = sorted(node for node in gold if cut(node) in wanted_f2p)
        p2p = sorted(node for node in gold if cut(node) in wanted_p2p)
        unmatched = wanted_f2p - {cut(node) for node in f2p}
        if unmatched or not f2p:
            return reject(instance, "tests", f"FAIL_TO_PASS not found in a gold run: {sorted(unmatched)[:5]}", tail=gold_tail[-1500:])
    # The base three times: a FAIL_TO_PASS test that passes in any of them is unstable (dropped when mined, else the
    # task goes); PASS_TO_PASS must pass in all of them.
    base_runs = [statuses]
    for repetition in range(2):
        again, _, _ = run_tests(fresh(f"base-run-{repetition + 2}", [instance["test_patch"]]), site, run_files)
        if again is None:
            return reject(instance, "base-run", "timeout")
        base_runs.append(again)
    flaky = [node for node in f2p if any(passed(run.get(node, "")) for run in base_runs)]
    if flaky and not mined:
        return reject(instance, "base-run", f"FAIL_TO_PASS passing at the base: {flaky[:5]}")
    f2p = [node for node in f2p if node not in flaky]
    if not f2p:
        return reject(instance, "base-run", f"every FAIL_TO_PASS passes at the base in some run: {flaky[:5]}")
    base_p2p = {node for node in p2p if all(passed(run.get(node, "")) for run in base_runs)}
    # Gold three times: every FAIL_TO_PASS passes each time; PASS_TO_PASS kept only where it passes every time, base included.
    stable = set(base_p2p)
    durations = []
    for repetition in range(3):
        gold_tree = fresh(f"gold-run-{repetition}", [instance["patch"], instance["test_patch"]])
        if gold_tree is None:
            return reject(instance, "apply", "the gold patch does not apply")
        statuses, seconds, tail = run_tests(gold_tree, site, run_files)
        durations.append(seconds)
        if statuses is None:
            return reject(instance, "gold-run", f"timeout after {seconds:.0f} s")
        missing = [node for node in f2p if not passed(statuses.get(node, ""))]
        if missing:
            return reject(instance, "gold-run", f"FAIL_TO_PASS not passing with the gold patch (run {repetition + 1}): {missing[:5]}", tail=tail[-1500:])
        stable &= {node for node in p2p if passed(statuses.get(node, ""))}
    if max(durations) > TEST_TIMEOUT:
        return reject(instance, "duration", f"{max(durations):.0f} s")
    # Admitted: the repository archive (the base tree) and the runtime archive go to the asset cache.
    repository_tar = os.path.join(base, "repository.tar")
    deterministic_tar(pristine, repository_tar)
    runtime_tar = os.path.join(base, "runtime.tar")
    deterministic_tar(site, runtime_tar)
    if os.path.getsize(runtime_tar) > MAX_RUNTIME_BYTES:
        size = os.path.getsize(runtime_tar)
        shutil.rmtree(base, ignore_errors=True)
        return reject(instance, "runtime-size", f"runtime of {size // 1_000_000} MB, over {MAX_RUNTIME_BYTES // 1_000_000} MB")
    if mined and instance.get("problem_statement") is None:
        # The issue the fix closes: asked of the GitHub API only now, for a candidate the tests admit.
        issue = linked_issue(instance["repo"], instance["pull_number"])
        if issue is None:
            shutil.rmtree(base, ignore_errors=True)
            return reject(instance, "issue", f"pull request #{instance['pull_number']} closes no issue")
        instance = {**instance, **issue}
    record = {"instance_id": instance_id, "repo": instance["repo"], "source": instance.get("source", "pool"), "status": "admitted",
              "created_at": instance.get("created_at"), "base_commit": instance["base_commit"], "licence": licence,
              "problem_statement": instance["problem_statement"], "patch": instance["patch"], "test_patch": instance["test_patch"],
              "FAIL_TO_PASS": f2p, "PASS_TO_PASS": sorted(stable), "dropped_pass_to_pass": len(p2p) - len(stable), "test_files": run_files,
              "gold_files": gold_files, "difficulty": instance.get("difficulty") or {"files": len(gold_files)},
              "repository_sha256": store_asset(repository_tar), "repository_bytes": os.path.getsize(repository_tar),
              "runtime_sha256": store_asset(runtime_tar), "runtime_bytes": os.path.getsize(runtime_tar), "runtime_detail": detail,
              "gold_seconds": round(max(durations), 1), "pull_number": instance.get("pull_number"), "merged_at": instance.get("merged_at"),
              "issue_number": instance.get("issue_number"), "issue_created_at": instance.get("issue_created_at")}
    save_record(record)
    shutil.rmtree(base, ignore_errors=True)
    log(f"{instance_id}: admitted ({len(f2p)} FAIL_TO_PASS, {len(stable)} PASS_TO_PASS, {max(durations):.0f} s, "
        f"repository {record['repository_bytes'] // 1024} KB, runtime {record['runtime_bytes'] // 1024} KB)")
    return record


# Mining -----------------------------------------------------------------------------------------------------------------

def github(path):
    """One GitHub API call (unauthenticated: 60 an hour); waits for the window to reset when it is used up."""
    while True:
        request = urllib.request.Request(f"https://api.github.com{path}", headers={"Accept": "application/vnd.github+json", "User-Agent": "agenteval-er-builder"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 403 and error.headers.get("X-RateLimit-Remaining") == "0":
                wait = max(30, int(error.headers.get("X-RateLimit-Reset", "0")) - int(time.time()) + 5)
                log(f"GitHub API limit reached; waiting {wait} s")
                time.sleep(wait)
                continue
            if error.code == 404:
                return None
            raise


CLOSING = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+(?:https://github\.com/([\w.-]+/[\w.-]+)/issues/|#)(\d+)", re.I)


def linked_issue(repo, pull_number):
    """The issue a pull request closes (its body's closing keyword), as the task's problem statement."""
    pull = github(f"/repos/{repo}/pulls/{pull_number}")
    if not pull or not pull.get("merged_at"):
        return None
    for other, number in CLOSING.findall(pull.get("body") or ""):
        if other and other.lower() != repo.lower():
            continue
        issue = github(f"/repos/{repo}/issues/{number}")
        if issue and "pull_request" not in issue and (issue.get("body") or "").strip():
            return {"problem_statement": f"{issue['title']}\n\n{issue['body']}", "issue_number": int(number), "issue_created_at": issue["created_at"],
                    "merged_at": pull["merged_at"], "created_at": issue["created_at"]}
    return None


def is_test_path(path):
    return bool(re.search(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$", path))


def split_commit(mirror, commit):
    """(fix patch, test patch) of a first-parent commit: test files apart from the rest."""
    files = run(["git", "-C", mirror, "diff", "--name-only", f"{commit}^1", commit], WORK, check=True).stdout.split()
    tests = [path for path in files if is_test_path(path)]
    rest = [path for path in files if not is_test_path(path)]
    diff = lambda paths: run(["git", "-C", mirror, "diff", "--binary", f"{commit}^1", commit, "--", *paths], WORK, check=True).stdout if paths else ""
    return diff(rest), diff(tests), rest, tests


def mine(repo, since, limit):
    """Candidates from the merged fixes of a repository since a date: a first-parent commit naming its pull request,
    changing Python code and tests, with a modest fix. They are validated like pool instances, with a runtime built
    once for the repository at its newest commit."""
    mirror = os.path.join(WORK, "mirrors", repo.replace("/", "__"))
    if not os.path.isdir(mirror):
        os.makedirs(os.path.dirname(mirror), exist_ok=True)
        run(["git", "init", "--quiet", "--bare", mirror], WORK, check=True)
        run(["git", "-C", mirror, "remote", "add", "origin", f"https://github.com/{repo}.git"], WORK, check=True)
    fetched = run(["git", "-C", mirror, "fetch", "--quiet", f"--shallow-since={since}", "origin", "HEAD"], WORK, timeout=1800)
    if fetched.returncode != 0:
        # Some servers reject a date-bounded shallow fetch ("error processing shallow info"); a deep enough
        # depth-bounded one serves the same window (the log below is still filtered by --since).
        run(["git", "-C", mirror, "fetch", "--quiet", "--depth=3000", "origin", "HEAD"], WORK, timeout=1800, check=True)
    head = run(["git", "-C", mirror, "rev-parse", "FETCH_HEAD"], WORK, check=True).stdout.strip()
    runtime_root = os.path.join(WORK, "runtimes", repo.replace("/", "__"))
    site = os.path.join(runtime_root, "site")
    if not os.path.isdir(site):
        tree = tempfile.mkdtemp(prefix="er-runtime-", dir=os.path.join(WORK, "tmp"))
        export_tree(repo, head, tree)
        ok, detail = build_runtime(tree, site)
        shutil.rmtree(tree, ignore_errors=True)
        if not ok:
            shutil.rmtree(runtime_root, ignore_errors=True)
            log(f"{repo}: no runtime: {detail[:300]}")
            return []
        with open(os.path.join(runtime_root, "detail.txt"), "w") as handle:
            handle.write(detail)
    detail = open(os.path.join(runtime_root, "detail.txt")).read()
    lines = run(["git", "-C", mirror, "log", "--first-parent", f"--since={since}", "--format=%H%x09%cI%x09%s", head], WORK, check=True).stdout.splitlines()
    admitted = []
    tried = 0
    for line in lines:
        commit, date, subject = line.split("\t", 2)
        number = re.search(r"\(#(\d+)\)\s*$", subject) or re.search(r"^Merge pull request #(\d+)", subject)
        if not number:
            continue
        instance_id = f"{repo.replace('/', '__')}-{number.group(1)}"
        if os.path.exists(record_path(instance_id)):
            continue
        if run(["git", "-C", mirror, "cat-file", "-e", f"{commit}^1"], WORK).returncode != 0:
            continue
        patch, test_patch, rest, tests = split_commit(mirror, commit)
        python_rest = [path for path in rest if path.endswith(".py")]
        if not python_rest or not any(path.endswith(".py") for path in tests) or patch.count("\n") > 600:
            continue
        parent = run(["git", "-C", mirror, "rev-parse", f"{commit}^1"], WORK, check=True).stdout.strip()
        instance = {"instance_id": instance_id, "repo": repo, "source": "mined", "base_commit": parent, "fix_commit": commit, "pull_number": int(number.group(1)),
                    "merged_at": date, "created_at": date, "patch": patch, "test_patch": test_patch, "FAIL_TO_PASS": None, "PASS_TO_PASS": None,
                    "problem_statement": None, "difficulty": {"files": len(rest)}}
        os.makedirs(os.path.join(WORK, "mined"), exist_ok=True)
        with open(os.path.join(WORK, "mined", f"{instance_id}.json"), "w") as handle:
            json.dump(instance, handle)
        tried += 1
        record = prepare(instance, site=site, detail=detail)
        if record["status"] == "admitted":
            admitted.append(record)
        if len(admitted) >= limit or tried >= 4 * limit:
            break
    return admitted


# Package ----------------------------------------------------------------------------------------------------------------

SPLIT_SEED = "er-2026-10"
POOL_PER_REPO = 3


def records():
    folder = os.path.join(WORK, "records")
    return [json.load(open(os.path.join(folder, name), encoding="utf-8")) for name in sorted(os.listdir(folder)) if name.endswith(".json")]


def digest_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def link_asset(sha256, target):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.exists(target):
        os.remove(target)
    try:
        os.link(os.path.join(ASSETS, sha256), target)
    except OSError:
        shutil.copy(os.path.join(ASSETS, sha256), target)


def relabel(ids, runs):
    """Recomputes FAIL_TO_PASS and PASS_TO_PASS of admitted tasks from `runs` base and `runs` gold runs through the
    grader's own preparation and parser (whole test ids): FAIL_TO_PASS fail in every base run and pass in every gold
    run, PASS_TO_PASS pass in all; a test whose outcome varies between identical runs is in neither. A pool task keeps
    only the dataset's tests (matched by their ids cut at the first space). The first lists are kept as *_v1."""
    review = reviewed()
    for record in records():
        instance_id = record["instance_id"]
        if record["status"] != "admitted" or (ids and instance_id not in ids) or review.get(instance_id, {}).get("decision") == "exclude":
            continue
        first_f2p = record.setdefault("FAIL_TO_PASS_v1", record["FAIL_TO_PASS"])
        first_p2p = record.setdefault("PASS_TO_PASS_v1", record["PASS_TO_PASS"])
        outcomes, failure = {"base": [], "gold": []}, None
        with tempfile.TemporaryDirectory(prefix="er-relabel-", dir=os.path.join(WORK, "tmp")) as work:
            site = os.path.join(work, "site")
            os.makedirs(site)
            with tarfile.open(os.path.join(ASSETS, record["runtime_sha256"])) as tar:
                tar.extractall(site, filter="tar")
            runtime = {"mounts": [{"source": site, "target": "/runtime/site"}],
                       "env": {"PYTHONPATH": "{workspace}/repo/src:{workspace}/repo:/runtime/site", "PYTHONDONTWRITEBYTECODE": "1"}}
            for kind, change in (("base", ""), ("gold", record["patch"])):
                for index in range(runs):
                    one = os.path.join(work, f"{kind}-{index}")
                    os.makedirs(one)
                    repo, applied = grader.prepared_repository(one, os.path.join(ASSETS, record["repository_sha256"]), change, record["test_patch"])
                    statuses, tail = grader.run_tests(repo, record["test_files"], {"launcher": LAUNCHER}, runtime)
                    if (kind == "gold" and not applied) or tail == "timeout":
                        failure = f"{kind} run {index + 1}: {'timeout' if tail == 'timeout' else 'the fix does not apply'}"
                    outcomes[kind].append(statuses)
                    shutil.rmtree(one)
        if failure:
            log(f"{instance_id}: relabel failed ({failure}); record unchanged")
            continue
        nodes = set().union(*outcomes["base"], *outcomes["gold"])
        base = {node: [passed(run.get(node, "")) for run in outcomes["base"]] for node in nodes}
        gold = {node: [passed(run.get(node, "")) for run in outcomes["gold"]] for node in nodes}
        unstable = sorted(node for node in nodes if len(set(base[node])) > 1 or len(set(gold[node])) > 1)
        f2p = sorted(node for node in nodes if not any(base[node]) and all(gold[node]))
        p2p = sorted(node for node in nodes if all(base[node]) and all(gold[node]))
        if record["source"] == "pool":
            f2p = [node for node in f2p if cut(node) in set(first_f2p)]
            p2p = [node for node in p2p if cut(node) in set(first_p2p)]
        record["relabel"] = {"runs": runs, "parser": 2, "unstable": unstable[:200], "unstableCount": len(unstable),
                             "f2pBefore": len(record["FAIL_TO_PASS"]), "p2pBefore": len(record["PASS_TO_PASS"])}
        if not f2p:
            record.update({"status": "rejected", "stage": "relabel", "reason": "no FAIL_TO_PASS test is stable over the runs"})
        else:
            record.update({"FAIL_TO_PASS": f2p, "PASS_TO_PASS": p2p})
        save_record(record)
        log(f"{instance_id}: relabelled ({record['status']}): FAIL_TO_PASS {record['relabel']['f2pBefore']} -> {len(f2p)}, "
            f"PASS_TO_PASS {record['relabel']['p2pBefore']} -> {len(p2p)}, unstable {len(unstable)}")


def reviewed():
    """The reviewer's decisions per admitted task (private/review.json): {"decision": "keep" | "exclude", "reason": ...,
    "interface": [names the tests use, stated in the prompt], "dropTests": [tests left unchecked: exact ids or "re:<pattern>"]}."""
    path = os.path.join(HERE, "review.json")
    return json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {}


def package():
    """Writes the package from the admitted records: dev from the pool (at most three per repository), validation and
    holdout from mined fixes, dealt by repository with a fixed seed, validation first; no repository in two splits."""
    import random
    import grader
    review = reviewed()
    admitted = [record for record in records() if record["status"] == "admitted" and review.get(record["instance_id"], {}).get("decision") != "exclude"]
    unreviewed = sorted(record["instance_id"] for record in admitted if record["instance_id"] not in review)
    if unreviewed:
        raise SystemExit(f"admitted tasks without a review decision in private/review.json: {unreviewed}")
    pool = [record for record in admitted if record["source"] == "pool"]
    mined = [record for record in admitted if record["source"] == "mined"]
    dev_repos = {record["repo"] for record in pool}
    chosen = {}
    per_repo = {}
    for record in sorted(pool, key=lambda record: record["instance_id"]):
        if per_repo.get(record["repo"], 0) < POOL_PER_REPO:
            chosen[record["instance_id"]] = (record, "dev")
            per_repo[record["repo"]] = per_repo.get(record["repo"], 0) + 1
    repos = sorted({record["repo"] for record in mined} - dev_repos)
    random.Random(SPLIT_SEED).shuffle(repos)
    counts = {"validation": 0, "holdout": 0}
    for repo in repos:
        own = sorted((record for record in mined if record["repo"] == repo), key=lambda record: record["instance_id"])
        split = "validation" if counts["validation"] < 30 or counts["holdout"] >= counts["validation"] else "holdout"
        for record in own:
            chosen[record["instance_id"]] = (record, split)
        counts[split] += len(own)
    if os.path.isdir(os.path.join(PACKAGE, "items")):
        shutil.rmtree(os.path.join(PACKAGE, "items"))
    if os.path.isdir(os.path.join(PACKAGE, "assets")):
        shutil.rmtree(os.path.join(PACKAGE, "assets"))
    items, tasks, mounts = [], {}, {}
    for instance_id, (record, split) in sorted(chosen.items()):
        runtime = record["runtime_sha256"][:16]
        if runtime not in mounts:
            link_asset(record["runtime_sha256"], os.path.join(PACKAGE, "assets", f"runtime-{runtime}.tar"))
            mounts[runtime] = {"path": f"runtime/{runtime}", "archive": f"assets/runtime-{runtime}.tar",
                               "env": {"PYTHONPATH": "{workspace}/repo/src:{workspace}/repo:{mount}", "PYTHONDONTWRITEBYTECODE": "1"}}
        link_asset(record["repository_sha256"], os.path.join(PACKAGE, "assets", f"repo-{instance_id}.tar"))
        issue = record["problem_statement"].strip()
        prompt = f"## Issue ({record['repo']})\n\n{issue}\n\nThe repository is in `repo/`; this issue is also in `public/ISSUE.md`.\n"
        interface = review.get(instance_id, {}).get("interface", [])
        if interface:
            # Names the real fix introduced and its tests use, which the issue does not state (the review's decision):
            # they become part of the task, so that no hidden check needs a name the model could not know.
            prompt += "\n## Names the tests use\n\nThe project's tests for this issue use these names; give them exactly as listed:\n\n" + \
                "".join(f"- {line}\n" for line in interface)
        files = {f"items/{instance_id}/public/ISSUE.md": f"{issue}\n", f"items/{instance_id}/prompt.md": prompt}
        for path, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(PACKAGE, path)), exist_ok=True)
            with open(os.path.join(PACKAGE, path), "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        published = (record.get("issue_created_at") or record.get("created_at") or "")[:10]
        source = f"SWE-bench-Live {instance_id}" if record["source"] == "pool" else \
            f"mined: {record['repo']} pull request #{record['pull_number']}, issue #{record['issue_number']}, merged {record['merged_at'][:10]}"
        items.append({"id": instance_id, "level": record["source"], "files": [{"path": path, "sha256": digest_file(os.path.join(PACKAGE, path))} for path in sorted(files)],
                      "activeRequirementIds": ["REQ-FAIL-TO-PASS", "REQ-PASS-TO-PASS"], "split": split, "structure": f"repo:{record['repo']}",
                      "provenance": {"source": f"{source} @{record['base_commit'][:12]}", "published": published, "license": record["licence"], "exposure": "public"},
                      "repository": {"archive": f"assets/repo-{instance_id}.tar", "directory": "repo"}, "mounts": [f"runtime/{runtime}"]})
        # Tests the review leaves unchecked (behaviour the issue does not describe, or unstable): exact ids, or "re:<pattern>".
        dropped = review.get(instance_id, {}).get("dropTests", [])
        kept = lambda node: not any(node == entry or (entry.startswith("re:") and re.search(entry[3:], node)) for entry in dropped)
        tasks[instance_id] = {"repo": record["repo"], "base_commit": record["base_commit"], "test_patch": record["test_patch"], "gold_patch": record["patch"],
                              "FAIL_TO_PASS": [node for node in record["FAIL_TO_PASS"] if kept(node)],
                              "PASS_TO_PASS": [node for node in record["PASS_TO_PASS"] if kept(node)], "test_files": record["test_files"],
                              "gold_files": record["gold_files"], "difficulty": record.get("difficulty")}
        if not tasks[instance_id]["FAIL_TO_PASS"]:
            raise SystemExit(f"{instance_id}: no FAIL_TO_PASS left after the review's dropTests")
    with open(os.path.join(HERE, "tasks.json"), "w", encoding="utf-8") as handle:
        json.dump(tasks, handle, indent=1, sort_keys=True)
        handle.write("\n")
    summary = [{key: record.get(key) for key in ("instance_id", "repo", "source", "status", "stage", "reason", "created_at")} for record in records()]
    for entry in summary:
        if entry["reason"]:
            entry["reason"] = entry["reason"][:300]
        entry["split"] = chosen[entry["instance_id"]][1] if entry["instance_id"] in chosen else None
        if entry["instance_id"] in review:
            entry["review"] = review[entry["instance_id"]]
    with open(os.path.join(HERE, "selection.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, sort_keys=True)
        handle.write("\n")
    trusted = ["calibration.md", "card.md", "rubric.md", "private/builder.py", "private/grader.py", "private/review.json", "private/selection.json", "private/tasks.json"]
    trusted += sorted(f"assets/{name}" for name in os.listdir(os.path.join(PACKAGE, "assets")))
    manifest = {
        "schemaVersion": 2, "id": grader.TASK_ID, "version": grader.TASK_VERSION, "familyId": "er-live-repair", "capability": "engineering", "usage": "development",
        "source": {"kind": "open-source", "references": ["https://huggingface.co/datasets/SWE-bench-Live/SWE-bench-Live", "https://arxiv.org/abs/2505.23419",
                                                         "docs/design/v2/TASK_LIBRARY.md"]},
        "license": {"taskText": "Instruction project-authored; issues, repositories and tests from their projects under their licences (per item).",
                    "thirdPartyContent": ["SWE-bench-Live (MIT) for the dev instances", "each repository under its own permissive licence"]},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest_file(os.path.join(PACKAGE, "instruction.md"))}],
                  "trusted": [{"path": path, "sha256": digest_file(os.path.join(PACKAGE, path))} for path in trusted]},
        "requirements": [{"id": "REQ-FAIL-TO-PASS", "critical": True, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}", "checkIds": ["fail-to-pass"]},
                         {"id": "REQ-PASS-TO-PASS", "critical": True, "introducedAt": f"{grader.TASK_ID} {grader.TASK_VERSION}", "checkIds": ["pass-to-pass"]}],
        "tier": "core", "capabilities": ["engineering"], "card": "card.md",
        "scoreModel": {"primary": {"kind": "resolved"},
                       "groups": [{"id": "fail-to-pass", "weight": 0.7, "critical": True, "rule": "all", "checkIds": ["fail-to-pass"]},
                                  {"id": "pass-to-pass", "weight": 0.3, "critical": True, "rule": "all", "checkIds": ["pass-to-pass"]}],
                       "metrics": [{"id": "f2pShare", "unit": "share of FAIL_TO_PASS tests passing", "direction": "higher"},
                                   {"id": "p2pRegressions", "unit": "PASS_TO_PASS tests failing", "direction": "lower"},
                                   {"id": "patchApplied", "unit": "0 or 1", "direction": "higher"}]},
        "items": items,
        "runtime": {"mounts": [mounts[key] for key in sorted(mounts)]},
        "toolProfiles": ["workspace-augmented"],
        "grader": {"id": "er-swe-tests", "version": grader.GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"]},
        "environment": {"runtime": "Python 3.13", "dependencies": "per task, from wheels, in a read-only runtime mount; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    with open(os.path.join(PACKAGE, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    by = {}
    for item in items:
        key = (item["split"], item["structure"])
        by.setdefault(item["split"], set()).add(item["structure"])
    log(json.dumps({split: {"tasks": sum(1 for item in items if item["split"] == split), "repositories": len(repos_)} for split, repos_ in by.items()}))


def pool_rows():
    return [json.loads(line) for line in open(POOL, encoding="utf-8")]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    candidates = commands.add_parser("pool-candidates")
    candidates.add_argument("--since", default="2025-06")
    prep = commands.add_parser("prepare")
    prep.add_argument("instance_ids", nargs="+")
    commands.add_parser("package")
    relabelling = commands.add_parser("relabel")
    relabelling.add_argument("ids", nargs="*")
    relabelling.add_argument("--runs", type=int, default=5)
    mining = commands.add_parser("mine")
    mining.add_argument("repos", nargs="+")
    mining.add_argument("--since", required=True)
    mining.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    os.makedirs(os.path.join(WORK, "tmp"), exist_ok=True)
    if args.command == "pool-candidates":
        for row in pool_rows():
            if row["created_at"] >= args.since and row["difficulty"]["files"] >= 2 and len(patch_files(row["test_patch"])) <= 2 \
                    and 1 <= len(row["FAIL_TO_PASS"]) <= 20:
                print(json.dumps({"instance_id": row["instance_id"], "repo": row["repo"], "created_at": row["created_at"],
                                  "files": row["difficulty"]["files"], "f2p": len(row["FAIL_TO_PASS"])}))
    elif args.command == "prepare":
        rows = {row["instance_id"]: row for row in pool_rows()}
        for instance_id in args.instance_ids:
            if instance_id in rows:
                prepare({**rows[instance_id], "source": "pool"})
            else:
                path = os.path.join(WORK, "mined", f"{instance_id}.json")
                prepare(json.load(open(path, encoding="utf-8")))
    elif args.command == "package":
        package()
    elif args.command == "relabel":
        relabel(set(args.ids), args.runs)
    elif args.command == "mine":
        for repo in args.repos:
            try:
                admitted = mine(repo, args.since, args.limit)
                log(f"{repo}: {len(admitted)} admitted")
            except Exception as error:  # noqa: BLE001
                log(f"{repo}: mining failed: {str(error)[:300]}")


if __name__ == "__main__":
    main()
