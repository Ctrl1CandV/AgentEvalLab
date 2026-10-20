"""The repository of the recover item: a rebased-then-deleted branch and two dropped stashes, with reflogs cleared
and nothing garbage-collected, so the lost commits survive only as unreachable objects.

build(directory) creates the repository with fixed authors and dates, so every hash is reproducible, and returns the
answers: the rebased branch tip, its tree's files, the last dropped stash and its RELEASE.md, and the decoys (the
pre-rebase tip and the stash dropped first).
"""
import os
import shutil
import subprocess

NOTES_V1 = '"""Notes: add, list."""\n\nNOTES = []\n\n\ndef add(text):\n    NOTES.append(text)\n\n\ndef listing():\n    return list(NOTES)\n'
NOTES_V2 = NOTES_V1.replace('"""Notes: add, list."""', '"""Notes: add, list, count."""') + "\n\ndef count():\n    return len(NOTES)\n"
NOTES_V3 = NOTES_V2.replace("NOTES = []", "NOTES = []  # in insertion order")
SEARCH_V1 = 'from notes import NOTES\n\n\ndef search(word):\n    return [note for note in NOTES if word in note]\n'
SEARCH_V2 = SEARCH_V1.replace("if word in note]", "if word.lower() in note.lower()]")
SEARCH_V3 = ('from notes import NOTES\n\n\ndef search(word):\n    """Matching notes, most recent first."""\n'
             '    return [note for note in reversed(NOTES) if word.lower() in note.lower()]\n')
RELEASE = "# Release notes\n\n## 1.0\n\n- Notes can be added and listed.\n"
RELEASE_OLD_STASH = RELEASE + "\n## 1.1 (draft)\n\n- Counting notes.\n"
RELEASE_STASH = RELEASE + "\n## 1.1\n\n- Counting notes.\n- Search, case-insensitive, most recent first.\n"


def build(directory):
    os.makedirs(directory)
    clock = [0]

    def git(*args):
        clock[0] += 1
        when = f"2026-09-{1 + clock[0] // 24:02d}T{clock[0] % 24:02d}:15:00+00:00"
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory, "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_AUTHOR_NAME": "Ines Varga", "GIT_AUTHOR_EMAIL": "ines@atlas.example", "GIT_COMMITTER_NAME": "Ines Varga",
               "GIT_COMMITTER_EMAIL": "ines@atlas.example", "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
        return subprocess.run(["git", *args], cwd=directory, env=env, check=True, capture_output=True, text=True).stdout.strip()

    def write(path, text):
        os.makedirs(os.path.join(directory, os.path.dirname(path)) or directory, exist_ok=True)
        with open(os.path.join(directory, path), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def commit(message, files):
        for path, text in files.items():
            write(path, text)
        git("add", "-A")
        git("commit", "-q", "-m", message)
        return git("rev-parse", "HEAD")

    git("init", "-q", "-b", "main")
    git("config", "gc.auto", "0")
    commit("Start atlas-notes", {"README.md": "# atlas-notes\n\nA tiny note keeper.\n", "src/notes.py": NOTES_V1, "RELEASE.md": RELEASE})
    commit("Add a contributing guide", {"CONTRIBUTING.md": "Open a pull request against main.\n"})
    git("checkout", "-q", "-b", "search")
    commit("search: find notes by word", {"src/search.py": SEARCH_V1})
    commit("search: ignore case", {"src/search.py": SEARCH_V2})
    commit("search: rank results by recency", {"src/search.py": SEARCH_V3})
    git("checkout", "-q", "main")
    commit("notes: count notes", {"src/notes.py": NOTES_V2})
    commit("notes: document insertion order", {"src/notes.py": NOTES_V3})
    git("checkout", "-q", "search")
    old_tip = git("rev-parse", "HEAD")
    git("rebase", "-q", "main")
    tip = git("rev-parse", "HEAD")
    git("checkout", "-q", "main")
    git("branch", "-q", "-D", "search")
    write("RELEASE.md", RELEASE_OLD_STASH)
    git("stash", "push", "-q", "-m", "release notes")
    old_stash = git("rev-parse", "stash@{0}")
    git("stash", "drop", "-q")
    write("RELEASE.md", RELEASE_STASH)
    git("stash", "push", "-q", "-m", "release notes")
    stash = git("rev-parse", "stash@{0}")
    git("stash", "drop", "-q")
    shutil.rmtree(os.path.join(directory, ".git", "logs"), ignore_errors=True)
    for name in ("ORIG_HEAD",):
        path = os.path.join(directory, ".git", name)
        if os.path.exists(path):
            os.remove(path)
    files = {"README.md": "# atlas-notes\n\nA tiny note keeper.\n", "CONTRIBUTING.md": "Open a pull request against main.\n", "RELEASE.md": RELEASE,
             "src/notes.py": NOTES_V3, "src/search.py": SEARCH_V3}
    return {"search": tip, "files": files, "stash": stash, "release": RELEASE_STASH, "decoys": {"search": old_tip, "stash": old_stash}}
