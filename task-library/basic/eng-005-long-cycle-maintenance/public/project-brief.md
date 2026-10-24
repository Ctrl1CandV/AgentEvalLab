# Project Brief

This is a local, single-user work order tool. The state file is data/work-orders.json. Successful commands emit JSON on stdout except CSV export. Failures return a non-zero exit code. Preserve existing commands, fields, and seed work orders unless a stage explicitly requires a change.

Key constraints: no network, services, or third-party dependencies. Seed data includes empty descriptions, repeated timestamps, and multiple statuses. Invalid operations must not partially write state. All ordering must be deterministic and stable. Refer to the current stage brief for command details.
