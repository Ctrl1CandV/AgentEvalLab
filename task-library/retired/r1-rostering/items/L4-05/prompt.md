## Instance L4-05

Staff a roster for 7 days (Day 1 to Day 7). Each day has the shifts early, day, late, in that order; the first shift is early and the last is late.
People: Ada, Cleo, Dov, Finn, Gia, Hugo, Lena.

Rules:

- coverage: Every shift is staffed by exactly 1 different person. This rule always applies.
- apart: These pairs never work the same shift: Cleo and Dov; Cleo and Hugo; Cleo and Lena.
- availability: Nobody works on a day listed as unavailable for them.
- max_shifts: Nobody works more than 3 shifts in total.
- min_shifts: Everybody works at least 2 shifts in total.
- one_per_day: Nobody works more than one shift on the same day.
- rest: Nobody works the last shift of a day and the first shift of the next day.

Unavailable days:

- Dov: Day 1, Day 3, Day 7
- Finn: Day 4, Day 7
- Gia: Day 2, Day 4, Day 6
- Hugo: Day 2, Day 3, Day 4
