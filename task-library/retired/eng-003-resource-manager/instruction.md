# Task: Local Resource Manager (eng-003, Stateful Interactive Application)

Build a single-user local web application from an empty directory for managing bookmarks/resources. It must support form entry, local persistence, import/export, and error recovery. Functionality, engineering quality, and visual design are evaluated separately; see the rubric for human review of design. Interfaces and semantics below are fixed; internal design is yours.

## Runtime

- Python 3.13, standard library only (including http.server, json, csv, os, re, and urllib). No third-party dependencies, network services, or database server. Persist to a JSON file.
- Single-user local application with no authentication.

## Deliverables and layout

- service.py exports ResourceStore, the functional core that headless tests can import.
- server.py uses stdlib http.server to expose ResourceStore as a local HTTP API and serve frontend/ static files. Start with python server.py --store <path> --port <p>.
- frontend/ contains index.html, app.js, and style.css for the form UI.
- README.md documents usage, API, data format, recovery semantics, and assumptions about unspecified details.

## Data model

A Resource has {id, title, url, tags, notes, created_at, updated_at}.
- id is a string integer allocated deterministically from next_id (one greater than the current maximum; initially 1).
- tags is an array of strings. created_at and updated_at are numeric timestamps. Allow a clock to be injected at construction for testing.
- Persist JSON as {"next_id": <int>, "resources": [<Resource>...]}.

## ResourceStore API

    ResourceStore(path, clock=None)
      .add(title, url, tags=None, notes=None) -> Result
      .edit(id, title=None, url=None, tags=None, notes=None) -> Result
      .delete(id) -> Result
      .get(id) -> Result
      .list(tag=None, text=None) -> [Resource]  # ascending numeric id
      .export(fmt="json"|"csv") -> str
      .import_data(payload, fmt="json"|"csv", mode="merge"|"replace") -> Result
      property .recovered_from_corrupt: bool

Result = {"ok": bool, "resource"?: Resource, "errors"?: [{"field","code","value"?,"record"?}], "added"?: int, "updated"?: int}.

## Validation

- title is required, non-empty after trimming, and at most 200 characters. Errors: title/required or title/too_long.
- url is required and must match ^https?://\S+$. Errors: url/required or url/invalid_format.
- tags must be an array of strings. Trim each item, discard empty strings, and deduplicate in first-seen order. At most 20 tags and at most 50 characters per tag; errors are tags/too_many or tags/tag_too_long. Wrong type: tags/invalid_type.
- notes is an optional string of at most 5,000 characters; otherwise notes/too_long.
- edit is a partial update and validates only supplied fields. A missing id returns id/not_found.
- Validation failure must not change in-memory state or persist anything.

## Persistence and recovery

- Atomic writes: write to <path>.part, then os.replace to path. Persist after each mutation.
- On load, a missing file means an empty store. Invalid JSON or invalid structure means recover to an empty store, move the damaged file to <path>.corrupt, set recovered_from_corrupt=true, and do not crash.

## Import and export

- export("json") returns {"resources":[...]}, sorted by id, with sorted keys and indent=2.
- export("csv") uses header id,title,url,tags,notes,created_at,updated_at; join tags with ; and use RFC 4180 quoting.
- import_data validates the entire payload before changing state. Duplicate IDs within the payload produce id/duplicate_in_payload. Any error returns {"ok":false,"errors":[...]} with a record index on every error, and leaves state entirely unchanged.
- Invalid JSON/CSV returns payload/parse_error and leaves state unchanged.
- merge updates existing IDs and inserts new or missing IDs; allocate missing IDs from next_id and advance next_id.
- replace clears the store, then inserts the payload.
- Success returns {"ok":true,"added":n,"updated":m,"mode":...}.

## HTTP API

- GET /resources?tag=&text= -> 200 {"ok":true,"resources":[...]}
- POST /resources with a JSON body -> 201 on success, or 400 with validation errors.
- GET /resources/<id> -> 200 or 404.
- PUT /resources/<id> -> 200, 400 on validation failure, or 404.
- DELETE /resources/<id> -> 200 or 404; deleting an id twice returns 404 on the second request.
- GET /export?fmt=json|csv -> text response.
- POST /import with {payload,fmt,mode} -> 200 or 400.
- GET / and static asset paths serve the frontend.

## Frontend behavior

- Provide an add/edit form for title, url, tags, and notes. After submit, show success or per-field validation feedback.
- Show a list of id, title, link, and tags, with tag and text filters.
- Make empty, error, and success states visible.
- Provide JSON/CSV export buttons and file import with automatic JSON/CSV detection and merge/replace selection.
- Support desktop and phone viewports. Visual quality is reviewed by people, not pixel-level automation.

## Out of scope

Authentication, multiple users, remote deployment, database servers, frontend frameworks, and performance are out of scope. Internal implementation is unrestricted.
