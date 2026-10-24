# Rolling back a change that caused an incident

An incident file gives its start time (Start). Every fact below is taken at that moment.

## Facts

- tier: the service's effective production tier, by docs/CONFIG.md, as the files stood at the start time.
- freeze: whether a change freeze applies to the service (calendar/freezes.md). A freeze applies to every service
  while it runs, except services of tier 3 and the services it exempts by name.
- class: the class of the change that caused the incident. It is the class in the change record, unless approved
  amendments in changes/amendments/ whose effective time is at or before the start time change it; then the one
  with the latest effective time decides. Rejected amendments change nothing.
- reach: the number of other services whose effective production upstream is the service, as the files stood at
  the start time.

## Procedure

The first rule that matches decides:

1. R0: the class is rollback.
2. P4: tier 1, and a freeze applies.
3. P3: reach 3 or more.
4. P2: the class is emergency, or tier 1.
5. P1: any other case.

## Approver

- R0 and P1: the primary on call of the team that owns the service at the start time.
- P2: the secondary on call of that team.
- P3 and P4: the incident commander at the start time.

Each service's OWNERS file names its team. The rotations are in oncall/.
A swap in oncall/swaps.md replaces the person it names, in the role it names, for the time it gives.

## Deadline

The rollback is due a window after the start time: R0 1 hour, P1 12 hours, P2 6 hours, P3 4 hours, P4 2 hours.
The P1 and P2 windows are halved while a freeze applies to the service.
Give deadlines in UTC as YYYY-MM-DDTHH:MMZ.
