## Brief: a phone-first schedule for Stackconf 2026

**Audience.** Conference attendees checking the programme on their phones between talks.
**Tone.** Lively but legible; one hand, one thumb.

**Content** (`public/content.json`): the brand, the venue, the saved-count format and two days of sessions.

**The page must** (checked at 390×844 first, and still work at 1440×900)
- offer one tab per day (`data-role="day-tab"`); the selected day's sessions are shown and the other day's are hidden;
- show each session in an element with `data-role="session"` (time, title, room) containing a favourite button (`data-role="favourite-button"`, at least 24×24 pixels) that toggles its `aria-pressed` between "true" and "false";
- show how many sessions are saved (`data-role="saved-count"`, "N saved").
