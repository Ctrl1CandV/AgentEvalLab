# Task: Abstraction and Reasoning (AR)

Each task below shows a few examples, each an input grid and its output grid. The same rule turns every example input into its output. Find the rule and apply it to each test input.

A grid is a rectangle of cells, each holding a digit from 0 to 9 (the digits stand for colours). Grids are written one row per line, cells separated by spaces, from the top row down. An output grid may differ in size from its input; finding its size is part of the task.

## Answer

You may give two attempts for each test input. A test input counts as solved when one of its two attempts is exactly the expected output grid, size included. The task is solved when every test input is.

Emit one JSON object only, without Markdown fences:

    {"test": [{"attempt_1": [[...], ...], "attempt_2": [[...], ...]}, ...]}

- One entry per test input, in the order given.
- Each attempt is a grid as a list of rows, each row a list of integers from 0 to 9.
- `attempt_2` may be left out. Further attempts are ignored.
