#!/usr/bin/env python3
"""The eight VIS v2 briefs (TASK_LIBRARY §3.5): their prompts, fixed content and the checks each brief states.
`python3 private/briefs.py` writes items/<brief>/prompt.md, items/<brief>/public/content.json
and the anchor pages' private/anchors/<brief>/content.js."""
import json
import pathlib
import random

COMMON_CHECKS = ["renders", "labels", "no-overflow"]
CHECKS = {
    "dashboard": ["kpis", "filter", "chart"],
    "editor": ["open-note", "unsaved", "save"],
    "multistep": ["validation", "review", "navigation", "submit"],
    "landing-fernwood": ["copy", "options", "form-invalid", "form-valid"],
    "landing-quanta": ["prices-monthly", "prices-yearly", "toggle-back", "copy"],
    "mobile-schedule": ["tabs", "favourite", "touch-targets"],
    "catalogue": ["search", "genre", "combined", "sort"],
    "states": ["empty", "error", "loaded", "retry"],
}
# TASK_LIBRARY §3.5: dev 3 briefs, validation 5; a brief is its own structure group.
SPLITS = {"landing-fernwood": "dev", "dashboard": "dev", "multistep": "dev", "editor": "validation", "landing-quanta": "validation",
          "mobile-schedule": "validation", "catalogue": "validation", "states": "validation"}


def dashboard_content():
    rng = random.Random("vis-dashboard")
    regions = ["North", "South", "East", "West"]
    statuses = ["On time"] * 5 + ["Delayed"] * 2 + ["Delivered"] * 3
    shipments = [{"id": f"TW-{4100 + index}", "region": rng.choice(regions), "status": rng.choice(statuses),
                  "eta": f"2026-11-{rng.randint(1, 28):02d}", "weightKg": rng.randint(120, 4800)} for index in range(24)]
    return {"brand": "Tidewater Logistics", "title": "Operations overview", "regions": regions, "allRegions": "All regions",
            "kpis": {"total": "Shipments tracked", "delayed": "Delayed"}, "chartTitle": "Shipments by status", "shipments": shipments}


TITLES = ["The Silent River", "An Atlas of Small Lights", "Northern Gardens", "Letters from the Harbour", "Clockwork Winter", "A Field Guide to Mosses",
          "Notes on Glass", "The Long Orchard", "Salt and Iron", "Maps of the Inland Sea", "The Weather Diaries", "Bridges of Lyon",
          "Paper Moons", "The Copper Kingdom", "Small Hours", "The Mathematics of Rain", "Lanterns", "A Short History of Bread",
          "The Quiet Engine", "Songs for a Cold Coast", "Beekeeping for Beginners", "The Last Cartographer", "Stone Circles",
          "Under the Linden", "Atoms and Orchards", "The Cartwright Papers", "Fen Country", "Rivers of the Moon", "Glass Harbour", "Other Islands"]


def catalogue_content():
    rng = random.Random("vis-catalogue")
    genres = ["Fiction", "History", "Science", "Poetry"]
    books = [{"title": title, "author": rng.choice(["M. Okafor", "L. Brandt", "S. Ito", "R. Delgado", "A. Novak", "J. Kerr"]),
              "genre": rng.choice(genres), "year": rng.randint(1890, 2025)} for title in TITLES]
    return {"brand": "Larkspur Public Library", "title": "Catalogue", "allGenres": "All genres", "genres": genres, "books": books,
            "countFormat": "{n} books", "sortLabel": "Sort by year"}


CONTENT = {
    "dashboard": dashboard_content(),
    "editor": {"brand": "Margin", "tagline": "Notes that stay out of your way", "notes": [
        {"title": "Reading list", "body": "Finish the essay collection.\nStart the field guide to mosses."},
        {"title": "Kitchen ideas", "body": "Try the lentil soup with smoked paprika.\nBuy a second cast-iron pan."},
        {"title": "Trip to the coast", "body": "Book the ferry for Friday.\nPack the waterproof notebook."}],
        "labels": {"title": "Title", "body": "Note", "save": "Save"}, "status": {"saved": "All changes saved", "unsaved": "Unsaved changes"}},
    "multistep": {"brand": "Orbit Coworking", "title": "Join Orbit", "steps": ["Your details", "Choose a plan", "Review"],
                  "fields": {"name": "Full name", "email": "Email"}, "plans": ["Desk", "Team room", "Studio"],
                  "planNotes": {"Desk": "A seat in the open floor", "Team room": "A room for up to six", "Studio": "A private studio with storage"},
                  "buttons": {"next": "Next", "back": "Back", "submit": "Create my membership"},
                  "states": {"error": "Please enter a valid email address.", "success": "Welcome to Orbit. Your membership is ready."}},
    "landing-fernwood": {"brand": "Fernwood", "hero": {"heading": "Gear that lasts longer than the trail.", "subheading": "Repairable outdoor equipment, made in small batches.",
                                                      "cta": "Shop the collection"},
                         "products": [{"name": "Ridgeline Pack 38", "price": "€189", "description": "A 38-litre pack with replaceable straps."},
                                      {"name": "Alder Shell", "price": "€249", "description": "A waterproof shell you can re-proof at home."},
                                      {"name": "Cinder Stove", "price": "€79", "description": "A burner with parts sold one by one."}],
                         "newsletter": {"heading": "Field notes, once a month", "emailLabel": "Email", "interestLabel": "Interest",
                                        "interests": ["Hiking", "Climbing", "Camping"], "button": "Subscribe",
                                        "error": "Enter a full email address, such as name@example.com.", "success": "Thanks. The next field notes are on their way."},
                         "footer": "© 2026 Fernwood · Repairs · Warranty · Contact"},
    "landing-quanta": {"brand": "Quanta", "hero": {"heading": "Bookkeeping that closes itself.", "subheading": "Quanta reconciles your accounts every night."},
                       "billing": {"monthly": "Monthly", "yearly": "Yearly", "note": "Yearly billing: pay for ten months, get twelve."},
                       "yearlyMultiple": 10,
                       "plans": [{"name": "Solo", "monthly": 12, "features": ["1 user", "2 bank feeds"]},
                                 {"name": "Studio", "monthly": 29, "features": ["5 users", "10 bank feeds", "Payroll"]},
                                 {"name": "Firm", "monthly": 79, "features": ["Unlimited users", "Unlimited feeds", "Audit trail"]}],
                       "currency": "$", "cta": "Start free for 30 days"},
    "mobile-schedule": {"brand": "Stackconf 2026", "venue": "Harbour Hall, Gdańsk", "savedFormat": "{n} saved", "days": [
        {"label": "Day 1", "sessions": [{"time": "09:30", "title": "Opening: small tools, long lives", "room": "Main hall"},
                                        {"time": "11:00", "title": "Caching without regret", "room": "Room B"},
                                        {"time": "14:00", "title": "Designing for the slow network", "room": "Main hall"},
                                        {"time": "16:00", "title": "Panel: maintainers at rest", "room": "Room C"}]},
        {"label": "Day 2", "sessions": [{"time": "10:00", "title": "Type systems in the wild", "room": "Room B"},
                                        {"time": "11:30", "title": "Accessible charts", "room": "Main hall"},
                                        {"time": "15:00", "title": "Closing: what we deleted", "room": "Main hall"}]}]},
    "catalogue": catalogue_content(),
    "states": {"brand": "Shelfspace", "title": "Your files", "empty": {"heading": "No files yet", "body": "Files you upload will appear here.", "action": "Upload a file"},
               "error": {"heading": "We could not load your files", "body": "Check your connection and try again.", "action": "Try again"},
               "retryDelayMs": 600,
               "files": [{"name": "budget-2026.xlsx", "size": "84 KB", "modified": "2026-10-02"}, {"name": "site-photos.zip", "size": "212 MB", "modified": "2026-09-28"},
                         {"name": "contract-draft.pdf", "size": "1.2 MB", "modified": "2026-10-11"}, {"name": "notes.md", "size": "6 KB", "modified": "2026-10-20"}]},
}

PROMPTS = {
    "dashboard": """## Brief: an operations dashboard for Tidewater Logistics

**Audience.** Dispatchers who watch it all day on a large screen and check it on a laptop; they need to see trouble at a glance.
**Tone.** Calm, dense, precise. Information first; no marketing.

**Content** (`public/content.json`): the brand, the title, the four regions, the KPI labels, the chart title and 24 shipments (id, region, status, ETA, weight).

**The page must**
- show two KPIs: the number of shipments shown (`data-role="kpi-total"`) and how many of them are Delayed (`data-role="kpi-delayed"`), each as a number;
- list the shipments in a table (`data-role="shipments-table"`, one `tbody` row per shipment, showing at least the id, region, status and ETA);
- offer a region filter (`data-role="region-filter"`, a `select` with "All regions" and the four regions): choosing a region shows only its shipments, and both KPIs then count only those;
- show a chart of shipments by status (`data-role="chart"`, an SVG or canvas you draw, at least 200×120 pixels).
""",
    "editor": """## Brief: a note editor for Margin

**Audience.** People who keep short notes and want a quiet, focused writing surface.
**Tone.** Minimal, warm, typographic.

**Content** (`public/content.json`): the brand, a tagline, three notes, the labels and the two status messages.

**The page must**
- list the notes (`data-role="note-list"`, each note an element with `data-role="note-item"` showing its title);
- edit the selected note in a title field (`data-role="note-title"`, an `input`) and a body field (`data-role="note-body"`, a `textarea`), both labelled; clicking a note item loads it into them;
- show a save status (`data-role="save-status"`): after any edit it reads "Unsaved changes"; the save button (`data-role="save-button"`) saves, the status then reads "All changes saved", and the note item shows the new title.
""",
    "multistep": """## Brief: a three-step membership form for Orbit Coworking

**Audience.** Freelancers and small teams signing up on a laptop or phone.
**Tone.** Friendly, clear, reassuring.

**Content** (`public/content.json`): the steps, field labels, the three plans with notes, button labels, and the error and success messages.

**The page must**
- show which step is current (`data-role="step-indicator"`, reading "Step 1 of 3" and so on);
- step 1: "Full name" and "Email" fields (labelled with exactly those words); "Next" (`data-role="next-button"`) moves on only with a name and a valid email; otherwise it shows the error message in `data-role="form-error"` and stays on step 1;
- step 2: the three plans as radio buttons, each labelled with the plan's name; "Back" (`data-role="back-button"`) returns to the previous step and keeps what was entered;
- step 3: a review (`data-role="review-summary"`) showing the name, the email and the plan, and the submit button (`data-role="submit-button"`), which shows the success message in `data-role="form-success"`.
""",
    "landing-fernwood": """## Brief: a landing page for Fernwood

**Audience.** Hikers and climbers aged 25–55 who buy fewer, better things.
**Tone.** Earthy, honest, quietly confident. Think workshop, not billboard.

**Content** (`public/content.json`): the hero, three products, the newsletter block and the footer. Use the copy exactly.

**The page must**
- open with the hero (`data-role="hero"`) carrying the heading and subheading;
- show the three products, each in an element with `data-role="product-card"` (name, price, description);
- have a newsletter form (`data-role="newsletter-form"`) with an "Email" field and an "Interest" select whose options are exactly Hiking, Climbing and Camping (a placeholder option with an empty value is allowed), and a subscribe button;
- on submit, an email that is not a full address (it needs a name, an "@", a domain and a dot in it) shows the error message in `data-role="form-error"` and never the success message; a valid one shows the success message in `data-role="form-success"`.
""",
    "landing-quanta": """## Brief: a pricing page for Quanta

**Audience.** Owners of small firms comparing accounting tools; sceptical, busy, on desktop.
**Tone.** Crisp, trustworthy, modern finance without coldness.

**Content** (`public/content.json`): the hero, the billing labels and note, three plans with monthly prices and features, the currency and the call to action.

**The page must**
- show the three plans, each in an element with `data-role="plan-card"`, with its price in an element with `data-role="plan-price"` (the number, with the currency sign if you like);
- start on monthly prices; a billing toggle (`data-role="billing-toggle"`, a button or a switch) switches to yearly prices, which are the monthly price × 10 (the yearly note explains why), and back.
""",
    "mobile-schedule": """## Brief: a phone-first schedule for Stackconf 2026

**Audience.** Conference attendees checking the programme on their phones between talks.
**Tone.** Lively but legible; one hand, one thumb.

**Content** (`public/content.json`): the brand, the venue, the saved-count format and two days of sessions.

**The page must** (checked at 390×844 first, and still work at 1440×900)
- offer one tab per day (`data-role="day-tab"`); the selected day's sessions are shown and the other day's are hidden;
- show each session in an element with `data-role="session"` (time, title, room) containing a favourite button (`data-role="favourite-button"`, at least 24×24 pixels) that toggles its `aria-pressed` between "true" and "false";
- show how many sessions are saved (`data-role="saved-count"`, "N saved").
""",
    "catalogue": """## Brief: a catalogue table for Larkspur Public Library

**Audience.** Library visitors of all ages searching the collection on a desktop terminal.
**Tone.** Welcoming, civic, very readable.

**Content** (`public/content.json`): the brand, the title, the genres, 30 books (title, author, genre, year), the count format and the sort label.

**The page must**
- show the books in a table (`data-role="books-table"`, one `tbody` row per book shown, with title, author, genre and year);
- filter by a search field (`data-role="search-input"`, labelled; case-insensitive "title contains"), and by genre (`data-role="genre-filter"`, a `select` with "All genres" first), both at once;
- show how many books are listed (`data-role="results-count"`, "N books");
- sort by year, oldest first, when the sort control (`data-role="sort-year"`) is clicked.
""",
    "states": """## Brief: empty, error and loaded states for Shelfspace

**Audience.** People managing their files; the states must reassure and tell them what to do.
**Tone.** Gentle, clear, a little playful.

**Content** (`public/content.json`): the brand, the title, the empty and error copy, the retry delay and four files.

**The page must** show exactly one state at a time, chosen by the address's fragment:
- `index.html#empty`: the empty state (`data-role="state-empty"`) with its heading, text and action;
- `index.html#error`: the error state (`data-role="state-error"`) with its heading and text, and a retry button (`data-role="retry-button"`); clicking it shows the loaded state within the retry delay plus a little;
- `index.html#loaded`: the loaded state (`data-role="state-loaded"`) listing the four files (name, size, modified date).
""",
}


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    for brief, prompt in PROMPTS.items():
        public = root / "items" / brief / "public"
        public.mkdir(parents=True, exist_ok=True)
        (root / "items" / brief / "prompt.md").write_text(prompt, encoding="utf-8")
        (public / "content.json").write_text(json.dumps(CONTENT[brief], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        # The anchor pages read the same content, injected as a script (file:// pages cannot fetch JSON).
        anchor = root / "private" / "anchors" / brief
        anchor.mkdir(parents=True, exist_ok=True)
        (anchor / "content.js").write_text("window.CONTENT = " + json.dumps(CONTENT[brief], ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
