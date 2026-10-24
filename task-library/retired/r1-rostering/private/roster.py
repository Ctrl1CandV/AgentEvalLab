"""Shift rostering instances for the R1 family (Task Set v2): model, rules, a feasibility solver, generation, grading.

Standard library only. A roster staffs every shift of every day with exactly `need` distinct people; that coverage
rule always holds. Each instance adds a subset of optional rules. An instance is feasible when some roster satisfies
coverage and all its optional rules; otherwise a minimal conflict set is a set of optional rules that cannot be
satisfied together with coverage, while dropping any one of them makes the rest satisfiable.
"""
import itertools
import random

class SolverLimit(Exception):
    """The search exceeded its node budget; the generator discards such instances."""


PEOPLE = ["Ada", "Bram", "Cleo", "Dov", "Esme", "Finn", "Gia", "Hugo", "Iris", "Jude", "Kai", "Lena"]
RULES = ("availability", "max_shifts", "min_shifts", "one_per_day", "rest", "senior", "apart")
RULE_TEXT = {
    "availability": "Nobody works on a day listed as unavailable for them.",
    "max_shifts": "Nobody works more than {max_shifts} shifts in total.",
    "min_shifts": "Everybody works at least {min_shifts} shifts in total.",
    "one_per_day": "Nobody works more than one shift on the same day.",
    "rest": "Nobody works the last shift of a day and the first shift of the next day.",
    "senior": "Every shift includes at least one senior person ({seniors}).",
    "apart": "These pairs never work the same shift: {pairs}.",
}


class Instance:
    def __init__(self, record):
        self.record = record
        self.people = record["people"]
        self.days = record["days"]
        self.shifts = record["shifts"]
        self.need = record["need"]
        self.rules = set(record["rules"])
        self.unavailable = {(person, day) for person, day in record.get("unavailable", [])}
        self.max_shifts = record.get("max_shifts")
        self.min_shifts = record.get("min_shifts")
        self.seniors = set(record.get("seniors", []))
        self.apart = [tuple(pair) for pair in record.get("apart", [])]

    def slots(self):
        return [(day, shift) for day in range(self.days) for shift in range(len(self.shifts))]

    def feasible(self, rules=None, node_limit=None):
        """A roster satisfying coverage and the given optional rules (default: the instance's), or None.

        With node_limit, raise SolverLimit after that many search nodes.
        """
        rules = self.rules if rules is None else set(rules)
        nodes = [0]
        slots = self.slots()
        people = range(len(self.people))
        last_shift, shift_count = len(self.shifts) - 1, len(self.shifts)
        senior_members = {member for member in people if self.people[member] in self.seniors}
        # Groups allowed by the rules that look at one shift only; an empty list means no roster exists.
        static = {}
        for day, shift in slots:
            groups = []
            for group in itertools.combinations(people, self.need):
                names = [self.people[member] for member in group]
                if "availability" in rules and any((name, day) in self.unavailable for name in names):
                    continue
                if "senior" in rules and not senior_members & set(group):
                    continue
                if "apart" in rules and any(a in names and b in names for a, b in self.apart):
                    continue
                groups.append(group)
            if not groups:
                return None
            static[(day, shift)] = groups
        # With one shift per person and day, each day alone must be staffable with disjoint groups.
        if "one_per_day" in rules:
            for day in range(self.days):
                def staff(shift, used):
                    return shift == shift_count or any(not used & set(group) and staff(shift + 1, used | set(group)) for group in static[(day, shift)])
                if not staff(0, set()):
                    return None
        # Upper bound of shifts a person can still take from slot position onwards.
        def can_take(member, position):
            if "one_per_day" in rules:
                days_left = {day for day, _ in slots[position:]}
                return sum(1 for day in days_left if "availability" not in rules or (self.people[member], day) not in self.unavailable)
            return sum(1 for day, _ in slots[position:] if "availability" not in rules or (self.people[member], day) not in self.unavailable)
        take_bound = {(member, position): can_take(member, position) for member in people for position in range(len(slots) + 1)}
        failed = set()
        roster = {}

        def search(position, counts, today, previous_last, current_last):
            nodes[0] += 1
            if node_limit is not None and nodes[0] > node_limit:
                raise SolverLimit()
            if position == len(slots):
                return "min_shifts" not in rules or all(count >= self.min_shifts for count in counts)
            day, shift = slots[position]
            if shift == 0 and position > 0:
                previous_last, today, current_last = current_last, frozenset(), frozenset()
            remaining_slots = len(slots) - position
            if "max_shifts" in rules:
                room = [min(self.max_shifts - counts[member], take_bound[(member, position)]) for member in people]
                if sum(room) < remaining_slots * self.need:
                    return False
                if "senior" in rules and sum(room[member] for member in senior_members) < remaining_slots:
                    return False
            if "min_shifts" in rules:
                if sum(max(0, self.min_shifts - count) for count in counts) > remaining_slots * self.need:
                    return False
                if any(self.min_shifts - counts[member] > take_bound[(member, position)] for member in people):
                    return False
            key = (position, counts, today, previous_last)
            if key in failed:
                return False
            # Prefer people with fewer shifts so far, which finds balanced rosters quickly.
            for group in sorted(static[(day, shift)], key=lambda group: sum(counts[member] for member in group)):
                if "max_shifts" in rules and any(counts[member] >= self.max_shifts for member in group):
                    continue
                if "one_per_day" in rules and today & set(group):
                    continue
                if "rest" in rules and shift == 0 and previous_last & set(group):
                    continue
                next_counts = tuple(count + (member in group) for member, count in enumerate(counts))
                roster[(day, shift)] = group
                if search(position + 1, next_counts, today | frozenset(group), previous_last,
                          frozenset(group) if shift == last_shift else current_last):
                    return True
            failed.add(key)
            return False

        if not search(0, tuple(0 for _ in people), frozenset(), frozenset(), frozenset()):
            return None
        return {f"Day {day + 1}": {self.shifts[shift]: [self.people[member] for member in roster[(day, shift)]]
                                   for shift in range(shift_count)} for day in range(self.days)}

    def subset_feasible(self, rules):
        """Feasibility of a subset of the instance's rules, from the precomputed table when the record has one."""
        table = self.record.get("subsets")
        if table is not None:
            return table[subset_key(rules)]
        return self.feasible(rules) is not None

    def is_minimal_conflict(self, rules):
        rules = set(rules)
        if not rules or not rules <= self.rules or self.subset_feasible(rules):
            return False
        return all(self.subset_feasible(rules - {rule}) for rule in rules)

    def minimal_conflicts(self):
        """Every minimal conflict set, smallest first."""
        found = []
        for size in range(1, len(self.rules) + 1):
            for combination in itertools.combinations(sorted(self.rules), size):
                if any(set(earlier) <= set(combination) for earlier in found):
                    continue
                if not self.subset_feasible(combination):
                    found.append(combination)
        return [list(conflict) for conflict in found]

    def violations(self, roster):
        """For a proposed roster: coverage and each optional rule, satisfied or not.

        Day keys ("Day 1"), shift names and people match case-insensitively. Optional rules count only for a roster
        that staffs every shift correctly; an empty or understaffed roster would satisfy many of them trivially.
        """
        rules = ["coverage"] + sorted(self.rules)
        failed = {rule: False for rule in rules}
        if not isinstance(roster, dict):
            return failed
        days = {str(key).strip().lower(): value for key, value in roster.items()}
        known = {name.lower(): name for name in self.people}
        normalized = {}
        for day in range(self.days):
            shifts = days.get(f"day {day + 1}")
            if not isinstance(shifts, dict):
                return failed
            shifts = {str(key).strip().lower(): value for key, value in shifts.items()}
            for index, shift in enumerate(self.shifts):
                names = shifts.get(shift.lower())
                if not isinstance(names, list) or not all(isinstance(name, str) and name.strip().lower() in known for name in names):
                    return failed
                normalized[(day, index)] = [known[name.strip().lower()] for name in names]
        slots = self.slots()
        if not all(len(normalized[slot]) == self.need and len(set(normalized[slot])) == self.need for slot in slots):
            return failed
        counts = {person: sum(person in normalized[slot] for slot in slots) for person in self.people}
        shift_count = len(self.shifts)
        checks = {
            "availability": lambda: all((name, day) not in self.unavailable for (day, _), names in normalized.items() for name in names),
            "max_shifts": lambda: all(count <= self.max_shifts for count in counts.values()),
            "min_shifts": lambda: all(count >= self.min_shifts for count in counts.values()),
            "one_per_day": lambda: all(len({name for shift in range(shift_count) for name in normalized[(day, shift)]}) == shift_count * self.need
                                       for day in range(self.days)),
            "rest": lambda: all(not set(normalized[(day, shift_count - 1)]) & set(normalized[(day + 1, 0)]) for day in range(self.days - 1)),
            "senior": lambda: all(any(name in self.seniors for name in names) for names in normalized.values()),
            "apart": lambda: all(not (a in names and b in names) for names in normalized.values() for a, b in self.apart),
        }
        results = {"coverage": True}
        for rule in sorted(self.rules):
            results[rule] = checks[rule]()
        return results


def subset_key(rules):
    return "+".join(sorted(rules)) or "-"


def subset_table(instance, node_limit):
    """Feasibility of every subset of the instance's rules; raises SolverLimit if any subset needs too many nodes."""
    rules = sorted(instance.rules)
    return {subset_key(combination): instance.feasible(set(combination), node_limit) is not None
            for size in range(len(rules) + 1) for combination in itertools.combinations(rules, size)}


NODE_LIMIT = 200_000

LEVELS = {
    # people, days, shifts, need, number of optional rules
    "L1": (4, 4, ["early", "late"], 1, 3),
    "L2": (5, 5, ["early", "late"], 1, 4),
    "L3": (6, 6, ["early", "late"], 2, 5),
    "L4": (7, 7, ["early", "day", "late"], 1, 6),
}


def generate(level, want_feasible, rng):
    """An instance of the level with the wanted feasibility. Infeasible instances need a conflict of two or more rules."""
    people_count, days, shifts, need, rule_count = LEVELS[level]
    while True:
        people = sorted(rng.sample(PEOPLE, people_count))
        rules = sorted(rng.sample(RULES, rule_count))
        slots = days * len(shifts) * need
        record = {"people": people, "days": days, "shifts": shifts, "need": need, "rules": rules}
        if "availability" in rules:
            record["unavailable"] = sorted([person, day] for person in people for day in range(days) if rng.random() < 0.22)
        if "max_shifts" in rules:
            record["max_shifts"] = max(1, -(-slots // people_count) + rng.choice([-1, 0, 0, 1]))
        if "min_shifts" in rules:
            record["min_shifts"] = max(1, slots // people_count + rng.choice([-1, -1, 0, 1]))
        if "senior" in rules:
            record["seniors"] = sorted(rng.sample(people, max(1, people_count // 3 + rng.choice([-1, 0, 0]))))
        if "apart" in rules:
            pairs = list(itertools.combinations(people, 2))
            record["apart"] = sorted(list(pair) for pair in rng.sample(pairs, min(len(pairs), max(1, people_count // 2))))
        instance = Instance(record)
        try:
            table = subset_table(instance, NODE_LIMIT)
        except SolverLimit:
            continue
        if table[subset_key(rules)] != want_feasible:
            continue
        record["subsets"] = table
        instance = Instance(record)
        if want_feasible:
            record["feasible"] = True
            record["example"] = instance.feasible()
            return record
        conflicts = instance.minimal_conflicts()
        if min(len(conflict) for conflict in conflicts) >= 2:
            record["feasible"] = False
            record["conflicts"] = conflicts
            return record


def prompt(item_id, record):
    lines = [f"## Instance {item_id}", "",
             f"Staff a roster for {record['days']} days (Day 1 to Day {record['days']}). Each day has the shifts "
             f"{', '.join(record['shifts'])}, in that order; the first shift is {record['shifts'][0]} and the last is {record['shifts'][-1]}.",
             f"People: {', '.join(record['people'])}.", "", "Rules:", "",
             f"- coverage: Every shift is staffed by exactly {record['need']} different {'person' if record['need'] == 1 else 'people'}. This rule always applies."]
    values = {"max_shifts": record.get("max_shifts"), "min_shifts": record.get("min_shifts"), "seniors": ", ".join(record.get("seniors", [])),
              "pairs": "; ".join(f"{a} and {b}" for a, b in record.get("apart", []))}
    for rule in record["rules"]:
        lines.append(f"- {rule}: {RULE_TEXT[rule].format(**values)}")
    if "availability" in record["rules"]:
        unavailable = {}
        for person, day in record.get("unavailable", []):
            unavailable.setdefault(person, []).append(f"Day {day + 1}")
        lines += ["", "Unavailable days:", ""]
        lines += [f"- {person}: {', '.join(days)}" for person, days in sorted(unavailable.items())] or ["- none"]
    return "\n".join(lines) + "\n"


def seeded(seed):
    return random.Random(seed)
