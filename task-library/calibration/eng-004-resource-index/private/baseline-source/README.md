# Resource Index CLI

A small command-line tool over a resource repository file, `{"resources": [...]}`, where each record has an `id`, a `title`, `tags` and a non-negative integer `rank`. It runs on Node.js 22 with native TypeScript type stripping and has no dependencies.

    node --experimental-strip-types src/cli.ts index --input <path-or->
    node --experimental-strip-types src/cli.ts export --input <path-or-> --format json|csv

- `index` prints the resources in ascending id order as `{"resources": [...]}`.
- `export --format json` prints the same; `export --format csv` prints the columns id, title, tags and rank, with tags joined by `|`.
- `--input -` reads the repository from standard input.
- On failure a command prints an error code to standard error and exits with code 2.

Source: `src/cli.ts` (commands), `src/catalog.ts` (validation), `src/index.ts` (ordering), `src/export.ts` (output), `src/types.ts`.

Tests: `node --experimental-strip-types --test tests/baseline.test.mjs`.
