#!/usr/bin/env python3
"""Reference implementation of the E2 query specification (items/query/prompt.md). Standard library only.

Integers are Python ints and decimals are Fractions, so a decimal stays a decimal even when integral (which matters
for %), and decimal arithmetic is exact.
"""
import json
import re
import sys
from decimal import Decimal
from fractions import Fraction
from functools import cmp_to_key

KEYWORDS = {"SELECT", "DISTINCT", "FROM", "WHERE", "GROUP", "BY", "HAVING", "ORDER", "ASC", "DESC", "LIMIT", "OFFSET", "AS", "LEFT", "JOIN", "ON",
            "OR", "AND", "NOT", "IS", "NULL", "IN", "BETWEEN", "LIKE", "TRUE", "FALSE", "CASE", "WHEN", "THEN", "ELSE", "END"}
AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
SCALARS = {"UPPER": 1, "LOWER": 1, "LENGTH": 1, "ABS": 1, "ROUND": 2}
TOKEN = re.compile(r"\s*(?:(?P<number>[0-9]+(?:\.[0-9]+)?)|(?P<string>'(?:[^']|'')*')|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<op><>|<=|>=|\|\||[-+*/%=<>(),.]))")


class QueryError(Exception):
    def __init__(self, code):
        self.code = code


# Values -------------------------------------------------------------------------------------------------------------

def kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, Fraction)):
        return "number"
    return "string"


def norm(value):
    """A key under which equal values (1 and 1.0, two NULLs) collide."""
    k = kind(value)
    return (k, Fraction(value)) if k == "number" else (k, value)


def rounded(value):
    """A decimal rounded half-even to 6 places, as an int if integral."""
    result = Fraction(round(value * 10**6), 10**6)
    return int(result) if result.denominator == 1 else result


def output(value):
    if isinstance(value, Fraction):
        value = rounded(value)
        return value if isinstance(value, int) else float(value)
    return value


def text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Fraction):
        value = rounded(value)
        if isinstance(value, int):
            return str(value)
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    return str(value)


# Parsing ------------------------------------------------------------------------------------------------------------

def tokenize(source):
    tokens, index = [], 0
    while index < len(source):
        if source[index:].strip() == "":
            break
        match = TOKEN.match(source, index)
        if not match:
            raise QueryError("PARSE_ERROR")
        index = match.end()
        group = match.lastgroup
        value = match.group(group)
        if group == "name" and value.upper() in KEYWORDS:
            tokens.append(("kw", value.upper()))
        else:
            tokens.append((group, value))
    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens, self.position = tokens, 0

    def peek(self, offset=0):
        index = self.position + offset
        return self.tokens[index] if index < len(self.tokens) else (None, None)

    def at(self, *keywords):
        return self.peek()[0] == "kw" and self.peek()[1] in keywords

    def at_op(self, *ops):
        return self.peek()[0] == "op" and self.peek()[1] in ops

    def take(self, kind=None, value=None):
        token = self.peek()
        if token[0] is None or (kind and token[0] != kind) or (value is not None and token[1] != value):
            raise QueryError("PARSE_ERROR")
        self.position += 1
        return token

    def keyword(self, word):
        return self.take("kw", word)

    def query(self):
        self.keyword("SELECT")
        distinct = bool(self.at("DISTINCT")) and bool(self.take())
        if self.at_op("*"):
            self.take()
            items = "*"
        else:
            items = [self.item()]
            while self.at_op(","):
                self.take()
                items.append(self.item())
        self.keyword("FROM")
        sources = [self.source()]
        joins = []
        while self.at("LEFT", "JOIN"):
            left = self.at("LEFT")
            if left:
                self.take()
            self.keyword("JOIN")
            sources.append(self.source())
            self.keyword("ON")
            joins.append((left, self.expr()))
        query = {"distinct": distinct, "items": items, "sources": sources, "joins": joins, "where": None, "group": [], "having": None,
                 "order": [], "limit": None, "offset": 0}
        if self.at("WHERE"):
            self.take()
            query["where"] = self.expr()
        if self.at("GROUP"):
            self.take()
            self.keyword("BY")
            query["group"] = [self.expr()]
            while self.at_op(","):
                self.take()
                query["group"].append(self.expr())
        if self.at("HAVING"):
            self.take()
            query["having"] = self.expr()
        if self.at("ORDER"):
            self.take()
            self.keyword("BY")
            query["order"] = [self.order()]
            while self.at_op(","):
                self.take()
                query["order"].append(self.order())
        if self.at("LIMIT"):
            self.take()
            query["limit"] = int(self.integer())
            if self.at("OFFSET"):
                self.take()
                query["offset"] = int(self.integer())
        if self.position != len(self.tokens):
            raise QueryError("PARSE_ERROR")
        return query

    def integer(self):
        kind_, value = self.take("number")
        if "." in value:
            raise QueryError("PARSE_ERROR")
        return value

    def item(self):
        expr = self.expr()
        if self.at("AS"):
            self.take()
            return expr, self.take("name")[1]
        return expr, None

    def source(self):
        table = self.take("name")[1]
        alias = None
        if self.at("AS"):
            self.take()
            alias = self.take("name")[1]
        elif self.peek()[0] == "name":
            alias = self.take()[1]
        return table, alias

    def order(self):
        expr = self.expr()
        descending = False
        if self.at("ASC", "DESC"):
            descending = self.take()[1] == "DESC"
        return expr, descending

    def expr(self):
        node = self.and_()
        while self.at("OR"):
            self.take()
            node = ("or", node, self.and_())
        return node

    def and_(self):
        node = self.not_()
        while self.at("AND"):
            self.take()
            node = ("and", node, self.not_())
        return node

    def not_(self):
        if self.at("NOT"):
            self.take()
            return ("not", self.not_())
        return self.test()

    def test(self):
        left = self.sum()
        if self.at_op("=", "<>", "<", "<=", ">", ">="):
            op = self.take()[1]
            return ("cmp", op, left, self.sum())
        if self.at("IS"):
            self.take()
            negated = bool(self.at("NOT")) and bool(self.take())
            self.keyword("NULL")
            return ("isnull", left, negated)
        negated = False
        if self.at("NOT") and self.peek(1)[0] == "kw" and self.peek(1)[1] in ("IN", "BETWEEN", "LIKE"):
            self.take()
            negated = True
        if self.at("IN"):
            self.take()
            self.take("op", "(")
            items = [self.expr()]
            while self.at_op(","):
                self.take()
                items.append(self.expr())
            self.take("op", ")")
            return ("in", left, items, negated)
        if self.at("BETWEEN"):
            self.take()
            low = self.sum()
            self.keyword("AND")
            return ("between", left, low, self.sum(), negated)
        if self.at("LIKE"):
            self.take()
            return ("like", left, self.sum(), negated)
        if negated:
            raise QueryError("PARSE_ERROR")
        return left

    def sum(self):
        node = self.product()
        while self.at_op("+", "-", "||"):
            op = self.take()[1]
            node = ("bin", op, node, self.product())
        return node

    def product(self):
        node = self.unary()
        while self.at_op("*", "/", "%"):
            op = self.take()[1]
            node = ("bin", op, node, self.unary())
        return node

    def unary(self):
        if self.at_op("-"):
            self.take()
            return ("neg", self.unary())
        return self.atom()

    def atom(self):
        kind_, value = self.peek()
        if kind_ == "number":
            self.take()
            return ("lit", Fraction(value) if "." in value else int(value))
        if kind_ == "string":
            self.take()
            return ("lit", value[1:-1].replace("''", "'"))
        if kind_ == "kw" and value in ("TRUE", "FALSE", "NULL"):
            self.take()
            return ("lit", {"TRUE": True, "FALSE": False, "NULL": None}[value])
        if kind_ == "kw" and value == "CASE":
            return self.case()
        if kind_ == "op" and value == "(":
            self.take()
            node = self.expr()
            self.take("op", ")")
            return node
        if kind_ == "name":
            self.take()
            if self.at_op("("):
                return self.call(value.upper())
            if self.at_op("."):
                self.take()
                return ("col", value, self.take("name")[1])
            return ("col", None, value)
        raise QueryError("PARSE_ERROR")

    def case(self):
        self.keyword("CASE")
        branches = []
        while self.at("WHEN"):
            self.take()
            condition = self.expr()
            self.keyword("THEN")
            branches.append((condition, self.expr()))
        if not branches:
            raise QueryError("PARSE_ERROR")
        otherwise = None
        if self.at("ELSE"):
            self.take()
            otherwise = self.expr()
        self.keyword("END")
        return ("case", branches, otherwise)

    def call(self, name):
        self.take("op", "(")
        star = distinct = False
        args = []
        if self.at_op("*"):
            self.take()
            star = True
        elif not self.at_op(")"):
            if self.at("DISTINCT"):
                self.take()
                distinct = True
            args.append(self.expr())
            while self.at_op(","):
                self.take()
                args.append(self.expr())
        self.take("op", ")")
        if name in SCALARS:
            ok = not star and not distinct and len(args) == SCALARS[name]
        elif name == "COALESCE":
            ok = not star and not distinct and len(args) >= 1
        elif name == "COUNT":
            ok = (star and not args) or (not star and len(args) == 1)
        elif name in AGGREGATES:
            ok = not star and len(args) == 1 and (not distinct or name == "SUM")
        else:
            ok = False
        if not ok:
            raise QueryError("PARSE_ERROR")
        return ("call", name, args, distinct, star)


# Names and grouping --------------------------------------------------------------------------------------------------

def children(node):
    tag = node[0]
    if tag in ("lit", "col", "ref"):
        return []
    if tag in ("neg", "not"):
        return [node[1]]
    if tag in ("bin", "cmp"):
        return [node[2], node[3]]
    if tag in ("and", "or"):
        return [node[1], node[2]]
    if tag == "isnull":
        return [node[1]]
    if tag == "in":
        return [node[1], *node[2]]
    if tag == "between":
        return [node[1], node[2], node[3]]
    if tag == "like":
        return [node[1], node[2]]
    if tag == "case":
        return [part for branch in node[1] for part in branch] + ([node[2]] if node[2] is not None else [])
    if tag == "call":
        return list(node[2])
    raise ValueError(tag)


def rebuild(node, function):
    """The node with each child replaced by function(child)."""
    tag = node[0]
    if tag in ("lit", "col", "ref"):
        return node
    if tag in ("neg", "not"):
        return (tag, function(node[1]))
    if tag in ("bin", "cmp"):
        return (tag, node[1], function(node[2]), function(node[3]))
    if tag in ("and", "or"):
        return (tag, function(node[1]), function(node[2]))
    if tag == "isnull":
        return (tag, function(node[1]), node[2])
    if tag == "in":
        return (tag, function(node[1]), [function(item) for item in node[2]], node[3])
    if tag == "between":
        return (tag, function(node[1]), function(node[2]), function(node[3]), node[4])
    if tag == "like":
        return (tag, function(node[1]), function(node[2]), node[3])
    if tag == "case":
        return (tag, [(function(condition), function(value)) for condition, value in node[1]], function(node[2]) if node[2] is not None else None)
    if tag == "call":
        return (tag, node[1], [function(argument) for argument in node[2]], node[3], node[4])
    raise ValueError(tag)


def is_aggregate(node):
    return node[0] == "call" and node[1] in AGGREGATES


def has_aggregate(node):
    return is_aggregate(node) or any(has_aggregate(child) for child in children(node))


def has_nested_aggregate(node, inside=False):
    if is_aggregate(node):
        if inside:
            return True
        return any(has_nested_aggregate(child, True) for child in children(node))
    return any(has_nested_aggregate(child, inside) for child in children(node))


def refs_outside_aggregates(node):
    if is_aggregate(node):
        return []
    if node[0] == "ref":
        return [(node[1], node[2])]
    return [ref for child in children(node) for ref in refs_outside_aggregates(child)]


class Resolver:
    def __init__(self, sources):
        self.sources = sources  # [(qualifier lower, columns)]

    def resolve(self, node):
        if node[0] == "col":
            qualifier, name = node[1], node[2]
            if qualifier is not None:
                for index, (own, columns) in enumerate(self.sources):
                    if own == qualifier.lower():
                        for column_index, column in enumerate(columns):
                            if column.lower() == name.lower():
                                return ("ref", index, column_index, column)
                raise QueryError("UNKNOWN_COLUMN")
            found = [(index, column_index, column) for index, (_, columns) in enumerate(self.sources)
                     for column_index, column in enumerate(columns) if column.lower() == name.lower()]
            if not found:
                raise QueryError("UNKNOWN_COLUMN")
            if len({index for index, _, _ in found}) > 1:
                raise QueryError("AMBIGUOUS_COLUMN")
            return ("ref", *found[0])
        return rebuild(node, self.resolve)


# Evaluation --------------------------------------------------------------------------------------------------------

def compare(op, left, right):
    if left is None or right is None:
        return None
    if kind(left) != kind(right):
        raise QueryError("TYPE_MISMATCH")
    return {"=": left == right, "<>": left != right, "<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[op]


def logical(value):
    if value is not None and not isinstance(value, bool):
        raise QueryError("TYPE_MISMATCH")
    return value


def number(value):
    if kind(value) != "number":
        raise QueryError("TYPE_MISMATCH")
    return value


def arithmetic(op, left, right):
    if op == "||":
        return None if left is None or right is None else text(left) + text(right)
    if left is None or right is None:
        return None
    number(left)
    number(right)
    if op == "%":
        if isinstance(left, Fraction) or isinstance(right, Fraction):
            raise QueryError("TYPE_MISMATCH")
        if right == 0:
            raise QueryError("DIVISION_BY_ZERO")
        remainder = abs(left) % abs(right)
        return remainder if left >= 0 else -remainder
    if op == "/":
        if right == 0:
            raise QueryError("DIVISION_BY_ZERO")
        if isinstance(left, int) and isinstance(right, int):
            quotient = Fraction(left, right)
            return int(quotient) if quotient.denominator == 1 else quotient
        return Fraction(left) / Fraction(right)
    if isinstance(left, int) and isinstance(right, int):
        return {"+": left + right, "-": left - right, "*": left * right}[op]
    return {"+": Fraction(left) + Fraction(right), "-": Fraction(left) - Fraction(right), "*": Fraction(left) * Fraction(right)}[op]


def like(value, pattern):
    regex = "".join(".*" if char == "%" else "." if char == "_" else re.escape(char) for char in pattern)
    return re.fullmatch(regex, value, re.DOTALL) is not None


class Context:
    """A row (a tuple of per-source rows, None for a LEFT JOIN's missing row) or a group of rows."""

    def __init__(self, row=None, group=None):
        self.row, self.group = row, group

    def column(self, source, column):
        row = self.row if self.group is None else (self.group[0] if self.group else None)
        if row is None or source >= len(row) or row[source] is None:
            return None
        return row[source][column]


def evaluate(node, context):
    tag = node[0]
    if tag == "lit":
        return node[1]
    if tag == "ref":
        return context.column(node[1], node[2])
    if tag == "neg":
        value = evaluate(node[1], context)
        return None if value is None else -number(value)
    if tag == "bin":
        left = evaluate(node[2], context)
        right = evaluate(node[3], context)
        return arithmetic(node[1], left, right)
    if tag == "cmp":
        left = evaluate(node[2], context)
        right = evaluate(node[3], context)
        return compare(node[1], left, right)
    if tag == "isnull":
        result = evaluate(node[1], context) is None
        return not result if node[2] else result
    if tag == "in":
        value = evaluate(node[1], context)
        unknown = value is None
        result = False
        for item in node[2]:
            outcome = compare("=", value, evaluate(item, context))
            if outcome is True:
                result = True
                break
            if outcome is None:
                unknown = True
        result = True if result else (None if unknown else False)
        return negate(result) if node[3] else result
    if tag == "between":
        value = evaluate(node[1], context)
        low = compare(">=", value, evaluate(node[2], context))
        if low is False:
            result = False
        else:
            high = compare("<=", value, evaluate(node[3], context))
            result = False if high is False else (None if low is None or high is None else True)
        return negate(result) if node[4] else result
    if tag == "like":
        value = evaluate(node[1], context)
        pattern = evaluate(node[2], context)
        if value is None or pattern is None:
            result = None
        elif isinstance(value, str) and isinstance(pattern, str):
            result = like(value, pattern)
        else:
            raise QueryError("TYPE_MISMATCH")
        return negate(result) if node[3] else result
    if tag == "not":
        return negate(logical(evaluate(node[1], context)))
    if tag == "and":
        left = logical(evaluate(node[1], context))
        if left is False:
            return False
        right = logical(evaluate(node[2], context))
        if right is False:
            return False
        return None if left is None or right is None else True
    if tag == "or":
        left = logical(evaluate(node[1], context))
        if left is True:
            return True
        right = logical(evaluate(node[2], context))
        if right is True:
            return True
        return None if left is None or right is None else False
    if tag == "case":
        for condition, value in node[1]:
            if evaluate(condition, context) is True:
                return evaluate(value, context)
        return evaluate(node[2], context) if node[2] is not None else None
    if tag == "call":
        return call(node, context)
    raise ValueError(tag)


def negate(value):
    return None if value is None else not value


def call(node, context):
    _, name, args, distinct, star = node
    if name in AGGREGATES:
        rows = context.group or []
        if star:
            return len(rows)
        values = [value for value in (evaluate(args[0], Context(row=row)) for row in rows) if value is not None]
        if distinct:
            seen, unique = set(), []
            for value in values:
                if norm(value) not in seen:
                    seen.add(norm(value))
                    unique.append(value)
            values = unique
        if name == "COUNT":
            return len(values)
        if not values:
            return None
        if name in ("SUM", "AVG"):
            for value in values:
                number(value)
            total = sum(values) if all(isinstance(value, int) for value in values) else sum(Fraction(value) for value in values)
            if name == "SUM":
                return total
            mean = Fraction(total) / len(values)
            return int(mean) if mean.denominator == 1 else mean
        if len({kind(value) for value in values}) > 1:
            raise QueryError("TYPE_MISMATCH")
        best = values[0]
        for value in values[1:]:
            if (value < best) if name == "MIN" else (value > best):
                best = value
        return best
    if name == "COALESCE":
        for argument in args:
            value = evaluate(argument, context)
            if value is not None:
                return value
        return None
    values = [evaluate(argument, context) for argument in args]
    value = values[0]
    if name in ("UPPER", "LOWER", "LENGTH"):
        if value is None:
            return None
        if not isinstance(value, str):
            raise QueryError("TYPE_MISMATCH")
        return value.upper() if name == "UPPER" else value.lower() if name == "LOWER" else len(value)
    if name == "ABS":
        return None if value is None else abs(number(value))
    if name == "ROUND":
        places = values[1]
        if value is None or places is None:
            return None
        number(value)
        if not isinstance(places, int) or isinstance(places, bool) or not 0 <= places <= 6:
            raise QueryError("TYPE_MISMATCH")
        if isinstance(value, int):
            return value
        scale = 10 ** places
        magnitude = Fraction(int(abs(value) * scale + Fraction(1, 2)), scale)
        return magnitude if value >= 0 else -magnitude
    raise ValueError(name)


def order_compare(left, right, descending):
    """ASC puts NULL last, DESC puts NULL first; other values compare naturally."""
    if left is None and right is None:
        return 0
    if left is None:
        return -1 if descending else 1
    if right is None:
        return 1 if descending else -1
    result = (left > right) - (left < right)
    return -result if descending else result


# Running a query ---------------------------------------------------------------------------------------------------

def run(tables, source):
    query = Parser(tokenize(source)).query()
    catalog = {name.lower(): (name, table) for name, table in tables.items()}
    sources = []
    for table, alias in query["sources"]:
        if table.lower() not in catalog:
            raise QueryError("UNKNOWN_TABLE")
        sources.append(((alias or table).lower(), catalog[table.lower()][1]["columns"], catalog[table.lower()][1]["rows"]))
    width = sum(len(columns) for _, columns, _ in sources) if query["items"] == "*" else len(query["items"])
    aliases = [] if query["items"] == "*" else [alias.lower() if alias else None for _, alias in query["items"]]
    for expr, _ in query["order"]:
        if expr[0] == "lit" and isinstance(expr[1], int) and not isinstance(expr[1], bool) and not 1 <= expr[1] <= width:
            raise QueryError("PARSE_ERROR")
    resolver = Resolver([(qualifier, columns) for qualifier, columns, _ in sources])
    joins = [(left, resolver.resolve(on)) for left, on in query["joins"]]
    where = resolver.resolve(query["where"]) if query["where"] is not None else None
    group = [resolver.resolve(expr) for expr in query["group"]]
    having = resolver.resolve(query["having"]) if query["having"] is not None else None
    if query["items"] == "*":
        items = [(("ref", index, column_index, column), None) for index, (_, columns, _) in enumerate(sources) for column_index, column in enumerate(columns)]
    else:
        items = [(resolver.resolve(expr), alias) for expr, alias in query["items"]]
    order = []
    for expr, descending in query["order"]:
        if expr[0] == "lit" and isinstance(expr[1], int) and not isinstance(expr[1], bool):
            order.append(("position", expr[1] - 1, descending))
        elif expr[0] == "col" and expr[1] is None and expr[2].lower() in aliases:
            order.append(("position", aliases.index(expr[2].lower()), descending))
        else:
            order.append(("expr", resolver.resolve(expr), descending))
    # Grouping rules.
    for expr in [on for _, on in joins] + ([where] if where is not None else []) + group:
        if has_aggregate(expr):
            raise QueryError("GROUPING_ERROR")
    expressions = [expr for expr, _ in items] + ([having] if having is not None else []) + [entry[1] for entry in order if entry[0] == "expr"]
    if any(has_nested_aggregate(expr) for expr in expressions):
        raise QueryError("GROUPING_ERROR")
    grouped = bool(group) or any(has_aggregate(expr) for expr, _ in items) or (having is not None and has_aggregate(having))
    if not grouped and (having is not None or any(entry[0] == "expr" and has_aggregate(entry[1]) for entry in order)):
        raise QueryError("GROUPING_ERROR")
    if grouped:
        keys = {(expr[1], expr[2]) for expr in group if expr[0] == "ref"}
        for expr in expressions:
            if any(ref not in keys for ref in refs_outside_aggregates(expr)):
                raise QueryError("GROUPING_ERROR")
    # FROM and joins.
    rows = [(row,) for row in sources[0][2]]
    for (left, on), (_, columns, table_rows) in zip(joins, sources[1:]):
        joined = []
        for row in rows:
            matched = False
            for other in table_rows:
                candidate = row + (other,)
                if evaluate(on, Context(row=candidate)) is True:
                    joined.append(candidate)
                    matched = True
            if left and not matched:
                joined.append(row + (None,))
        rows = joined
    if where is not None:
        rows = [row for row in rows if evaluate(where, Context(row=row)) is True]
    if grouped:
        groups, index = [], {}
        for row in rows:
            key = tuple(norm(evaluate(expr, Context(row=row))) for expr in group)
            if key not in index:
                index[key] = len(groups)
                groups.append([])
            groups[index[key]].append(row)
        if not group:
            groups = [rows]
        contexts = [Context(group=members) for members in groups]
        if having is not None:
            contexts = [context for context in contexts if evaluate(having, context) is True]
    else:
        contexts = [Context(row=row) for row in rows]
    results = [(context, [evaluate(expr, context) for expr, _ in items]) for context in contexts]
    if query["distinct"]:
        seen, unique = set(), []
        for context, values in results:
            key = tuple(norm(value) for value in values)
            if key not in seen:
                seen.add(key)
                unique.append((context, values))
        results = unique
    if order:
        keyed = []
        for context, values in results:
            keyed.append(([values[entry[1]] if entry[0] == "position" else evaluate(entry[1], context) for entry in order], values))
        for position in range(len(order)):
            if len({kind(keys[position]) for keys, _ in keyed} - {"null"}) > 1:
                raise QueryError("TYPE_MISMATCH")
        def compare_rows(left, right):
            for position, entry in enumerate(order):
                result = order_compare(left[0][position], right[0][position], entry[2])
                if result:
                    return result
            return 0
        keyed.sort(key=cmp_to_key(compare_rows))
        ordered = [values for _, values in keyed]
    else:
        ordered = [values for _, values in results]
    ordered = ordered[query["offset"]:]
    if query["limit"] is not None:
        ordered = ordered[:query["limit"]]
    names = [alias if alias else (expr[3] if expr[0] == "ref" else f"col{position}") for position, (expr, alias) in enumerate(items, 1)]
    return {"columns": names, "rows": [[output(value) for value in values] for values in ordered]}


def load_tables(raw):
    return raw


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle, parse_float=Fraction)
    results = []
    for source in data["queries"]:
        try:
            results.append(run(data["tables"], source))
        except QueryError as error:
            results.append({"error": error.code})
    print(json.dumps({"results": results}))


if __name__ == "__main__":
    main()
