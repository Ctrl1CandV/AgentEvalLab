## Task: recover lost work from a Git repository

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

`atlas-notes.tar` holds a copy of the `atlas-notes` Git repository (unpack it with `tar xf atlas-notes.tar`). Two pieces of work were lost in it:

- **The `search` branch.** It held the finished search feature, three commits ending with "search: rank results by recency". Shortly before it was deleted, it had been rebased onto `main`; the rebased branch is the one that matters.
- **The release notes.** A draft of `RELEASE.md` was stashed and the stash dropped. The draft was stashed twice; the stash dropped last is the one that matters.

Reflogs were cleared afterwards, but nothing has been garbage-collected.

Deliver, in a directory `recovered/`:

1. `recovered/search.txt`: the full 40-character hash of the rebased branch's last commit, and nothing else.
2. `recovered/search/`: every file of that commit's tree, at the same paths and with the same contents, and no other files.
3. `recovered/stash.txt`: the full hash of the last dropped stash's commit, and nothing else.
4. `recovered/RELEASE.md`: `RELEASE.md` as stashed in that stash.
