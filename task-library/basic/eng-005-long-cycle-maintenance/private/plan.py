"""S7 (planning) for eng-005 0.5.0: hidden stores, the best plans known for them, and the quality scale.

`plan --crews N` schedules every work order that is not DONE on N identical crews. Each order runs for its `hours`
(1 when absent) without a break, after every prerequisite that is not DONE has ended. The cost of a plan is the sum of
priority x end (priority 1 when absent), to be made as small as possible: the total priority-weighted completion
time, P|prec|sum wC in scheduling notation.

The public stage files hold the store generator (make_plan_store.py) and the plan tools (plan_tools.py): the orders a
plan schedules, validation, and the two lower anchors of the scale. 0 is the naive plan, which takes the orders in id
order; 0.5 is the greedy plan, which starts the ready order with the highest priority per hour whenever a crew is free.
This module holds the hidden stores and the upper anchor, the best plan known, which differs by case:

- tiny (7 orders, 2 crews) and small (9 orders, 3 crews): the optimum, by the serial scheme over every sequence. These
  stores are drawn until the greedy plan is at least 10% above the optimum;
- chains (40 orders in chains, 1 crew): the optimum, by Sidney's rule (chain prefixes by priority per hour);
- general (300 orders, 5 crews) and large (3,000 orders, 16 crews): no exact method; the best of the greedy plan,
  a successor-aware ranking (the best priority per hour of a dependency path an order starts) and a long local search.

Dependency stores have gateways: long, low-priority orders that short, high-priority orders depend on, which the
greedy plan starts late.
"""
import heapq
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parent / "stages" / "S7" / "public"
BEST_PATH = HERE / "plan-best.json"
SEED = "eng005-plan-hidden"
EXACT = {"tiny", "small", "chains"}
SMALL_GAP = 0.10
RUNGS = (("25", 0.25), ("50", 0.5), ("65", 0.65), ("80", 0.8), ("90", 0.9), ("97", 0.97))


def public(name):
    """A module of the stage's public directory, without leaving a bytecode cache there (the package declares its files)."""
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, PUBLIC / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


make_plan_store = public("make_plan_store")
tools = public("plan_tools")
STORES = make_plan_store.STORES
jobs, cost_of, list_schedule, naive, greedy, check = tools.jobs, tools.cost_of, tools.list_schedule, tools.naive, tools.greedy, tools.check


def store(name, seed=SEED):
    """A hidden store for a case; small cases take the first draw on which the greedy plan is SMALL_GAP above the optimum."""
    if name not in ("tiny", "small"):
        return make_plan_store.store(name, f"{seed}:{name}")
    for attempt in range(1000):
        value = make_plan_store.store(name, f"{seed}:{name}:{attempt}")
        work = jobs(value)
        crews = STORES[name]["crews"]
        if cost_of(greedy(work, crews), work) >= (1 + SMALL_GAP) * cost_of(exhaustive(work, crews), work):
            return value
    raise RuntimeError(f"no {name} store")


def crews_by_coloring(times, crews):
    """Crew numbers for {id: (start, end)} with at most `crews` running at once: by start, the lowest free crew."""
    free, assigned, running = list(range(1, crews + 1)), {}, []
    for item, (start, end) in sorted(times.items(), key=lambda pair: (pair[1][0], pair[1][1], pair[0])):
        while running and running[0][0] <= start:
            _, crew = heapq.heappop(running)
            heapq.heappush(free, crew)
        crew = heapq.heappop(free)
        assigned[item] = (crew, start, end)
        heapq.heappush(running, (end, crew))
    return assigned


def serial(sequence, work, crews):
    """The serial generation scheme: each order of a precedence-feasible sequence, in turn, at the earliest time at which
    its prerequisites have ended and fewer than `crews` orders are running throughout its hours (filling gaps). Over
    all sequences it reaches every active schedule, so its best is optimal for this regular cost."""
    events, ends, times = [], {}, {}
    for item in sequence:
        hours, _, before = work[item]
        start = max((ends[other] for other in before), default=0)
        while True:
            level = sum(delta for moment, delta in events if moment <= start)
            fits = level < crews
            if fits:
                for moment, delta in events:
                    if start < moment < start + hours:
                        level += delta
                        if level >= crews:
                            fits = False
                            break
            if fits:
                break
            start = min(moment for moment, delta in events if delta < 0 and moment > start)
        ends[item] = start + hours
        times[item] = (start, start + hours)
        events += [(start, 1), (start + hours, -1)]
        events.sort()
    return crews_by_coloring(times, crews)


def exhaustive(work, crews):
    """The optimum of a small case: the serial scheme over every precedence-feasible sequence."""
    items, best = sorted(work), [None, None]

    def extend(sequence, placed):
        if len(sequence) == len(items):
            schedule = serial(sequence, work, crews)
            cost = cost_of(schedule, work)
            if best[0] is None or cost < best[0]:
                best[0], best[1] = cost, schedule
            return
        for item in items:
            if item not in placed and all(other in placed for other in work[item][2]):
                placed.add(item)
                sequence.append(item)
                extend(sequence, placed)
                sequence.pop()
                placed.discard(item)
    extend([], set())
    return best[1]


def sidney(work):
    """1|chains|sum wC: repeatedly the chain prefix with the highest priority per hour, the first such when tied."""
    following = {}
    for item, (_, _, before) in work.items():
        for other in before:
            following[other] = item
    chains = []
    for head in sorted(item for item, (_, _, before) in work.items() if not before):
        chain, item = [head], head
        while item in following:
            item = following[item]
            chain.append(item)
        chains.append(chain)
    sequence = []
    while any(chains):
        best = None
        for index, chain in enumerate(chains):
            weight = hours = 0
            for length, item in enumerate(chain, 1):
                weight += work[item][1]
                hours += work[item][0]
                if best is None or weight / hours > best[0] + 1e-12:
                    best = (weight / hours, index, length)
        _, index, length = best
        sequence += chains[index][:length]
        chains[index] = chains[index][length:]
    return list_schedule(sequence, work, 1)


def topological_from(schedule):
    return [item for item, _ in sorted(schedule.items(), key=lambda pair: (pair[1][1], pair[1][2], pair[0]))]


def path_ratios(work):
    """For each order, the best priority per hour of a dependency path that starts at it: finishing the order early is
    worth as much as the work it unlocks."""
    dependents = {}
    for item, (_, _, before) in work.items():
        for other in before:
            dependents.setdefault(other, []).append(item)
    best = {}
    for item in reversed(topological_from(greedy(work, 1))):
        hours, priority, _ = work[item]
        options = [(priority, hours)] + [(priority + best[other][0], hours + best[other][1]) for other in dependents.get(item, [])]
        best[item] = max(options, key=lambda pair: pair[0] / pair[1])
    return {item: weight / hours for item, (weight, hours) in best.items()}


def ranked_greedy(work, crews, ratios):
    """The greedy plan with orders ranked by `ratios` instead of their own priority per hour."""
    dependents, waiting = {}, {}
    for item, (_, _, before) in work.items():
        waiting[item] = len(before)
        for other in before:
            dependents.setdefault(other, []).append(item)
    ready = [((-ratios[item], item), item) for item, count in waiting.items() if count == 0]
    heapq.heapify(ready)
    free = list(range(1, crews + 1))
    running, now, schedule = [], 0, {}
    while ready or running:
        while free and ready:
            _, item = heapq.heappop(ready)
            crew = heapq.heappop(free)
            schedule[item] = (crew, now, now + work[item][0])
            heapq.heappush(running, (now + work[item][0], crew, item))
        if not running:
            break
        now = running[0][0]
        while running and running[0][0] == now:
            _, crew, item = heapq.heappop(running)
            heapq.heappush(free, crew)
            for other in dependents.get(item, []):
                waiting[other] -= 1
                if waiting[other] == 0:
                    heapq.heappush(ready, ((-ratios[other], other), other))
    return schedule


def search(work, crews, seconds, seed, decode):
    """Iterated local search on sequences: moves of one order within the positions its prerequisites and dependents
    allow, kept when the cost does not rise; restarts from perturbed copies of the best."""
    rng = random.Random(seed)
    dependents = {}
    for item, (_, _, before) in work.items():
        for other in before:
            dependents.setdefault(other, []).append(item)

    def window(sequence, position, item):
        low = max((position[other] for other in work[item][2]), default=-1) + 1
        high = min((position[other] for other in dependents.get(item, [])), default=len(sequence)) - 1
        return low, high
    best_sequence, best_cost = None, None
    for schedule in (greedy(work, crews), ranked_greedy(work, crews, path_ratios(work)), naive(work, crews)):
        sequence = topological_from(schedule)
        cost = cost_of(decode(sequence, work, crews), work)
        if best_cost is None or cost < best_cost:
            best_sequence, best_cost = sequence, cost
    current, current_cost, stale = list(best_sequence), best_cost, 0
    deadline = time.time() + seconds
    while time.time() < deadline:
        position = {item: index for index, item in enumerate(current)}
        item = rng.choice(current)
        index = position[item]
        low, high = window(current, position, item)
        if high <= low:
            continue
        target = rng.randint(low, high)
        if target == index:
            continue
        candidate = current[:index] + current[index + 1:]
        candidate.insert(target, item)
        cost = cost_of(decode(candidate, work, crews), work)
        if cost <= current_cost:
            current, current_cost = candidate, cost
            if cost < best_cost:
                best_sequence, best_cost, stale = list(candidate), cost, 0
                continue
        stale += 1
        if stale > 4000:
            current, stale = list(best_sequence), 0
            for _ in range(max(2, len(current) // 50)):
                position = {item: index for index, item in enumerate(current)}
                item = rng.choice(current)
                low, high = window(current, position, item)
                if high > low:
                    current.pop(position[item])
                    current.insert(rng.randint(low, high), item)
            current_cost = cost_of(decode(current, work, crews), work)
    return decode(best_sequence, work, crews)


def best_plan(name, seconds=0):
    """The best plan known for a case: the exact method where there is one, else the best of `seconds` of search."""
    work = jobs(store(name))
    crews = STORES[name]["crews"]
    if name in ("tiny", "small"):
        return exhaustive(work, crews)
    if name == "chains":
        return sidney(work)
    # The search decodes sequences fast, without filling gaps; its best sequences are also decoded filling gaps.
    found = [greedy(work, crews), ranked_greedy(work, crews, path_ratios(work))]
    for seed in range(3):
        schedule = search(work, crews, seconds / 3, f"{name}:{seed}", list_schedule)
        found.append(schedule)
        if len(work) <= 400:
            found.append(serial(topological_from(schedule), work, crews))
    return min(found, key=lambda schedule: cost_of(schedule, work))


def anchors():
    """{case: {naive, greedy, best, crews}}, the best from plan-best.json."""
    best = json.loads(BEST_PATH.read_text(encoding="utf-8"))
    result = {}
    for name, spec in STORES.items():
        work = jobs(store(name))
        result[name] = {"naive": cost_of(naive(work, spec["crews"]), work), "greedy": cost_of(greedy(work, spec["crews"]), work),
                        "best": best[name]["cost"], "crews": spec["crews"]}
    return result


def place(cost, anchor):
    """A plan's place on its case's scale: naive 0, greedy 0.5, best 1, linear in between, within 0 and 1. A plan no
    worse than the greedy one is on the upper half."""
    naive_cost, greedy_cost, best_cost = anchor["naive"], anchor["greedy"], anchor["best"]
    if cost is None:
        return 0.0
    if cost <= greedy_cost:
        if cost <= best_cost or greedy_cost <= best_cost:
            return 1.0
        return 0.5 + 0.5 * (greedy_cost - cost) / (greedy_cost - best_cost)
    if naive_cost <= greedy_cost:
        return 0.0
    return max(0.0, 0.5 * (naive_cost - cost) / (naive_cost - greedy_cost))


def compute_best(seconds):
    """Write plan-best.json: each case's best plan cost and how it was found."""
    result = {}
    for name in STORES:
        started = time.time()
        schedule = best_plan(name, seconds)
        work = jobs(store(name))
        result[name] = {"cost": cost_of(schedule, work),
                        "method": "exact" if name in EXACT else f"best of the greedy plan, a successor-aware ranking and {seconds:g} s of local search",
                        "seconds": round(time.time() - started, 1)}
        print(name, result[name], flush=True)
    BEST_PATH.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    compute_best(float(sys.argv[1]) if len(sys.argv) > 1 else 60)
