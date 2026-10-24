## Specification: recur.py, a recurrence expander

Write `recur.py` at the workspace root. `python3 recur.py <input.json>` reads recurrence rules, expands each one into its dates, prints one JSON object to standard output, then exits 0. Use only the Python standard library.

### Input

    {"rules": [{"id": "standup", "start": "2026-03-02", "freq": "weekly", "days": ["MO", "TH"], "count": 4}]}

Every rule is an object with a string `id`; ids are unique. Dates are strings in the form `YYYY-MM-DD` and must be real calendar dates, so `"2026-02-30"` and `"2026-3-02"` are not dates. Weekdays are written `MO`, `TU`, `WE`, `TH`, `FR`, `SA`, `SU`.

### Rule fields

| Field | Meaning |
| --- | --- |
| `start` | Required. The first date that may occur. No occurrence is ever earlier than `start`. |
| `freq` | Required: `daily`, `weekly`, `monthly` or `yearly`. |
| `interval` | A positive integer, default 1: every `interval` days, weeks, months or years. |
| `count` | A positive integer: stop after this many occurrences. |
| `until` | A date: stop after this date. `until` itself may occur. |
| `days` | `weekly` only: a non-empty list of weekdays. Default: the weekday of `start`. |
| `monthday` | `monthly` only: a day of the month from 1 to 31. Default: the day of `start`, unless `nth` is given. |
| `nth` | `monthly` only: `[n, weekday]`, the n-th such weekday of the month, with n from 1 to 5, or from −1 to −5 counting from the end of the month (−1 is the last). |
| `overflow` | `monthly` and `yearly` only: `"skip"` (default) or `"clamp"`. See below. |
| `except` | A list of dates removed from the result. |

Exactly one of `count` and `until` must be given.

### Expansion

- **daily:** `start`, then every `interval` days.
- **weekly:** weeks run Monday to Sunday. The week that contains `start` is week 0. The rule occurs on each listed weekday of weeks 0, `interval`, 2×`interval`, and so on, except on days before `start`.
- **monthly:** the month of `start` is month 0. The rule occurs once in months 0, `interval`, 2×`interval`, and so on: on day `monthday`, or on the `nth` weekday. A month without that day (such as day 31 in April, or a fifth Friday that does not exist) has no occurrence with `overflow: "skip"`. With `"clamp"`, it occurs on the month's last day instead; `clamp` does not apply to `nth`, where a missing weekday is always skipped. Dates before `start` are dropped, so `start` need not itself be an occurrence.
- **yearly:** on the month and day of `start`, in the year of `start` and every `interval` years after it. A 29 February start has no occurrence in years without 29 February with `skip`, and occurs on 28 February with `clamp`.
- **Counting and exceptions.** Occurrences are generated in date order. `count` counts generated occurrences, **including** those that `except` later removes; so a rule with `count: 3` and one excepted occurrence yields 2 dates. With `until`, every occurrence up to and including `until` is generated. An `until` before `start` yields an empty list.
- **Limits.** Nothing after 2099-12-31 is ever generated, even if `count` asks for more. A rule that would generate more than 1000 occurrences (before exceptions) is invalid.

### Invalid rules

A rule is `"INVALID"` when any of these holds:

- `start` is missing or not a date;
- `freq` is not one of the four values;
- `interval` is given and is not a positive integer;
- `count` and `until` are both given, or neither is; `count` is not a positive integer; or `until` is not a date;
- a field is used with the wrong `freq` (`days` outside `weekly`; `monthday` or `nth` outside `monthly`; `overflow` outside `monthly` and `yearly`);
- `days` is empty or has an unknown weekday; `monthday` is not an integer from 1 to 31; `nth` is not a pair of a valid n and a weekday; or `monthday` and `nth` are both given;
- `overflow` is not `"skip"` or `"clamp"`; `except` is not a list of dates;
- the rule would generate more than 1000 occurrences.

Integers must be JSON integers: `2` is an integer, and `2.0`, `"2"` and `true` are not.

### Output

Print one JSON object with one key per rule id. The value is the list of dates, as `YYYY-MM-DD` strings in increasing order, or the string `"INVALID"`.

### Examples

    {"rules": [
      {"id": "a", "start": "2026-01-31", "freq": "monthly", "count": 4},
      {"id": "b", "start": "2026-01-31", "freq": "monthly", "count": 4, "overflow": "clamp"},
      {"id": "c", "start": "2026-03-02", "freq": "weekly", "days": ["MO", "TH"], "count": 4, "except": ["2026-03-05"]},
      {"id": "d", "start": "2026-01-01", "freq": "monthly", "nth": [-1, "FR"], "until": "2026-03-31"}
    ]}
    -> {"a": ["2026-01-31", "2026-03-31", "2026-05-31", "2026-07-31"],
        "b": ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"],
        "c": ["2026-03-02", "2026-03-09", "2026-03-12"],
        "d": ["2026-01-30", "2026-02-27", "2026-03-27"]}

Deliver `recur.py` and a short README.md. Test your implementation against your own cases. The hidden tests cover every rule above, and each rule area is scored separately.
