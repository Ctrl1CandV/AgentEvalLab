# S7: Planning

Crews now work through the orders, and the tool must plan their work.

Work orders may carry two new fields: `hours`, the work's duration in whole hours (a positive integer, 1 when absent), and `priority`, from 1 to 5 (1 when absent). Every earlier command keeps both fields as they are; `create` does not set them.

Add `plan --crews N`, where N is an integer from 1 to 50; any other value, a missing value or any other option is `INVALID_ARGUMENT`. It schedules every work order that is not DONE on N identical crews and prints one JSON object:

    {"crews": 2, "cost": 57, "schedule": [{"id": "WO-101", "crew": 1, "start": 0, "end": 3}, ...]}

- Each crew does one order at a time, from its start to its end without a break, and end − start is the order's hours. Times are whole hours from 0, when the plan begins; crews are numbered from 1.
- An order starts only after every prerequisite that is not DONE has ended. Prerequisites that are DONE impose nothing.
- `cost` is the sum, over the schedule, of priority × end. Make it as small as you can.
- `plan` reads the store and never writes it. A store whose `hours` or `priority` values are invalid is `STORE_INVALID`.
- Each `plan` run must finish within 10 seconds on one CPU core, including on the 100,000-order stores of S6.

`public/make_plan_store.py` writes sample stores with these fields (`python3 public/make_plan_store.py --help`), and `public/plan_tools.py` holds the plan validation and the naive and greedy plans described below, which the checks use.

Hidden checks run `plan` on stores of several kinds: a handful of orders on two or three crews, chains of orders on one crew, a few hundred orders and a few thousand on several crews, all with dependencies, and the S6 scale store.

- `plan.valid-small`, `plan.valid-large`, `plan.valid-scale`: every plan is valid as above, its cost is reported right, and it finishes in time.
- `plan.read-only`, `plan.errors`, `plan.fields-preserved`: the store is left as it was, invalid input gets the right error codes, and earlier commands keep `hours` and `priority`.
- `plan.quality-25` to `plan.quality-97`: on each store except the scale store, the plan's cost is placed on a scale:
  - **0** is the plan that repeatedly takes the lowest id whose prerequisites are planned, starting it on the crew free first as soon as that crew is free and its prerequisites have ended;
  - **0.5** is the greedy plan: whenever a crew is free (the lowest-numbered first), it starts the ready order with the highest priority per hour (ties by id); when no order is ready, it waits for the next order to end;
  - **1** is the best plan we know for that store: the optimum where it can be proved, the best of a long search otherwise.

  The place is linear between these points and stays within 0 and 1; an invalid plan is placed at 0. The checks pass when the mean place over those stores reaches 0.25, 0.5, 0.65, 0.8, 0.9 and 0.97.

Earlier stages' checks keep running on your delivery. Update README with the new command and fields.
