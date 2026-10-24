# Work Order CLI (Reference Implementation B)

Reference B is one valid implementation of the eng-005 contract after all five stages. Its internal organization differs from Reference A; scoring compares behavior, not source similarity.

## Usage

Node.js 22 with TypeScript type stripping; no dependencies or network access:

    node --experimental-strip-types src/cli.ts <command> [options]

| Command | Result |
| --- | --- |
| `list [--status OPEN\|IN_PROGRESS\|DONE] [--sort createdAt\|title\|id] [--order asc\|desc] [--page N] [--page-size N]` | `{"total","page","pageSize","pages","items"}` |
| `show <id>` | One work order |
| `create <id> <title>` | The created work order |
| `update <id> [--status S] [--title T] [--description D]` | The updated work order |
| `depends add <id> <prerequisite-id>` | The updated work order |
| `export json` | All work orders as a JSON array |

## Query and pagination

Sorting defaults to `createdAt` ascending; ties are broken by id ascending. Pagination is one-based: `--page` defaults to 1 and `--page-size` defaults to 2, with an allowed range of 1 through 100. Zero, non-integers, out-of-range values, and unknown or repeated options are rejected. An empty page keeps the same output shape.

## Dependencies and status rules

Each work order has `dependsOn: string[]`; records without the field are treated as having no dependencies. Self-dependencies, duplicates, unknown work orders, and dependencies that would create a cycle are rejected. Status moves only `OPEN -> IN_PROGRESS -> DONE`, and a work order can become `DONE` only after all of its dependencies are `DONE`. A rejected command leaves `data/work-orders.json` byte-for-byte unchanged.

## Error codes

Every failure prints one JSON line to stdout, `{"ok":false,"error":{"code":"...","message":"..."}}`, writes nothing to stderr, and exits with code 2. Stable error codes: `INVALID_ARGUMENT`, `NOT_FOUND`, `DUPLICATE_ID`, `INVALID_STATUS_TRANSITION`, `SELF_DEPENDENCY`, `DEPENDENCY_CYCLE`, `DEPENDENCY_NOT_COMPLETE`, `STORE_INVALID`, and `UNKNOWN_COMMAND`.

## Storage, migration, and events

The state file is `data/work-orders.json`. A version 1 file (`{"version":1,"workOrders":[...]}`) is migrated to version 2 (`{"version":2,"workOrders":[...],"events":[...]}`) on the first successful write; read-only commands never rewrite it. Migration preserves every work-order field and adds one `state_migrated` event. Each successful `create`, `update`, or `depends add` appends one event (`created`, `updated`, or `dependency_added`).

Event fields are `sequence` (contiguous from 1), `type`, `orderId` (`null` for migration), and `at` (ISO timestamp). Writes go to a temporary file that atomically replaces the state file.
