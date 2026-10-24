# Task: Resource Index CLI Maintenance (eng-004)

In the current Git repository, implement the change described in public/task-contract.md while preserving the public behavior of existing commands. The contract lists new requirements and regression requirements.

First inspect the repository structure, README.md, and the public contract. Organize implementation and checks as needed. Do not bind behavior to a particular filename or algorithm. Dependencies and network access are unavailable. After completion, briefly report the changes and checks performed.

Execution baseline: Node.js 22 native TypeScript type stripping. Existing commands:

    node --experimental-strip-types src/cli.ts index --input public/catalog.json
    node --experimental-strip-types src/cli.ts export --input public/catalog.json --format json
    node --experimental-strip-types src/cli.ts export --input public/catalog.json --format csv
    node --experimental-strip-types --test tests/baseline.test.mjs

public/catalog.json is a small public example. Exact requirements and error boundaries are in public/task-contract.md.
