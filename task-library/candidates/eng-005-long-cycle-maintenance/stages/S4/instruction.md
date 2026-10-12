# S4: v1 to v2 Store Migration and Event History

Upgrade data/work-orders.json to version 2 with this shape: {"version":2,"workOrders":[...],"events":[...]}. Automatically migrate a version 1 file on its first successful write. Read-only commands must not rewrite the file. Preserve every existing work-order field and value; a missing dependsOn may be added as an empty array.

- Migration adds exactly one state_migrated event. Each successful create, update, or dependency change adds one event. Event fields are sequence (contiguous, starting at 1), stable type, orderId (null for migration), and ISO timestamp at.
- Repeated writes to a version 2 file must not add another migration event. Event sequence numbers continue increasing.
- After migration, list, show, and export json retain their existing CLI shape and result. Failed operations do not write state.
- Write a temporary file, then atomically replace the state file to avoid partial JSON after interruption.

Use the public version 1 fixture for migration checks. Do not rely on the repository's current data still being unmigrated.
