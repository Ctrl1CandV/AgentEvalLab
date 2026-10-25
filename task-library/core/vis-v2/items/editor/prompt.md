## Brief: a note editor for Margin

**Audience.** People who keep short notes and want a quiet, focused writing surface.
**Tone.** Minimal, warm, typographic.

**Content** (`public/content.json`): the brand, a tagline, three notes, the labels and the two status messages.

**The page must**
- list the notes (`data-role="note-list"`, each note an element with `data-role="note-item"` showing its title);
- edit the selected note in a title field (`data-role="note-title"`, an `input`) and a body field (`data-role="note-body"`, a `textarea`), both labelled; clicking a note item loads it into them;
- show a save status (`data-role="save-status"`): after any edit it reads "Unsaved changes"; the save button (`data-role="save-button"`) saves, the status then reads "All changes saved", and the note item shows the new title.
