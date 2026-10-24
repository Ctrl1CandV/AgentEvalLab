"""Plan tools for S7: the orders a plan schedules, the two lower anchors of the quality scale (the naive and the greedy
plan, as the stage brief defines them), and the validation of a plan's output. The public checker uses them; you may
use them to compare your plans."""
import heapq
import json


def jobs(store_value):
    """{id: (hours, priority, prerequisites not DONE)} of the orders a plan schedules."""
    orders = {order["id"]: order for order in store_value["workOrders"]}
    result = {}
    for order in store_value["workOrders"]:
        if order["status"] == "DONE":
            continue
        result[order["id"]] = (order.get("hours", 1), order.get("priority", 1),
                               tuple(sorted(item for item in order.get("dependsOn", []) if orders[item]["status"] != "DONE")))
    return result


def cost_of(schedule, work):
    return sum(work[item][1] * end for item, (_, _, end) in schedule.items())


def list_schedule(sequence, work, crews):
    """Each order of a precedence-feasible sequence, in turn, on the crew free first, as soon as its prerequisites have
    ended (no back-filling)."""
    free = [(0, crew) for crew in range(1, crews + 1)]
    heapq.heapify(free)
    ends, schedule = {}, {}
    for item in sequence:
        hours, _, before = work[item]
        ready = max((ends[other] for other in before), default=0)
        available, crew = heapq.heappop(free)
        start = max(available, ready)
        ends[item] = start + hours
        schedule[item] = (crew, start, start + hours)
        heapq.heappush(free, (start + hours, crew))
    return schedule


def naive(work, crews):
    """0 on the scale: repeatedly the lowest id whose prerequisites are planned, on the crew free first."""
    sequence = []
    ready = [item for item, (_, _, before) in work.items() if not before]
    heapq.heapify(ready)
    dependents = {}
    for item, (_, _, before) in work.items():
        for other in before:
            dependents.setdefault(other, []).append(item)
    waiting = {item: len(before) for item, (_, _, before) in work.items()}
    while ready:
        item = heapq.heappop(ready)
        sequence.append(item)
        for other in dependents.get(item, []):
            waiting[other] -= 1
            if waiting[other] == 0:
                heapq.heappush(ready, other)
    return list_schedule(sequence, work, crews)


def greedy(work, crews):
    """0.5 on the scale: whenever a crew is free, the ready order with the highest priority per hour (ties by id) starts
    on it (the free crew with the lowest number); when none is ready, the next order to end frees one."""
    dependents, waiting = {}, {}
    for item, (_, _, before) in work.items():
        waiting[item] = len(before)
        for other in before:
            dependents.setdefault(other, []).append(item)
    key = lambda item: (-work[item][1] / work[item][0], item)  # noqa: E731
    ready = [(key(item), item) for item, count in waiting.items() if count == 0]
    heapq.heapify(ready)
    free = list(range(1, crews + 1))
    heapq.heapify(free)
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
                    heapq.heappush(ready, (key(other), other))
    return schedule


def check(store_value, crews, stdout):
    """(cost, None) for a valid plan printed by `plan --crews crews`, else (None, reason)."""
    try:
        output = json.loads(stdout)
        rows = output["schedule"]
        reported = output["cost"]
        if output.get("crews") != crews or not isinstance(rows, list):
            return None, "shape"
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return None, "not the plan's JSON"
    work = jobs(store_value)
    seen, by_crew, ends = set(), {}, {}
    for row in rows:
        try:
            item, crew, start, end = row["id"], row["crew"], row["start"], row["end"]
        except (KeyError, TypeError):
            return None, "row shape"
        if item not in work or item in seen:
            return None, f"unknown or repeated order {item}"
        if not all(type(value) is int for value in (crew, start, end)) or not 1 <= crew <= crews or start < 0 or end - start != work[item][0]:
            return None, f"bad crew, times or hours for {item}"
        seen.add(item)
        by_crew.setdefault(crew, []).append((start, end))
        ends[item] = (start, end)
    if seen != set(work):
        return None, f"{len(set(work) - seen)} orders missing"
    for intervals in by_crew.values():
        intervals.sort()
        if any(previous[1] > following[0] for previous, following in zip(intervals, intervals[1:])):
            return None, "a crew does two orders at once"
    for item, (_, _, before) in work.items():
        if any(ends[other][1] > ends[item][0] for other in before):
            return None, f"{item} starts before a prerequisite ends"
    cost = sum(work[item][1] * end for item, (_, end) in ends.items())
    if reported != cost:
        return None, f"reported cost {reported} is not {cost}"
    return cost, None
