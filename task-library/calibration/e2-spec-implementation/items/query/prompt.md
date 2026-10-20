## Specification: query.py, a small query language

Write `query.py` at the workspace root. `python3 query.py <input.json>` reads tables and queries, runs every query, prints one JSON object with every query's result to standard output, then exits 0. Use only the Python standard library.

The language looks like SQL but differs from SQLite and other SQL databases on purpose. Wherever this specification and your knowledge of SQL disagree, follow the specification.

### Input and output

    {"tables": {"people": {"columns": ["id", "name", "age"], "rows": [[1, "Ada", 36], [2, "Bob", null]]}},
     "queries": ["SELECT name FROM people WHERE age > 30"]}
    -> {"results": [{"columns": ["name"], "rows": [["Ada"]]}]}

- `results` has one entry per query, in order: either `{"columns": [...], "rows": [[...], ...]}`, or `{"error": "<CODE>"}` when the query fails. A failing query does not affect the others.
- **Values** are integers, decimals, strings, booleans and `NULL`. In the input, a JSON integer is an integer, any other JSON number is a decimal, and `null` is `NULL`.
- **Output values.** An integer is a JSON integer. A decimal is rounded half-even to 6 decimal places: if the result is integral it is written as a JSON integer, and otherwise as a JSON number. Strings and booleans are written as JSON strings and booleans, and `NULL` as `null`.
- **Exact arithmetic.** Arithmetic on decimals is exact, and decimals are not binary floating point: `0.1 + 0.2` is exactly `0.3`.

### Grammar

Keywords and function names are case-insensitive. Table names, column names and aliases are case-insensitive too: `People.NAME` names `people.name`. Whitespace is free between tokens.

    query     := SELECT [DISTINCT] items FROM source { join } [WHERE expr] [GROUP BY expr {, expr}] [HAVING expr]
                 [ORDER BY order {, order}] [LIMIT integer [OFFSET integer]]
    items     := "*" | item {, item}
    item      := expr [AS name]
    source    := table [[AS] alias]
    join      := [LEFT] JOIN source ON expr
    order     := expr [ASC | DESC]
    expr      := or
    or        := and { OR and }
    and       := not { AND not }
    not       := NOT not | test
    test      := sum [ ("=" | "<>" | "<" | "<=" | ">" | ">=") sum
                     | IS [NOT] NULL | [NOT] IN "(" expr {, expr} ")" | [NOT] BETWEEN sum AND sum | [NOT] LIKE sum ]
    sum       := product { ("+" | "-" | "||") product }
    product   := unary { ("*" | "/" | "%") unary }
    unary     := "-" unary | atom
    atom      := number | string | TRUE | FALSE | NULL | column | call | case | "(" expr ")"
    column    := name | name "." name
    call      := function "(" [ "*" | [DISTINCT] expr {, expr} ] ")"
    case      := CASE WHEN expr THEN expr { WHEN expr THEN expr } [ELSE expr] END
    number    := digits [ "." digits ]          (no sign; "-" is the unary operator)
    string    := "'" { any character except "'" | "''" } "'"      ("''" is one quote)
    name      := a letter or "_", then letters, digits or "_", and not a keyword

The keywords are the words in capitals above. A query that does not match the grammar, or that has text left after it, fails with `PARSE_ERROR`.

### Evaluation

The clauses run in this order: `FROM` and joins, `WHERE`, `GROUP BY`, `HAVING`, the select items, `DISTINCT`, `ORDER BY`, then `LIMIT` and `OFFSET`.

- **Rows and joins.** `FROM` yields the table's rows in input order. `JOIN` pairs each row with each row of the joined table, in order (left rows outermost), and keeps the pairs whose `ON` condition is `TRUE`. `LEFT JOIN` also keeps each left row that matched nothing, once, with `NULL` for every column of the joined table.
- **Names.** A column is named `column` or `qualifier.column`, where the qualifier is the table's alias if it has one and its name otherwise. An unqualified name that matches columns of more than one table in the query is ambiguous.
- **WHERE and HAVING** keep the rows, or groups, whose condition is `TRUE`; `FALSE` and `NULL` drop them.
- **SELECT \*** yields every column of every table, in `FROM` and join order.
- **Column names in the result.** An item with `AS` has that name. An item that is a column has the column's name as stored in the table, without its qualifier. Any other item at position *k* (1-based) is named `colk`.
- **DISTINCT** keeps the first of any rows that are equal value by value. Here two `NULL`s are equal, and `1` equals `1.0`.

### Types and operators

- **Arithmetic** (`+ - * / %`, unary `-`) takes integers and decimals; booleans and strings give `TYPE_MISMATCH`.
  - Integer with integer gives an integer, except `/`, whose result is the exact quotient: `7 / 2` is `3.5` and `6 / 3` is the integer `2`.
  - Any decimal operand gives a decimal.
  - `%` takes integers only (a decimal gives `TYPE_MISMATCH`), and the result has the sign of the left operand: `-7 % 3` is `-1`.
  - Division or `%` by zero gives `DIVISION_BY_ZERO`.
  - `NULL` in arithmetic gives `NULL`, without any type check.
- **`||`** joins the text forms of its operands. A number's text form is its output value written in plain decimal notation (`2.5`, `0.000001`, `-3`), and a boolean's is `true` or `false`. `NULL` with `||` gives `NULL`.
- **Comparisons** give `TRUE`, `FALSE` or `NULL`. If either side is `NULL`, the result is `NULL`. Numbers compare by value (`1 = 1.0`). Strings compare by Unicode code points and case-sensitively. Booleans compare with booleans (`FALSE < TRUE`). Comparing values of different kinds (a number with a string, say) gives `TYPE_MISMATCH`.
- **`IS NULL` and `IS NOT NULL`** always give `TRUE` or `FALSE`.
- **`x IN (a, b, ...)`** is `TRUE` if `x` equals some item. Otherwise it is `NULL` if `x` or some item is `NULL`, and `FALSE` if neither is. Items are compared left to right with the comparison rules, so a mismatched kind gives `TYPE_MISMATCH`.
- **`x BETWEEN a AND b`** is `x >= a AND x <= b`.
- **`NOT IN`, `NOT BETWEEN` and `NOT LIKE`** are `NOT` of the positive form.
- **`x LIKE p`** takes strings, otherwise giving `TYPE_MISMATCH`; with `NULL` it gives `NULL`. It matches the whole string, where `%` matches any run of characters and `_` exactly one character. Unlike SQLite, matching is **case-sensitive**.
- **AND, OR and NOT** use three-valued logic, and their operands must be booleans or `NULL` (anything else is `TYPE_MISMATCH`). They evaluate the left operand first and skip the right one when the left decides: `FALSE AND ...` is `FALSE`, and `TRUE OR ...` is `TRUE`.
- **CASE** evaluates its conditions in order and returns the first branch whose condition is `TRUE`, else the `ELSE` value, else `NULL`. Only that branch is evaluated.

### Functions

| Function | Result |
| --- | --- |
| `UPPER(s)`, `LOWER(s)` | Case conversion of a string; `NULL` gives `NULL`; other kinds give `TYPE_MISMATCH`. |
| `LENGTH(s)` | The number of characters of a string; `NULL` gives `NULL`. |
| `ABS(x)` | The absolute value of a number. |
| `ROUND(x, n)` | `x` rounded half away from zero to `n` decimal places, where `n` is an integer from 0 to 6. An integer `x` stays an integer. |
| `COALESCE(a, b, ...)` | The first argument that is not `NULL`, evaluated left to right and stopping there; `NULL` if all are. |
| `COUNT(*)` | The number of rows in the group. |
| `COUNT(x)`, `SUM(x)`, `AVG(x)`, `MIN(x)`, `MAX(x)` | Aggregates over the group's non-`NULL` values of `x`. `COUNT` counts them. `SUM` of integers is an integer. `AVG` is the exact mean, a decimal unless it comes out integral. `SUM`, `AVG`, `MIN` and `MAX` of no values are `NULL`. `MIN` and `MAX` use the comparison rules. |
| `COUNT(DISTINCT x)`, `SUM(DISTINCT x)` | The same over distinct non-`NULL` values. |

A call with the wrong number of arguments, an unknown function, or `DISTINCT` or `*` outside the aggregates that allow them gives `PARSE_ERROR`.

### Grouping

- **With grouping.** A query has groups when it has `GROUP BY`, or when an aggregate appears in its select items or `HAVING`.
  - Rows with equal `GROUP BY` values form a group, with `NULL`s equal. Groups are ordered by their first row.
  - Without `GROUP BY`, all rows form one group, even when there are no rows: `SELECT COUNT(*) FROM t WHERE FALSE` gives one row, `[0]`.
- **Column rules.** In a grouped query, every column used in the select items, `HAVING` or `ORDER BY` outside an aggregate must appear as a `GROUP BY` expression, written as a plain column. Otherwise the query fails with `GROUPING_ERROR`.
- **Where aggregates may appear.** Aggregates are not allowed in `WHERE`, `GROUP BY` or join conditions, and may not be nested; either gives `GROUPING_ERROR`.
- **Clauses that need groups.** A query without groups that has `HAVING`, or an aggregate in `ORDER BY`, gives `GROUPING_ERROR`.

### Ordering and limits

- **What ORDER BY can name.** Each `ORDER BY` item is one of these:
  - an integer literal *k*, meaning the *k*-th result column; *k* must be from 1 to the number of result columns, otherwise the query fails with `PARSE_ERROR` (see the error order);
  - a name equal to a result column's `AS` name, meaning that column;
  - any other expression, evaluated per row (per group when grouped).
- **How rows are ordered.** `ASC` is the default.
  - Unlike SQLite, `NULL` sorts **after** every other value in `ASC`, and before every other value in `DESC`.
  - Rows that tie on every item keep their order.
  - Values of different kinds in one `ORDER BY` column give `TYPE_MISMATCH`.
- **LIMIT and OFFSET.** `LIMIT n OFFSET m` skips `m` rows, then keeps at most `n`.

### Errors and their order

The error codes are `PARSE_ERROR`, `UNKNOWN_TABLE`, `UNKNOWN_COLUMN`, `AMBIGUOUS_COLUMN`, `GROUPING_ERROR`, `TYPE_MISMATCH` and `DIVISION_BY_ZERO`. A query's error is found in this order:

1. `PARSE_ERROR`, for the whole query text.
2. Name errors, checked over the whole query before any row is read, clause by clause in the order of evaluation above, and left to right within a clause:
   - `UNKNOWN_TABLE`;
   - an `ORDER BY` integer literal outside 1 to the number of result columns: `PARSE_ERROR`;
   - `UNKNOWN_COLUMN` or `AMBIGUOUS_COLUMN`. An `ORDER BY` name that is a result column's `AS` name is not a column, but any other name is resolved, even in a `CASE` branch or an operand that evaluation would skip.
3. `GROUPING_ERROR`.
4. Evaluation errors (`TYPE_MISMATCH`, `DIVISION_BY_ZERO`), from evaluating the clauses in their order, rows in their order, and each expression left to right. Only what is evaluated can fail: a row that `WHERE` dropped is never selected, and a skipped operand or branch is never evaluated.

Deliver `query.py` and a short README.md. Test your implementation against your own cases. The hidden tests cover every rule above, and each rule area is scored separately.
