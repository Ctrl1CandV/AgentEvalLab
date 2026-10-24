## Instance L4-03

Staff a roster for 7 days (Day 1 to Day 7). Each day has the shifts early, day, late, in that order; the first shift is early and the last is late.
People: Ada, Bram, Esme, Finn, Jude, Kai, Lena.

Rules:

- coverage: Every shift is staffed by exactly 1 different person. This rule always applies.
- apart: These pairs never work the same shift: Ada and Finn; Bram and Jude; Finn and Kai.
- availability: Nobody works on a day listed as unavailable for them.
- max_shifts: Nobody works more than 3 shifts in total.
- min_shifts: Everybody works at least 2 shifts in total.
- one_per_day: Nobody works more than one shift on the same day.
- rest: Nobody works the last shift of a day and the first shift of the next day.

Unavailable days:

- Ada: Day 3, Day 7
- Bram: Day 7
- Esme: Day 3, Day 6, Day 7
- Finn: Day 3, Day 7
- Kai: Day 4, Day 7
- Lena: Day 3, Day 7
