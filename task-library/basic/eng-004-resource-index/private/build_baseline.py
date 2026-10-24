#!/usr/bin/env python3
"""Builds eng-004's baseline repository from private/baseline-source and writes baseline.bundle.

Usage: python3 private/build_baseline.py   (from the package directory). Fixed authors and dates make the commit
hashes reproducible; the script prints the baseline commit, which manifest.json pins.

The original baseline (commit 3b43f3c) was a Git link to a repository that is not available. This rebuild follows
the public contract and the reference variants: index and JSON export work, CSV export does not quote or use CRLF,
and there is no search command.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PACKAGE = HERE.parent
SOURCE = HERE / "baseline-source"
HISTORY = [
    ("2026-03-02T10:00:00+00:00", "Add the resource index command", ["README.md", "package.json", "src/types.ts", "src/catalog.ts", "src/index.ts"]),
    ("2026-04-14T15:30:00+00:00", "Add JSON and CSV export", ["src/export.ts", "src/cli.ts", "tests/baseline.test.mjs"]),
]


def git(directory, *args, when=None):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(directory), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "Resource Index Team", "GIT_AUTHOR_EMAIL": "index@example.org",
           "GIT_COMMITTER_NAME": "Resource Index Team", "GIT_COMMITTER_EMAIL": "index@example.org"}
    if when:
        env.update({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    return subprocess.run(["git", *args], cwd=directory, env=env, check=True, capture_output=True, text=True).stdout.strip()


def main():
    with tempfile.TemporaryDirectory() as scratch:
        repository = pathlib.Path(scratch) / "resource-index"
        repository.mkdir()
        git(repository, "init", "-q", "-b", "main")
        for when, message, paths in HISTORY:
            for path in paths:
                target = repository / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(SOURCE / path, target)
                os.chmod(target, 0o644)
            git(repository, "add", *paths)
            git(repository, "commit", "-q", "-m", message, when=when)
        assert sorted(str(path.relative_to(SOURCE)) for path in SOURCE.rglob("*") if path.is_file()) == \
            sorted(path for _, _, paths in HISTORY for path in paths), "every source file belongs to the history"
        commit = git(repository, "rev-parse", "HEAD")
        bundle = PACKAGE / "baseline.bundle"
        bundle.unlink(missing_ok=True)
        git(repository, "bundle", "create", str(bundle), "main")
    print(commit)


if __name__ == "__main__":
    main()
