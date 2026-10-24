## Task a1-6f473927

### Examples

Example 1, input (10 rows, 5 columns):
0 0 0 0 0
0 0 0 0 2
0 0 0 2 0
0 0 2 0 2
0 2 2 2 2
0 0 0 0 2
0 0 2 2 0
0 0 0 0 2
0 0 0 2 2
0 0 0 0 0

Example 1, output (10 rows, 10 columns):
0 0 0 0 0 8 8 8 8 8
0 0 0 0 2 0 8 8 8 8
0 0 0 2 0 8 0 8 8 8
0 0 2 0 2 0 8 0 8 8
0 2 2 2 2 0 0 0 0 8
0 0 0 0 2 0 8 8 8 8
0 0 2 2 0 8 0 0 8 8
0 0 0 0 2 0 8 8 8 8
0 0 0 2 2 0 0 8 8 8
0 0 0 0 0 8 8 8 8 8

Example 2, input (8 rows, 6 columns):
2 0 0 0 0 0
2 2 2 0 0 0
0 0 2 0 0 0
0 2 2 2 0 0
0 0 2 2 0 0
2 2 0 0 0 0
2 2 2 2 2 0
2 0 0 0 0 0

Example 2, output (8 rows, 12 columns):
8 8 8 8 8 0 2 0 0 0 0 0
8 8 8 0 0 0 2 2 2 0 0 0
8 8 8 0 8 8 0 0 2 0 0 0
8 8 0 0 0 8 0 2 2 2 0 0
8 8 0 0 8 8 0 0 2 2 0 0
8 8 8 8 0 0 2 2 0 0 0 0
8 0 0 0 0 0 2 2 2 2 2 0
8 8 8 8 8 0 2 0 0 0 0 0

Example 3, input (3 rows, 3 columns):
0 2 0
0 2 2
0 0 2

Example 3, output (3 rows, 6 columns):
0 2 0 8 0 8
0 2 2 0 0 8
0 0 2 0 8 8

Example 4, input (3 rows, 3 columns):
2 2 0
2 0 0
2 2 0

Example 4, output (3 rows, 6 columns):
8 0 0 2 2 0
8 8 0 2 0 0
8 0 0 2 2 0

### Test inputs

Test input 1 (12 rows, 6 columns):
0 0 0 0 0 0
0 0 0 0 0 2
0 0 0 0 2 0
0 0 0 2 2 2
0 0 0 0 2 2
0 2 2 2 0 0
0 0 0 2 2 2
0 0 0 0 0 2
0 0 0 0 2 2
0 0 0 0 2 2
0 0 0 0 0 0
0 0 0 0 0 0

Answer for the 1 test input above, in order.
