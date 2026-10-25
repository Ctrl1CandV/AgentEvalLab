## Brief: empty, error and loaded states for Shelfspace

**Audience.** People managing their files; the states must reassure and tell them what to do.
**Tone.** Gentle, clear, a little playful.

**Content** (`public/content.json`): the brand, the title, the empty and error copy, the retry delay and four files.

**The page must** show exactly one state at a time, chosen by the address's fragment:
- `index.html#empty`: the empty state (`data-role="state-empty"`) with its heading, text and action;
- `index.html#error`: the error state (`data-role="state-error"`) with its heading and text, and a retry button (`data-role="retry-button"`); clicking it shows the loaded state within the retry delay plus a little;
- `index.html#loaded`: the loaded state (`data-role="state-loaded"`) listing the four files (name, size, modified date).
