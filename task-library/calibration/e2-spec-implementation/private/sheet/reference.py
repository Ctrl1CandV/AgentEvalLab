#!/usr/bin/env python3
"""Reference implementation of the E2 sheet specification (items/sheet/prompt.md). Standard library only."""
import json
import math
import re
import sys

NUMBER_LITERAL = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
ERRORS = {"#PARSE!", "#VALUE!", "#DIV/0!", "#NUM!", "#REF!", "#CYCLE!"}
FUNCTIONS = {"SUM", "MIN", "MAX", "AVERAGE", "COUNT", "IF"}
EMPTY = object()


class Error(Exception):
    pass


class Err:
    def __init__(self, code):
        self.code = code


class Boolean:
    def __init__(self, value):
        self.value = bool(value)


class ParseError(Exception):
    pass


TOKEN = re.compile(r"\s*(?:(?P<number>[0-9]+(?:\.[0-9]+)?)(?![0-9.])|(?P<string>\"[^\"]*\")|(?P<name>[A-Za-z]+[0-9]*)|(?P<op><=|>=|<>|[-+*/^&=<>(),:]))")


def tokenize(text):
    tokens, index = [], 0
    while index < len(text):
        if text[index:].strip() == "":
            break
        match = TOKEN.match(text, index)
        if not match:
            raise ParseError()
        index = match.end()
        kind = match.lastgroup
        tokens.append((kind, match.group(kind)))
    return tokens


def parse_reference(name):
    match = re.fullmatch(r"([A-Za-z])([0-9]+)", name)
    if not match:
        return None
    return match.group(1).upper(), int(match.group(2))


class Parser:
    def __init__(self, tokens):
        self.tokens, self.position = tokens, 0

    def peek(self, offset=0):
        index = self.position + offset
        return self.tokens[index] if index < len(self.tokens) else (None, None)

    def take(self, value=None):
        token = self.peek()
        if token[0] is None or (value is not None and token[1] != value):
            raise ParseError()
        self.position += 1
        return token

    def parse(self):
        node = self.comparison()
        if self.position != len(self.tokens):
            raise ParseError()
        return node

    def comparison(self):
        left = self.concat()
        if self.peek()[1] in ("=", "<>", "<", "<=", ">", ">=") and self.peek()[0] == "op":
            operator = self.take()[1]
            return ("compare", operator, left, self.concat())
        return left

    def concat(self):
        node = self.additive()
        while self.peek() == ("op", "&"):
            self.take()
            node = ("binary", "&", node, self.additive())
        return node

    def additive(self):
        node = self.term()
        while self.peek()[0] == "op" and self.peek()[1] in ("+", "-"):
            operator = self.take()[1]
            node = ("binary", operator, node, self.term())
        return node

    def term(self):
        node = self.power()
        while self.peek()[0] == "op" and self.peek()[1] in ("*", "/"):
            operator = self.take()[1]
            node = ("binary", operator, node, self.power())
        return node

    def power(self):
        base = self.unary()
        if self.peek() == ("op", "^"):
            self.take()
            return ("binary", "^", base, self.power())
        return base

    def unary(self):
        if self.peek() == ("op", "-"):
            self.take()
            return ("negate", self.unary())
        return self.primary()

    def primary(self):
        kind, value = self.peek()
        if kind == "number":
            self.take()
            return ("number", float(value))
        if kind == "string":
            self.take()
            return ("text", value[1:-1])
        if kind == "op" and value == "(":
            self.take()
            node = self.comparison()
            self.take(")")
            return node
        if kind == "name":
            self.take()
            if self.peek() == ("op", "("):
                name = value.upper()
                if name not in FUNCTIONS:
                    raise ParseError()
                self.take("(")
                arguments = []
                if self.peek() != ("op", ")"):
                    arguments.append(self.argument())
                    while self.peek() == ("op", ","):
                        self.take()
                        arguments.append(self.argument())
                self.take(")")
                if name == "IF" and len(arguments) != 3:
                    raise ParseError()
                if name == "IF" and any(argument[0] == "range" for argument in arguments):
                    raise ParseError()
                return ("call", name, arguments)
            reference = parse_reference(value)
            if reference is None:
                raise ParseError()
            return ("ref", reference)
        raise ParseError()

    def argument(self):
        kind, value = self.peek()
        if kind == "name" and self.peek(1) == ("op", ":"):
            start = parse_reference(value)
            self.take()
            self.take(":")
            end_kind, end_value = self.take()
            end = parse_reference(end_value) if end_kind == "name" else None
            if start is None or end is None:
                raise ParseError()
            return ("range", start, end)
        return self.comparison()


class Sheet:
    def __init__(self, cells):
        self.cells = cells
        self.values = {}
        self.stack = []
        self.cyclic = set()

    def cell(self, column, row):
        if not 1 <= row <= 99:
            return Err("#REF!")
        name = f"{column}{row}"
        if name in self.values:
            return self.values[name]
        if name in self.stack:
            for member in self.stack[self.stack.index(name):]:
                self.cyclic.add(member)
            return Err("#CYCLE!")
        content = self.cells.get(name, "")
        self.stack.append(name)
        try:
            value = self.content_value(content)
        finally:
            self.stack.pop()
        if name in self.cyclic:
            value = Err("#CYCLE!")
        self.values[name] = value
        return value

    def content_value(self, content):
        if content == "":
            return EMPTY
        if content.startswith("="):
            try:
                tree = Parser(tokenize(content[1:])).parse()
            except ParseError:
                return Err("#PARSE!")
            return self.evaluate(tree)
        if NUMBER_LITERAL.match(content):
            return float(content)
        return content

    def evaluate(self, node):
        kind = node[0]
        if kind == "number":
            return node[1]
        if kind == "text":
            return node[1]
        if kind == "ref":
            return self.cell(*node[1])
        if kind == "negate":
            value = self.evaluate(node[1])
            if isinstance(value, Err):
                return value
            number = self.as_number(value)
            return number if isinstance(number, Err) else self.finite(-number)
        if kind == "binary":
            _, operator, left_node, right_node = node
            left = self.evaluate(left_node)
            if isinstance(left, Err):
                return left
            right = self.evaluate(right_node)
            if isinstance(right, Err):
                return right
            if operator == "&":
                return self.text(left) + self.text(right)
            a, b = self.as_number(left), self.as_number(right)
            if isinstance(a, Err):
                return a
            if isinstance(b, Err):
                return b
            if operator == "+":
                return self.finite(a + b)
            if operator == "-":
                return self.finite(a - b)
            if operator == "*":
                return self.finite(a * b)
            if operator == "/":
                return Err("#DIV/0!") if b == 0 else self.finite(a / b)
            try:
                result = a ** b
            except (OverflowError, ZeroDivisionError):
                return Err("#NUM!")
            return Err("#NUM!") if isinstance(result, complex) else self.finite(result)
        if kind == "compare":
            _, operator, left_node, right_node = node
            left = self.evaluate(left_node)
            if isinstance(left, Err):
                return left
            right = self.evaluate(right_node)
            if isinstance(right, Err):
                return right
            if isinstance(left, Boolean) or isinstance(right, Boolean):
                return Err("#VALUE!")
            if left is EMPTY and right is EMPTY:
                left = right = 0.0
            elif left is EMPTY:
                left = "" if isinstance(right, str) else 0.0
            elif right is EMPTY:
                right = "" if isinstance(left, str) else 0.0
            if isinstance(left, str) != isinstance(right, str):
                return Err("#VALUE!")
            return Boolean({"=": left == right, "<>": left != right, "<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[operator])
        if kind == "call":
            return self.call(node[1], node[2])
        raise ValueError(kind)

    def call(self, name, arguments):
        if name == "IF":
            condition = self.evaluate(arguments[0])
            if isinstance(condition, Err):
                return condition
            if isinstance(condition, Boolean):
                truth = condition.value
            elif isinstance(condition, float):
                truth = condition != 0
            else:
                return Err("#VALUE!")
            return self.evaluate(arguments[1] if truth else arguments[2])
        numbers = []
        for argument in arguments:
            if argument[0] == "range":
                (c1, r1), (c2, r2) = argument[1], argument[2]
                rows = range(min(r1, r2), max(r1, r2) + 1)
                columns = [chr(code) for code in range(min(ord(c1), ord(c2)), max(ord(c1), ord(c2)) + 1)]
                if not all(1 <= row <= 99 for row in (r1, r2)):
                    return Err("#REF!")
                for row in rows:
                    for column in columns:
                        value = self.cell(column, row)
                        if isinstance(value, Err):
                            return value
                        if isinstance(value, float):
                            numbers.append(value)
            else:
                value = self.evaluate(argument)
                if isinstance(value, Err):
                    return value
                if value is EMPTY:
                    continue
                if isinstance(value, str):
                    return Err("#VALUE!")
                numbers.append(float(value.value) if isinstance(value, Boolean) else value)
        if name == "SUM":
            return self.finite(math.fsum(numbers))
        if name == "MIN":
            return min(numbers) if numbers else 0.0
        if name == "MAX":
            return max(numbers) if numbers else 0.0
        if name == "COUNT":
            return float(len(numbers))
        if not numbers:
            return Err("#DIV/0!")
        return self.finite(math.fsum(numbers) / len(numbers))

    @staticmethod
    def finite(value):
        return value if isinstance(value, float) and math.isfinite(value) else Err("#NUM!")

    @staticmethod
    def as_number(value):
        if value is EMPTY:
            return 0.0
        if isinstance(value, Boolean):
            return 1.0 if value.value else 0.0
        if isinstance(value, str):
            return Err("#VALUE!")
        return value

    @staticmethod
    def text(value):
        if value is EMPTY:
            return ""
        if isinstance(value, Boolean):
            return "TRUE" if value.value else "FALSE"
        if isinstance(value, float):
            return json.dumps(output(value))
        return value


def output(value):
    if isinstance(value, Err):
        return value.code
    if value is EMPTY:
        return None
    if isinstance(value, Boolean):
        return value.value
    if isinstance(value, float):
        rounded = round(value, 9)
        return int(rounded) if rounded == int(rounded) else rounded
    return value


def evaluate_sheet(cells):
    sheet = Sheet(cells)
    return {name: output(sheet.cell(name[0], int(name[1:]))) for name in cells}


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(evaluate_sheet(data["cells"])))


if __name__ == "__main__":
    main()
