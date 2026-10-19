## Task: make the activity report fast

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

`report.py` turns an events export into a short activity report: `python3 report.py events.csv > report.txt`. It is correct but far too slow. On the 40,000-line `events.csv` in the workspace it takes several seconds, and production exports are much larger.

Make `report.py` fast. The rewritten script must:

- produce **byte-identical** output to the current script for every input, including the oddities that the current script tolerates (comments, blank and repeated header lines, malformed rows, unusual amounts);
- process an export of 60,000 lines in under 2 seconds, including Python's start-up;
- keep the same interface and use only the Python standard library.

Commands you run are stopped after 10 seconds, so the current script may not finish on the full `events.csv`; use smaller samples to compare outputs. Deliver the new `report.py` at the workspace root.
