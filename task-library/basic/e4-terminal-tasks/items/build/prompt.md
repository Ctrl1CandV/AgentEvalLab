## Task: repair the wordfreq build

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

The workspace holds `wordfreq`, a small C program; `README.md` describes what it does. Its build is broken: `make` fails, and the program has bugs that its tests reveal.

Make it work:

- `make` builds `bin/wordfreq` with the compiler flags in the `Makefile` (`-std=c11 -Wall -Wextra -Werror -O2`). Keep those flags; fix the code instead.
- `make test` runs the cases in `tests/cases` and passes. Do not change the test cases.
- `make clean` removes everything the build creates.
- The program behaves as `README.md` describes, also on inputs that are not among the test cases.

Use the tools in the sandbox (`make`, `cc`, the shell). Deliver the repaired project in place.
