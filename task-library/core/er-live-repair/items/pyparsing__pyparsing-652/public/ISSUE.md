`expr[..., upper_bound]` syntax can raise Recursion error if upper_bound is too large

`Literal("A")[..., 1000]` raises `RecursionError`, because the [] syntax generates a recursive expression of nested Optionals.

(Found while investigating #330)
