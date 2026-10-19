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


LEDGER = [
    ("float-conversion", "fx-rounding",
     "            credited = (value * factor).quantize(Decimal(1).scaleb(-PLACES[target_currency]), rounding=ROUND_HALF_EVEN)",
     "            credited = Decimal(str(round(float(value) * float(factor), PLACES[target_currency]))).quantize(Decimal(1).scaleb(-PLACES[target_currency]))"),
    ("half-up-rounding", "fx-rounding",
     "rounding=ROUND_HALF_EVEN)", "rounding=\"ROUND_HALF_UP\")"),
    ("holds-not-in-available", "holds",
     "        return account[\"balance\"] + account[\"limit\"] - held",
     "        return account[\"balance\"] + account[\"limit\"]"),
    ("capture-checks-available", "capture",
     "        if value > held:\n            raise Rejected(\"EXCEEDS_HOLD\")\n        del self.holds[hold]",
     "        if value > held:\n            raise Rejected(\"EXCEEDS_HOLD\")\n        if value > self.available(name):\n            raise Rejected(\"INSUFFICIENT_FUNDS\")\n        del self.holds[hold]"),
    ("ids-recorded-only-when-ok", "duplicates",
     "            self.seen.add(identifier)\n            try:\n                self.apply(event)\n",
     "            try:\n                self.apply(event)\n                self.seen.add(identifier)\n"),
    ("frozen-blocks-deposits", "frozen",
     "        name = self.account(event, \"account\")\n        value = self.money(event, name)\n        self.accounts[name][\"balance\"] += value",
     "        name = self.account(event, \"account\")\n        self.paying(name)\n        value = self.money(event, name)\n        self.accounts[name][\"balance\"] += value"),
    ("reversal-respects-frozen", "reversal",
     "            _, source, value, receiver, credited = effect\n",
     "            _, source, value, receiver, credited = effect\n            self.paying(receiver)\n"),
    ("frozen-before-same-account", "error-order",
     "        if source == target:\n            raise Rejected(\"SAME_ACCOUNT\")\n        self.paying(source)",
     "        self.paying(source)\n        if source == target:\n            raise Rejected(\"SAME_ACCOUNT\")"),
    ("zero-limit-with-decimals", "open",
     "            if event[\"limit\"] != \"0\":", "            if Decimal(event[\"limit\"]) != 0 if NUMBER.match(str(event[\"limit\"])) else True:"),
    ("trailing-point-accepted", "amounts",
     "    if not isinstance(value, str) or not NUMBER.match(value):\n        return None\n    decimals",
     "    if not isinstance(value, str) or not re.match(r\"^[0-9]+(\\.[0-9]*)?$\", value):\n        return None\n    value = value.rstrip(\".\")\n    decimals"),
    ("overdraft-limit-ignored", "withdraw",
     "        return account[\"balance\"] + account[\"limit\"] - held",
     "        return account[\"balance\"] - held"),
]

RECUR = [
    ("count-after-exceptions", "count-except",
     "        generated.append(day)\n",
     "        if day.isoformat() in rule.get(\"except\", []):\n            continue\n        generated.append(day)\n"),
    ("clamp-applies-to-nth", "nth",
     "                if n <= len(matches) and -n <= len(matches):\n                    day = datetime.date(year, month, matches[n - 1] if n > 0 else matches[n])",
     "                if n <= len(matches) and -n <= len(matches):\n                    day = datetime.date(year, month, matches[n - 1] if n > 0 else matches[n])\n                elif rule.get(\"overflow\") == \"clamp\":\n                    day = datetime.date(year, month, matches[-1])"),
    ("weekly-keeps-days-before-start", "weekly",
     "                if day >= start:\n                    yield day\n            monday",
     "                yield day\n            monday"),
    ("monthly-keeps-days-before-start", "monthly",
     "            if day is not None and day >= start:\n                yield day\n            index += interval",
     "            if day is not None:\n                yield day\n            index += interval"),
    ("leap-day-to-march", "yearly",
     "                if rule.get(\"overflow\", \"skip\") == \"clamp\":\n                    yield datetime.date(year, 2, 28)",
     "                yield datetime.date(year, 3, 1)"),
    ("until-exclusive", "daily",
     "        if until is not None and day > until:", "        if until is not None and day >= until:"),
    ("no-occurrence-limit", "limits",
     "        if len(generated) > MAX_OCCURRENCES:\n            return \"INVALID\"\n", ""),
    ("booleans-as-integers", "validation",
     "    if type(value) is not int or value < 1:", "    if not isinstance(value, int) or value < 1:"),
    ("clamp-ignored", "clamp",
     "                elif rule.get(\"overflow\", \"skip\") == \"clamp\":\n                    day = datetime.date(year, month, length)\n",
     ""),
]


def mutants(item_id, reference_path):
    """(name, target check, source) for each mutant of an item's reference."""
    with open(reference_path, encoding="utf-8") as handle:
        source = handle.read()
    table = {"sheet": SHEET, "ledger": LEDGER, "recur": RECUR}[item_id]
    for name, target, old, new in table:
        if source.count(old) != 1:
            raise ValueError(f"mutant {name} no longer applies")
        yield name, target, source.replace(old, new)
