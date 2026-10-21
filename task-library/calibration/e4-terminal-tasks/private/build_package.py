#!/usr/bin/env python3
"""Builds the E4 package: generated workspace files, the bisect culprit, and the manifest with every file hash.

Usage: python3 private/build_package.py   (run from the package directory)
Generation is seeded; the Git history uses fixed authors and dates, so its commit hashes are reproducible.
"""
import gzip
import hashlib
import json
import os
import pathlib
import py_compile
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(".")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bisect_item import history  # noqa: E402
from recover_item import history as lost_history  # noqa: E402
from migrate import data as migrate_data  # noqa: E402
from perf import data as perf_data  # noqa: E402
import grader  # noqa: E402
from codec_item import cases as codec_cases, lgz  # noqa: E402
from speedup_item import data as speedup_data  # noqa: E402
from compress_item import logdata as compress_data  # noqa: E402

VERSION = grader.TASK_VERSION
GRADER_VERSION = grader.GRADER_VERSION


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def generate():
    shutil.copy(HERE / "perf" / "original.py", ROOT / "items" / "perf" / "public" / "report.py")
    (ROOT / "items" / "perf" / "public" / "events.csv").write_text(perf_data.events(*perf_data.WORKSPACE), encoding="utf-8")
    database = ROOT / "items" / "migrate" / "public" / "shop.db"
    database.unlink(missing_ok=True)
    migrate_data.generated(str(database), *migrate_data.WORKSPACE)
    with tempfile.TemporaryDirectory() as scratch:
        repository = os.path.join(scratch, "pricing")
        culprit = history.build(repository)
        bundle = ROOT / "items" / "bisect" / "public" / "history.bundle"
        bundle.unlink(missing_ok=True)
        subprocess.run(["git", "bundle", "create", str(bundle.resolve()), "main"], cwd=repository, check=True, capture_output=True)
    (HERE / "bisect_item" / "culprit.txt").write_text(culprit + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory() as scratch:
        repository = os.path.join(scratch, "atlas-notes")
        answers = lost_history.build(repository)
        archive = ROOT / "items" / "recover" / "public" / "atlas-notes.tar"
        archive.parent.mkdir(parents=True, exist_ok=True)
        answers_path = HERE / "recover_item" / "answers.json"
        # Git's index records file times, so a new tar differs in bytes even when every object is the same: keep the
        # existing tar while the answers it encodes are unchanged.
        if archive.exists() and answers_path.exists() and json.loads(answers_path.read_text(encoding="utf-8")) == answers:
            generate_speedup()
            generate_compress()
            return generate_codec()
        with tarfile.open(archive, "w", format=tarfile.GNU_FORMAT) as tar:
            # Sorted entries, fixed times and owners: the archive's bytes depend only on the repository's contents.
            for path in sorted(pathlib.Path(repository).rglob("*")):
                info = tar.gettarinfo(str(path), arcname=str(path.relative_to(scratch)))
                info.mtime, info.uid, info.gid, info.uname, info.gname = 1790000000, 0, 0, "", ""
                if info.isfile():
                    with open(path, "rb") as handle:
                        tar.addfile(info, handle)
                else:
                    tar.addfile(info)
    (HERE / "recover_item" / "answers.json").write_text(json.dumps(answers, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    generate_speedup()
    generate_compress()
    generate_codec()


def generate_compress():
    """The gzip-only packlog.py as shipped and a sample log, gzipped with a fixed header so its bytes are reproducible."""
    public = ROOT / "items" / "compress" / "public"
    public.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "compress_item" / "baseline.py", public / "packlog.py")
    (public / "edge-sample.log.gz").write_bytes(gzip.compress(compress_data.events(*compress_data.SAMPLE), compresslevel=9, mtime=0))


def generate_speedup():
    """The slow report program as shipped and a sample day."""
    public = ROOT / "items" / "speedup" / "public"
    public.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "speedup_item" / "naive.py", public / "analyze.py")
    with open(public / "events-sample.csv", "w", encoding="utf-8", newline="") as handle:
        handle.write(speedup_data.events("speedup-sample", 20_000, 0.03))


def generate_codec():
    """The encoder as bytecode only (docstrings stripped, hash-based so the bytes are reproducible), samples, the archive."""
    public = ROOT / "items" / "codec" / "public"
    if public.exists():
        shutil.rmtree(public)
    (public / "samples").mkdir(parents=True)
    (public / "archive").mkdir()
    py_compile.compile(str(HERE / "codec_item" / "lgz.py"), cfile=str(public / "lgz.pyc"), dfile="lgz.py", optimize=2,
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH, doraise=True)
    for name, data in codec_cases.samples().items():
        (public / "samples" / name).write_bytes(data)
        (public / "samples" / f"{name}.lgz").write_bytes(lgz.encode(data))
    for name, data in codec_cases.archive().items():
        (public / "archive" / f"{name}.lgz").write_bytes(lgz.encode(data))


def main():
    generate()
    trusted = ["calibration.md", "rubric.md"] + sorted(str(path.relative_to(ROOT)) for path in (ROOT / "private").rglob("*")
                                                     if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc")
                                                     and not any(part.startswith(".") for part in path.parts))
    requirements, items = [], []
    for item, checks in grader.CHECKS.items():
        ids = [f"REQ-{item.upper()}-{check.upper()}" for check in checks]
        requirements += [{"id": requirement, "critical": True, "introducedAt": f"e4-terminal-tasks {VERSION}", "checkIds": [f"{item}-{check}"]}
                         for requirement, check in zip(ids, checks)]
        files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "items" / item).rglob("*") if path.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in path.parts))
        items.append({"id": item, "level": item, "files": [{"path": path, "sha256": digest(path)} for path in files], "activeRequirementIds": ids})
    manifest = {
        "schemaVersion": 1, "id": "e4-terminal-tasks", "version": VERSION, "familyId": "e4-terminal-tasks", "capability": "engineering", "usage": "development",
        "source": {"kind": "original-design", "references": ["docs/design/TASK_SET_V2.md"]},
        "license": {"taskText": "Original project-authored tasks, data, programs and checks.", "thirdPartyContent": []},
        "entryPoint": {"instruction": "instruction.md"},
        "files": {"public": [{"path": "instruction.md", "sha256": digest("instruction.md")}], "trusted": [{"path": path, "sha256": digest(path)} for path in trusted]},
        "requirements": requirements, "items": items, "toolProfiles": ["workspace-basic"],
        "grader": {"id": "e4-terminal-checks", "version": GRADER_VERSION, "entryPoint": "private/grader.py", "executable": "python3",
                   "args": ["{entryPoint}", "--request", "{request}", "--result", "{result}"]},
        "environment": {"runtime": "Python 3.13", "dependencies": "Python standard library; git, make, cc and coreutils from the host; no network", "network": False,
                        "runtimeCheck": {"executable": "python3", "args": ["--version"], "expectedSubstring": "Python 3.13."}},
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
