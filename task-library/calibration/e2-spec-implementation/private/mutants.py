"""Faulty variants of each E2 reference, built by source substitution, for self-calibration.

Each mutant models a plausible misreading of the specification and names the check it must fail. A mutant whose
substitution no longer applies raises, so a changed reference cannot silently disable a mutant.
"""

SHEET = [
    ("power-left-associative", "power",
     '            self.take()\n            return ("binary", "^", base, self.power())',
     '            self.take()\n            node = ("binary", "^", base, self.unary())\n            while self.peek() == ("op", "^"):\n                self.take()\n                node = ("binary", "^", node, self.unary())\n            return node'),
    ("no-if-short-circuit", "if",
     '            return self.evaluate(arguments[1] if truth else arguments[2])',
     '            chosen, other = (arguments[1], arguments[2]) if truth else (arguments[2], arguments[1])\n            unused = self.evaluate(other)\n            if isinstance(unused, Err):\n                return unused\n            return self.evaluate(chosen)'),
    ("average-counts-empty", "functions",
     '                        if isinstance(value, float):\n                            numbers.append(value)',
     '                        if isinstance(value, float):\n                            numbers.append(value)\n                        elif value is EMPTY:\n                            numbers.append(0.0)'),
    ("case-insensitive-text-compare", "comparison",
     '            if isinstance(left, str) != isinstance(right, str):\n                return Err("#VALUE!")',
     '            if isinstance(left, str) != isinstance(right, str):\n                return Err("#VALUE!")\n            if isinstance(left, str):\n                left, right = left.lower(), right.lower()'),
    ("no-output-rounding", "rounding",
     '        rounded = round(value, 9)',
     '        rounded = value'),
    ("type-check-before-operands", "error-propagation",
     '            right = self.evaluate(right_node)\n            if isinstance(right, Err):\n                return right\n            if operator == "&":',
     '            if operator != "&" and isinstance(left, str):\n                return Err("#VALUE!")\n            right = self.evaluate(right_node)\n            if isinstance(right, Err):\n                return right\n            if operator == "&":'),
    ("cycle-as-ref-error", "cycles",
     '        if name in self.stack:\n            for member in self.stack[self.stack.index(name):]:\n                self.cyclic.add(member)\n            return Err("#CYCLE!")',
     '        if name in self.stack:\n            return Err("#REF!")'),
    ("float-for-integers", "number-format",
     '        return int(rounded) if rounded == int(rounded) else rounded',
     '        return rounded'),
    ("zero-negative-power-as-num", "division",
     '            if a == 0 and b < 0:\n                return Err("#DIV/0!")\n',
     ''),
    ("division-by-zero-as-num", "division",
     '                return Err("#DIV/0!") if b == 0 else self.finite(a / b)',
     '                return Err("#NUM!") if b == 0 else self.finite(a / b)'),
]


def mutants(item_id, reference_path):
    """(name, target check, source) for each mutant of an item's reference."""
    with open(reference_path, encoding="utf-8") as handle:
        source = handle.read()
    table = {"sheet": SHEET}[item_id]
    for name, target, old, new in table:
        if source.count(old) != 1:
            raise ValueError(f"mutant {name} no longer applies")
        yield name, target, source.replace(old, new)
