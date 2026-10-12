# Public Contract: Resource Index CLI

Repository input is a UTF-8 JSON object of the form {"resources":[...]}. Each record has id, title, tags, and a non-negative integer rank. index emits a stable ascending resource list. export --format json preserves every field. export --format csv emits columns id,title,tags,rank and joins tags with |.

## Search

Command:

    node --experimental-strip-types src/cli.ts search --input <path-or-> --query <text> [--offset N] [--limit N]

- Search literal substrings in title and each tag; do not search id. Trim query whitespace and compare query and text using toLocaleLowerCase("en-US").
- Sort matching results by id in Unicode code-point order, then apply zero-based offset and limit. Defaults: offset 0, limit 20.
- Emit one JSON object: {"items": Resource[], "total": number, "offset": number, "limit": number, "nextOffset": number|null}.
- total is the number of matches before pagination. If more results remain, nextOffset = offset + items.length; otherwise null. An offset beyond the end is a valid empty page.
- offset must be a non-negative safe integer; limit must be a positive safe integer. Reject missing, repeated, or unknown options, invalid numbers, and blank queries with a non-zero exit code. Do not emit success-shaped JSON on failure.
- Output must not depend on input order, system locale, current time, or randomness.

## Existing behavior and CSV repair

- index and JSON export preserve all input fields. Do not drop rank: 0, empty tag arrays, or empty strings due to truthiness checks.
- CSV is UTF-8, uses columns id,title,tags,rank, CRLF line endings, and ends with CRLF. Fields containing commas, double quotes, CR, or LF must be quoted. Double each embedded quote. Leave fields that need no quoting unchanged.
- Join tags using the literal | character. An empty array produces an empty field.

## Out of scope

Fuzzy search, relevance ranking, network queries, databases, and new dependencies are out of scope. Any correct internal data structures, function boundaries, and algorithms are acceptable.
