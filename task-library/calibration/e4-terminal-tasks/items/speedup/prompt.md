## Task: make the nightly report fast

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

`analyze.py` prints the nightly traffic report for a day of request events: `python3 analyze.py events.csv`. Its output is correct, but it is far too slow for production days of several hundred thousand events. `events-sample.csv` is a sample day.

Make `analyze.py` as fast as you can while keeping its output **byte for byte the same for every input**. That includes the rows it skips and the way it reads timestamps, user names and paths; the dashboards depend on them. Use only the Python standard library, and one process with one thread.

Hidden checks run your `analyze.py` on other days, one at a time on one CPU core:

- `small`, `quirks`, `large`: it must print exactly what the original prints, on a normal day, on a day full of malformed and unusual rows, and on a day of 200,000 events. Only the quirks day has malformed rows.
- `speed-8`, `speed-3`, `speed-1.5`, `speed-1.1`, `speed-0.75`: on the day of 200,000 events, it must take at most 8, 3, 1.5, 1.1 and 0.75 times as long as our own optimised version (best of three runs each). These need the normal and large outputs right.
- The output checks count only once `speed-8` passes, so the original as shipped earns nothing.
