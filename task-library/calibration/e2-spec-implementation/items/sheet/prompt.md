## Specification: sheet.py, a small spreadsheet evaluator

Write `sheet.py` at the workspace root. `python3 sheet.py <input.json>` reads a sheet, evaluates every cell, and prints one JSON object with the value of every cell to standard output, then exits 0. Use only the Python standard library.

### Input

    {"cells": {"A1": "5", "B1": "=A1*2", "C1": "hello"}}

- Cell names are one column letter `A`–`Z` and a row number `1`–`99`, such as `B12`. Input names are always valid and upper-case.
- Every cell's content is a string. A cell that is absent from the input is empty.

### Cell content

- An empty string is an empty cell.
- A string that starts with `=` is a formula (see below).
- Otherwise, a string matching `^-?[0-9]+(\.[0-9]+)?$` is a number. Any other string is text, kept exactly as written.

### Formulas

Grammar, with whitespace allowed between tokens:

    expression := comparison
    comparison := concat [ ("=" | "<>" | "<" | "<=" | ">" | ">=") concat ]     (at most one comparison)
    concat     := additive { "&" additive }
    additive   := term { ("+" | "-") term }
    term       := power { ("*" | "/") power }
    power      := unary [ "^" power ]           (right-associative: 2^3^2 = 2^9 = 512)
    unary      := "-" unary | primary            (unary minus binds tighter than ^: -2^2 = 4)
    primary    := number | string | reference | function | "(" expression ")"
    number     := [0-9]+ ( "." [0-9]+ )?
    string     := '"' any characters except '"' '"'
    reference  := column letter + row number, letters in any case (a1 = A1)
    function   := name "(" [ argument { "," argument } ] ")"   (names in any case)
    argument   := range | expression
    range      := reference ":" reference        (only allowed as a function argument)

A formula that does not match this grammar evaluates to the error `#PARSE!`. That includes `=` with nothing after it, unbalanced parentheses, a range outside a function argument, and an unknown function name.

### Values and types

A value is a number, a text, a boolean (`TRUE` or `FALSE`), empty, or an error.

- **Arithmetic** (`+ - * / ^` and unary `-`) needs numbers.
  - An empty operand counts as 0, and a boolean counts as 1 or 0.
  - A text operand gives `#VALUE!`.
  - Division by zero gives `#DIV/0!`.
  - A result that is not a finite number, such as `(-8)^0.5`, gives `#NUM!`.
- **`&`** concatenates the text forms of its operands.
  - A number's text form is its output form (see Output).
  - Booleans become `TRUE` or `FALSE`, and empty becomes "".
- **Comparisons** return a boolean.
  - Two numbers compare numerically. Two texts compare by Unicode code points and are case-sensitive.
  - An empty operand counts as 0 when the other side is a number, as "" when the other side is text, and as 0 when both are empty.
  - A number compared with a text, or any comparison involving a boolean, gives `#VALUE!`.
- **References.** A reference evaluates to the referenced cell's value. A reference to a row outside 1–99 gives `#REF!`, for example `A100` or `A0`.

### Functions

| Function | Result |
| --- | --- |
| `SUM`, `MIN`, `MAX`, `AVERAGE`, `COUNT` | Take any number of arguments, each a range or an expression. Collect the numbers: from a range, only the cells whose value is a number (empty, text and boolean cells in a range are ignored); from an expression argument, its value, which must be a number or a boolean (counted as 1 or 0); an empty expression value is ignored, and a text expression value gives `#VALUE!`. `SUM` of nothing is 0. `MIN` and `MAX` of nothing are 0. `AVERAGE` of nothing is `#DIV/0!`. `COUNT` counts the collected numbers. |
| `IF(condition, then, else)` | Exactly three expression arguments; any other number of arguments, or a range argument, is `#PARSE!`. The condition must be a boolean or a number (non-zero is true); text or empty gives `#VALUE!`. Only the chosen branch is evaluated, so an error in the other branch has no effect. |

A range such as `A1:B3` covers the rectangle between its two corners. The corners may be given in any order, so `B3:A1` covers the same cells. A range with an out-of-bounds row gives `#REF!`.

### Errors

The errors are `#PARSE!`, `#VALUE!`, `#DIV/0!`, `#NUM!`, `#REF!` and `#CYCLE!`.

- When an operator or a function meets an error operand or argument, it returns that error without evaluating further.
- Operands are evaluated left to right, and the first error met wins.
- An operator evaluates all its operands before applying its own type rules. So `="x"+1/0` is `#DIV/0!`: the error operand takes precedence over the `#VALUE!` that the text operand would cause.
- A function, by contrast, handles its arguments one at a time, left to right. A text expression argument gives `#VALUE!` as soon as it is reached, before later arguments are evaluated, so `=SUM("x", 1/0)` is `#VALUE!`. For a function, arguments are evaluated left to right, and a range argument checks its cells in row-major order (row by row, columns left to right).
- **Dependencies are dynamic.** Only references that are actually evaluated count as dependencies. A reference in an `IF` branch that is not taken creates no dependency, and neither does a reference that is skipped because an earlier operand or argument was already an error.
- **Cycles.** A cell that, through these dependencies, needs its own value while it is being evaluated is in a cycle. Every cell in a cycle has the value `#CYCLE!`. A cell outside the cycle that references a cycle cell gets `#CYCLE!` through normal error propagation.

### Output

Print one JSON object whose keys are every cell present in the input:

- a number as a JSON number, rounded to 9 decimal places, and written as an integer when the rounded value is integral (`10.0` → `10`, `0.1+0.2` → `0.3`);
- text as a JSON string;
- a boolean as JSON `true` or `false`;
- an empty cell as `null`;
- an error as its JSON string, for example `"#DIV/0!"`.

Key order does not matter. A formula cell whose result is a reference to an empty cell is `null`.

### Examples

    {"cells": {"A1": "2", "A2": "=A1^3^2", "A3": "=-A1^2", "A4": "=A9+1"}}
    -> {"A1": 2, "A2": 512, "A3": 4, "A4": 1}

    {"cells": {"A1": "=B1", "B1": "=A1", "C1": "=IF(1, 5, A1)", "D1": "=IF(0, 5, A1)"}}
    -> {"A1": "#CYCLE!", "B1": "#CYCLE!", "C1": 5, "D1": "#CYCLE!"}

Deliver `sheet.py` and a short README.md. Test your implementation against your own cases. The hidden tests cover every rule above, and each one is scored separately.
