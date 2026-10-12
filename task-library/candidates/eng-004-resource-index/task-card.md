# Candidate Task Card: eng-004 Resource Index

- ID: `eng-004-resource-index`; family: resource-index maintenance
- Status: calibrated for development use; not frozen
- Baseline: pinned TypeScript repository and commit
- Task: add literal title/tag search, Unicode code-point ordering, default and explicit pagination, argument validation, and RFC 4180 CSV export.
- Regression: preserve existing index and JSON export fields and values.
- Evidence: two independent references passed the recorded checks; targeted pagination and CSV mutations were rejected.
- Limits: small synthetic repository; not representative of a large production codebase or long-horizon maintenance.
