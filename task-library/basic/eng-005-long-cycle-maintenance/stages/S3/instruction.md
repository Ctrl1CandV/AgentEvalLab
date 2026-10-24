# S3: Public Reproductions and Failure Atomicity

Use the public reproduction cases in public/cases.json to check self-dependency, dependency cycles, and invalid status changes. If the current implementation already behaves correctly, demonstrate and preserve that behavior; do not introduce a defect just to fix it later.

Rejected operations must leave data/work-orders.json byte-for-byte unchanged. In particular, do not leave partial state if an operation first adds a dependency and later detects a cycle, or first changes status and later finds an incomplete prerequisite. Preserve S1 queries, S2 dependency rules, and every baseline record.
