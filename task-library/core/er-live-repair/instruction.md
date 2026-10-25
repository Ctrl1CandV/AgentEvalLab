# Task: Repository Repair (ER)

The workspace holds a Python project in `repo/`, at the commit where the issue below was open. The issue is also in `public/ISSUE.md`. Change the project so that the issue is resolved.

## How your change is checked

- Your change is the difference between `repo/` and its single commit when you stop: files you edit, add or delete count, as do commits you make; files the project's `.gitignore` ignores do not.
- The project's own tests that come with the real fix are then run on your change: tests for the issue must pass, and the project's tests that passed before must still pass. These tests are not in the workspace.
- Test files those tests touch are reset to their original content before they run, so changing tests does not help; fix the code.
- When the task lists names the tests use (a new function, class, argument or attribute), the tests call them exactly as listed.

## Running the project

- Python 3.13 and the project's test dependencies are installed and read-only; there is no network, so nothing can be installed.
- Commands run from the workspace root, with the project on the import path. Run the project's tests with `python -m pytest repo/tests/...` (or the project's own test directory), and Python with `python -c ...` or a script you write.
- Each command may run for a limited time and print a limited amount of output; the limits are in the tool's description.

End with a short summary of what you changed.
