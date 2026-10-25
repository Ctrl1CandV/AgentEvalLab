## Specification: routes.py, delivery route planning

Write `routes.py` at the workspace root. `python3 routes.py <instance.json>` reads one instance and prints one JSON object, a plan of delivery routes, to standard output, then exits 0. Use only the Python standard library, and one process with one thread.

This item is an optimisation problem: every feasible plan is valid, and better plans score higher. The directory `public/` holds two sample instances, `public/samples/s1.json` and `public/samples/s2.json`; their costs, in `public/samples/costs.json` (see Scoring); and `public/evaluate.py`: `python3 public/evaluate.py <instance.json> <plan.json>` checks a plan and prints its cost.

### Instance

    {"depot": [500.0, 500.0], "speed": 4.0, "max_duration": 480,
     "vans": [{"id": "V01", "capacity": 100, "cold": true}, {"id": "V02", "capacity": 100, "cold": false}, ...],
     "customers": [{"id": "C001", "x": 312.4, "y": 77.0, "demand": 12, "service": 7, "cold": false}, ...]}

Positions are in distance units, `speed` in distance units per minute, `service` and `max_duration` in minutes.

### Plan

    {"routes": {"V01": ["C014", "C003", ...], "V02": [...], ...}}

Each van drives at most one route: it leaves the depot, visits its customers in the listed order, and returns to the depot. A van may be left out or given an empty list. A plan is **feasible** when:

- every customer is visited exactly once;
- the demands on a route add up to at most the van's `capacity`;
- the route's duration is at most `max_duration`, where the duration is its length divided by `speed` plus the `service` minutes of its customers;
- every customer with `"cold": true` rides in a van with `"cold": true`.

A route's **length** is the sum of the straight-line (Euclidean) distances along it, depot to first customer to ... to last customer to depot. The plan's **cost** is the total length of its routes. Lower is better.

### Scoring

`routes.py` is run on eight hidden instances of the same kind as the samples, with 50 to 800 customers. They are run one at a time on one CPU core.

- It must print its plan within **8 seconds of CPU time** (user and system time of every process it starts; it runs on one core). It is stopped at 10 seconds of CPU time, or at 30 seconds of wall time. Waiting costs no CPU time; computing does, whatever else the machine is doing.
- An infeasible plan, invalid JSON, a crash or a timeout earns nothing for that instance.
- For a feasible plan, take how far its cost gets from the cost of a simple **baseline** (nearest neighbour: each van in turn takes the nearest customer that still fits, refrigerated customers first) towards the **best cost we know**. Four checks per instance pass at 50%, 80%, 90% and 97% of that way.

`public/samples/costs.json` gives both costs for the samples:

    {"s1": {"baseline": ..., "best": ...}, "s2": {"baseline": ..., "best": ...}}

Also write `README.md`, describing your method in a few lines.
