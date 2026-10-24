# Rubric: AP stockroom 0.1.0

- The grader replays the simulator's command log on the item's scenario. Days not reached are advanced with no orders.
- `completed` (critical): the model ended day 40 itself.
- Not critical, recorded: `no-invalid-actions` (no rejected order), `no-duplicate-orders` (no order line repeated the same day under another reference), `no-overflow` (no unit refused for lack of capacity). Their cost is their effect on the profit.
- Primary: `profit`, normalised per item through the myopic policy's profit (0) and the strong policy's (1), uncapped; 0 when not completed. Raw values: `profit`, `bound` (hindsight optimum with capacity and cash relaxed), `regret` (bound − profit), the hard-constraint counts, `lostUnits`, `daysManaged`.
