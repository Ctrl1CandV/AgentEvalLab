# Work Order CLI Long-Cycle Maintenance Task

You will handle five fixed maintenance requests in sequence. At the end of each stage, a public checker evaluates that stage's behavior. If it reports public failures, you receive one feedback message and one repair opportunity. A stage failure does not automatically stop later requests. All stages share one working directory and conversation history.

Treat only the currently provided stage brief as the active request. Preserve baseline data, existing CLI commands, and behavior established earlier. Do not modify checkers, acceptance scripts, or fixed data to satisfy checks; independent scoring happens after your session ends.

The project runs on Node.js 22 with TypeScript type stripping. No dependency installation or network access is needed. The command entry point is:

    node --experimental-strip-types src/cli.ts ...

Before starting, read README.md and public/project-brief.md. Stage materials will be provided separately.
