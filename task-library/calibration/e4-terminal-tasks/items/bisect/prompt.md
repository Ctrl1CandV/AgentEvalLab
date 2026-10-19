## Task: find and undo a pricing regression

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

`history.bundle` in the workspace is a Git bundle of the `pricing` repository (clone it with `git clone history.bundle repo`). Customers report that orders of exactly 100 items no longer get the 5% bulk discount, while orders of 101 items or more still do. The discount used to apply from 100 items.

1. Find the commit that introduced this regression. Write its full 40-character hash, and nothing else, to `culprit.txt` at the workspace root.
2. Write `fixed/pricing.py`: the repository's current `pricing.py` with this regression undone. Undo only the regression. Every other change in the history, including any other change made in the same commit, is intended and must keep working.

Nothing needs to be committed; only `culprit.txt` and `fixed/pricing.py` are checked.
