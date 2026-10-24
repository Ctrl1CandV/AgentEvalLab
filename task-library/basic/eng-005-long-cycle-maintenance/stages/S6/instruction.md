# S6: Scale

The tool now runs against stores of 100,000 work orders and more. Dependency chains can run tens of thousands of orders deep, prerequisites can fan out widely, and many paths can lead through the same orders. Every command must stay correct at this size and become fast; keep the version 2 store format, the CLI, and every earlier behaviour.

`public/make_store.py` writes such a store for testing: `python3 public/make_store.py data/scale-test.json` (it does not touch data/work-orders.json). Point a copy of the project at it to try your commands.

Hidden checks run a fixed workload on another store of this kind, one command at a time on one CPU core: list pages with filters and sorts by createdAt and id, show, dependency additions that do and do not close a cycle through long chains and many paths, completions with and without finished prerequisites, a create and a rename.

- `scale.list`, `scale.dependencies`, `scale.status`: each command's output and the final store match our reference implementation (error codes and the store's contents are compared, not messages or timestamps).
- `scale.speed-3`, `scale.speed-1.5`, `scale.speed-1.1`, `scale.speed-0.75`: the whole workload takes at most 3, 1.5, 1.1 and 0.75 times as long as our reference implementation (best of three runs). These need the three checks above.

Earlier stages' checks keep running on your delivery. Update README with what changed.
