# S2: Dependencies and Completion Rules

Add depends add <work-order-id> <prerequisite-work-order-id> to the existing CLI. Work order JSON gains dependsOn: string[]. Treat existing records without this field as having an empty array.

- Reject self-dependencies, duplicate dependencies, unknown work orders, and any dependency that creates a directed cycle.
- Status may advance only OPEN -> IN_PROGRESS -> DONE. Do not skip a state or move backward from DONE.
- A work order can move to DONE only after all prerequisites are DONE.
- Failed operations must not partially write state. Successful dependency operations must preserve S1 queries and baseline commands.

Update README with the dependency command and status rules. Do not reset or rebuild the data file.
