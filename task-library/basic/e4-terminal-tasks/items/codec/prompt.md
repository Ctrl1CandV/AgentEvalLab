## Task: decode logs whose decompressor was lost

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

The logs in `archive/` were compressed with our in-house tool `lgz`. Its source code and its documentation are lost, and it never had a decompressor. Only the compiled module survives: `lgz.pyc`, CPython 3.13 bytecode. `python3 lgz.pyc INPUT OUTPUT` still compresses the file INPUT into OUTPUT. `samples/` holds a few logs with their compressed forms (`<name>` and `<name>.lgz`).

Deliver:

1. **`decode.py`**: `python3 decode.py INPUT OUTPUT` writes to OUTPUT the exact original bytes of any file INPUT that `lgz.pyc` produced. It will be run on other compressed logs, which may use any feature of the format.
2. **`restored/<name>`**: the original of each `archive/<name>.lgz`.

Use only the Python standard library.
