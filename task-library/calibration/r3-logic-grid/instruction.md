# Task: Logic Grid Puzzle (R3)

Solve the logic grid puzzle below. It has exactly one solution, which follows from the clues alone; no outside knowledge is needed. The workspace contains no further material.

## Answer

Emit one JSON object only, without Markdown fences:

    {"solution": {"1": {"<Attribute>": "<value>", ...}, "2": {...}, ...}}

- Give every house, keyed by its number as a string ("1" is the leftmost house), and every attribute of the puzzle in each house.
- Use attribute names and values exactly as listed in the puzzle.
- The answer is graded cell by cell. The puzzle counts as solved only when every cell is correct.
