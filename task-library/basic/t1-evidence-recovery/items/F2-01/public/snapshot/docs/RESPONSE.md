# Rolling back a change that caused an incident

An incident file gives its start time (Start). Every fact below is taken at that moment.

## Facts

- tier: the service's effective production tier, by docs/CONFIG.md, as the files stood at the start time.
- class: the class of the change that caused the incident. It is the class in the change record, unless approved
  amendments in changes/amendments/ whose effective time is at or before the start time change it; then the one
  with the latest effective time decides. Rejected amendments change nothing.

## Procedure

The first rule that matches decides:

1. R0: the class is rollback.
2. P2: the class is emergency, or tier 1.
3. P1: any other case.

## Approver

- R0 and P1: the primary on call of the team that owns the service at the start time.
- P2: the secondary on call of that team.

Each service's OWNERS file names its team. The rotations are in oncall/.

## Deadline

The rollback is due a window after the start time: R0 1 hour, P1 12 hours, P2 6 hours.
Give deadlines in UTC as YYYY-MM-DDTHH:MMZ.
