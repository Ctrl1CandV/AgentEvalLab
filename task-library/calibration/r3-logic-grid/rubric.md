# Rubric: R3 Logic Grid

Each item is one generated puzzle with a unique solution and a minimal clue set: removing any single clue admits a second solution. Levels differ by grid size: L1 is 4 houses by 4 attributes, up to L5 at 8 by 8.

## Checks

- One critical check per cell (house, attribute). Attribute names match case-insensitively; values match exactly after trimming and ignoring case.
- The trial score is the fraction of cells correct (cell accuracy). The item is resolved only when every cell is correct (puzzle accuracy).
- `answer-format` (non-critical) passes when the answer is one JSON object, as instructed. If the answer is not one JSON object, it is recovered when exactly one JSON object can be found in it: the only fenced code block that holds one, or else the only top-level object in surrounding prose. With no candidate, or with several, nothing is recovered. A recovered answer is graded on its content and loses 20% of its score. An answer that cannot be parsed fails every cell.

## Not scored

The reasoning shown, its length, and the order of keys are not scored.
