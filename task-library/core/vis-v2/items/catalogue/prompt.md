## Brief: a catalogue table for Larkspur Public Library

**Audience.** Library visitors of all ages searching the collection on a desktop terminal.
**Tone.** Welcoming, civic, very readable.

**Content** (`public/content.json`): the brand, the title, the genres, 30 books (title, author, genre, year), the count format and the sort label.

**The page must**
- show the books in a table (`data-role="books-table"`, one `tbody` row per book shown, with title, author, genre and year);
- filter by a search field (`data-role="search-input"`, labelled; case-insensitive "title contains"), and by genre (`data-role="genre-filter"`, a `select` with "All genres" first), both at once;
- show how many books are listed (`data-role="results-count"`, "N books");
- sort by year, oldest first, when the sort control (`data-role="sort-year"`) is clicked.
