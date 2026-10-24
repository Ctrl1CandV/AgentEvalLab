"""Logic grid puzzles for the R3 family (Task Set v2): model, clue types, a counting solver, generation and grading.

Standard library only. A puzzle has N houses in a row, numbered 1 (leftmost) to N, and M attributes. Every attribute
places each of its N values in exactly one house. Internally houses are 0-based; texts and answers use 1-based numbers.
"""
import random

ATTRIBUTES = {
    "Name": ["Arlo", "Bryn", "Cato", "Dara", "Elio", "Fenna", "Galen", "Hollis", "Ilse", "Joren"],
    "Color": ["amber", "cobalt", "coral", "ivory", "jade", "lilac", "maroon", "ochre", "slate", "teal"],
    "Pet": ["axolotl", "canary", "ferret", "gecko", "hamster", "parrot", "rabbit", "terrier", "tortoise", "whippet"],
    "Drink": ["cider", "cocoa", "coffee", "kefir", "lemonade", "matcha", "milk", "oolong", "soda", "water"],
    "Job": ["architect", "baker", "chemist", "courier", "florist", "librarian", "nurse", "pilot", "potter", "welder"],
    "Hobby": ["archery", "birding", "chess", "climbing", "fencing", "knitting", "origami", "pottery", "rowing", "sailing"],
    "Fruit": ["apricot", "banana", "cherry", "fig", "guava", "kiwi", "lychee", "mango", "papaya", "quince"],
    "Instrument": ["banjo", "cello", "clarinet", "drums", "flute", "harp", "lute", "oboe", "trumpet", "viola"],
    "Sport": ["badminton", "cricket", "curling", "golf", "handball", "hockey", "judo", "polo", "rugby", "squash"],
    "Vehicle": ["bicycle", "canoe", "glider", "kayak", "moped", "scooter", "sedan", "tandem", "tram", "van"],
}

# Clue kinds. "x" and "y" are (attribute, value) pairs; "house" is 0-based.
KINDS = ("at", "not_at", "same", "not_same", "left", "directly_left", "next_to", "one_between")


def popcount(mask):
    return bin(mask).count("1")


def lowest(mask):
    return (mask & -mask).bit_length() - 1


def highest(mask):
    return mask.bit_length() - 1


class Puzzle:
    """Houses, attributes with their values, and clues; variables are (attribute, value) pairs."""

    def __init__(self, n, attributes, clues):
        self.n = n
        self.attributes = attributes  # list of (name, [values])
        self.clues = clues
        self.full = (1 << n) - 1
        self.variables = [(name, value) for name, values in attributes for value in values]

    def solutions(self, limit=2):
        """Up to `limit` complete assignments {(attribute, value): house} satisfying every clue."""
        domains = {variable: self.full for variable in self.variables}
        found = []
        self._search(domains, found, limit)
        return found

    def _propagate(self, domains):
        changed = True
        while changed:
            changed = False
            for clue in self.clues:
                outcome = self._apply(clue, domains)
                if outcome is None:
                    return False
                changed |= outcome
            for name, values in self.attributes:
                for value in values:
                    mask = domains[(name, value)]
                    if not mask:
                        return False
                    if popcount(mask) == 1:
                        for other in values:
                            if other != value and domains[(name, other)] & mask:
                                domains[(name, other)] &= ~mask
                                changed = True
                for house in range(self.n):
                    bit = 1 << house
                    holders = [value for value in values if domains[(name, value)] & bit]
                    if not holders:
                        return False
                    if len(holders) == 1 and domains[(name, holders[0])] != bit:
                        domains[(name, holders[0])] = bit
                        changed = True
        return True

    def _apply(self, clue, domains):
        """Narrow domains for one clue; True if anything changed, False if not, None on contradiction."""
        kind, full = clue["kind"], self.full
        x = tuple(clue["x"])
        before_x = domains[x]
        if kind == "at":
            domains[x] &= 1 << clue["house"]
            return None if not domains[x] else domains[x] != before_x
        if kind == "not_at":
            domains[x] &= ~(1 << clue["house"]) & full
            return None if not domains[x] else domains[x] != before_x
        y = tuple(clue["y"])
        before_y = domains[y]
        dx, dy = domains[x], domains[y]
        if kind == "same":
            dx = dy = dx & dy
        elif kind == "not_same":
            if popcount(dx) == 1:
                dy &= ~dx
            if popcount(dy) == 1:
                dx &= ~dy
        elif kind == "left":  # x somewhere left of y
            if dy:
                dx &= (1 << highest(dy)) - 1
            if dx:
                dy &= full & ~((1 << (lowest(dx) + 1)) - 1)
        elif kind == "directly_left":  # x immediately left of y
            dx &= dy >> 1
            dy &= (dx << 1) & full
        elif kind == "next_to":
            dx &= ((dy << 1) | (dy >> 1)) & full
            dy &= ((dx << 1) | (dx >> 1)) & full
        elif kind == "one_between":
            dx &= ((dy << 2) | (dy >> 2)) & full
            dy &= ((dx << 2) | (dx >> 2)) & full
        else:
            raise ValueError("unknown clue kind")
        domains[x], domains[y] = dx, dy
        if not dx or not dy:
            return None
        return dx != before_x or dy != before_y

    def _search(self, domains, found, limit):
        if len(found) >= limit or not self._propagate(domains):
            return
        open_variables = [variable for variable in self.variables if popcount(domains[variable]) > 1]
        if not open_variables:
            assignment = {variable: lowest(domains[variable]) for variable in self.variables}
            if all(holds(clue, assignment) for clue in self.clues):
                found.append(assignment)
            return
        variable = min(open_variables, key=lambda candidate: popcount(domains[candidate]))
        mask = domains[variable]
        while mask and len(found) < limit:
            bit = mask & -mask
            mask &= mask - 1
            branch = dict(domains)
            branch[variable] = bit
            self._search(branch, found, limit)


def holds(clue, assignment):
    """Whether a clue is true under a complete assignment {(attribute, value): house}."""
    x = assignment[tuple(clue["x"])]
    kind = clue["kind"]
    if kind == "at":
        return x == clue["house"]
    if kind == "not_at":
        return x != clue["house"]
    y = assignment[tuple(clue["y"])]
    return {"same": x == y, "not_same": x != y, "left": x < y, "directly_left": x == y - 1,
            "next_to": abs(x - y) == 1, "one_between": abs(x - y) == 2}[kind]


def true_clues(n, attributes, solution, rng):
    """Every true clue of each kind for a solution, shuffled within kind."""
    variables = [(name, value) for name, values in attributes for value in values]
    pool = {kind: [] for kind in KINDS}
    for x in variables:
        pool["at"].append({"kind": "at", "x": list(x), "house": solution[x]})
        for house in range(n):
            if house != solution[x]:
                pool["not_at"].append({"kind": "not_at", "x": list(x), "house": house})
    for index, x in enumerate(variables):
        for y in variables[index + 1:]:
            if x[0] == y[0]:
                continue
            a, b = solution[x], solution[y]
            first, second = (x, y) if rng.random() < 0.5 else (y, x)
            pool["same" if a == b else "not_same"].append({"kind": "same" if a == b else "not_same", "x": list(first), "y": list(second)})
            if a != b:
                low, high = (x, y) if a < b else (y, x)
                pool["left"].append({"kind": "left", "x": list(low), "y": list(high)})
                if abs(a - b) == 1:
                    pool["directly_left"].append({"kind": "directly_left", "x": list(low), "y": list(high)})
                    pool["next_to"].append({"kind": "next_to", "x": list(first), "y": list(second)})
                if abs(a - b) == 2:
                    pool["one_between"].append({"kind": "one_between", "x": list(first), "y": list(second)})
    for kind in pool:
        rng.shuffle(pool[kind])
    return pool


# Relative frequency of clue kinds while building a puzzle; relational clues dominate, as in ZebraLogic.
KIND_WEIGHTS = {"at": 1, "not_at": 2, "same": 3, "not_same": 2, "left": 2, "directly_left": 2, "next_to": 2, "one_between": 2}


def generate(n, m, rng):
    """A puzzle with a unique solution and a minimal clue set: no single clue can be removed without losing uniqueness."""
    names = sorted(rng.sample(sorted(ATTRIBUTES), m), key=list(ATTRIBUTES).index)
    attributes = [(name, sorted(rng.sample(ATTRIBUTES[name], n))) for name in names]
    solution = {}
    for name, values in attributes:
        for value, house in zip(values, rng.sample(range(n), n)):
            solution[(name, value)] = house
    pool = true_clues(n, attributes, solution, rng)
    clues = []
    while True:
        kinds = [kind for kind in KINDS if pool[kind]]
        kind = rng.choices(kinds, weights=[KIND_WEIGHTS[kind] for kind in kinds])[0]
        clues.append(pool[kind].pop())
        found = Puzzle(n, attributes, clues).solutions(2)
        if len(found) == 1:
            break
    order = list(range(len(clues)))
    rng.shuffle(order)
    for index in order:
        trial = [clue for position, clue in enumerate(clues) if position != index and clue is not None]
        if len(Puzzle(n, attributes, trial).solutions(2)) == 1:
            clues[index] = None
    clues = [clue for clue in clues if clue is not None]
    rng.shuffle(clues)
    for clue in clues:
        clue["phrase"] = rng.randrange(2)
    return {"n": n, "attributes": [[name, values] for name, values in attributes], "clues": clues,
            "solution": {str(house + 1): {name: value for name, values in attributes for value in values if solution[(name, value)] == house}
                         for house in range(n)}}


def describe(variable):
    return f"the person whose {variable[0]} is {variable[1]}"


def clue_text(clue):
    x = describe(clue["x"])
    flip = clue.get("phrase", 0)
    kind = clue["kind"]
    if kind == "at":
        return f"{x[0].upper()}{x[1:]} lives in house {clue['house'] + 1}."
    if kind == "not_at":
        return f"{x[0].upper()}{x[1:]} does not live in house {clue['house'] + 1}."
    y = describe(clue["y"])
    cap = lambda text: text[0].upper() + text[1:]
    if kind == "same":
        return f"{cap(x)} is {y}."
    if kind == "not_same":
        return f"{cap(x)} is not {y}."
    if kind == "left":
        return f"{cap(x)} lives somewhere to the left of {y}." if not flip else f"{cap(y)} lives somewhere to the right of {x}."
    if kind == "directly_left":
        return f"{cap(x)} lives directly left of {y}." if not flip else f"{cap(y)} lives directly right of {x}."
    if kind == "next_to":
        return f"{cap(x)} and {y} live next to each other."
    if kind == "one_between":
        return f"There is exactly one house between {x} and {y}."
    raise ValueError("unknown clue kind")


def prompt(item_id, puzzle):
    lines = [f"## Puzzle {item_id}", "",
             f"There are {puzzle['n']} houses in a row, numbered 1 to {puzzle['n']} from left to right. One person lives in each house. "
             "Each attribute below takes each of its values in exactly one house.", ""]
    for name, values in puzzle["attributes"]:
        lines.append(f"- {name}: {', '.join(values)}")
    lines += ["", "Clues:", ""]
    for index, clue in enumerate(puzzle["clues"], 1):
        lines.append(f"{index}. {clue_text(clue)}")
    return "\n".join(lines) + "\n"


def puzzle_from(record):
    return Puzzle(record["n"], [(name, values) for name, values in record["attributes"]], record["clues"])


def grade_cells(answer, key):
    """Per cell: whether the answer gives the key's value. Cells are (house, attribute index), both 1-based."""
    solution = answer.get("solution") if isinstance(answer, dict) else None
    attributes = list(key["solution"]["1"].keys())
    results = {}
    for house in range(1, key["n"] + 1):
        given = solution.get(str(house)) if isinstance(solution, dict) else None
        lowered = {str(k).strip().lower(): v for k, v in given.items()} if isinstance(given, dict) else {}
        for index, name in enumerate(attributes, 1):
            value = lowered.get(name.lower())
            results[(house, index)] = isinstance(value, str) and value.strip().lower() == key["solution"][str(house)][name].lower()
    return results


def seeded(seed):
    return random.Random(seed)
