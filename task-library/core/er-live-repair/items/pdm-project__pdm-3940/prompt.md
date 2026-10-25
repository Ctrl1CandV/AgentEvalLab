## Issue (pdm-project/pdm)

`pdm import` fails on a Pipfile version without an operator, e.g. `requests = "2.31.0"`

### Describe the bug

pipenv accepts a version with no operator in a Pipfile and treats it as an exact pin (`requests = "2.31.0"` means `requests==2.31.0`), in both the string form and `{version = "2.31.0"}`. `pdm import` passes the version through unchanged, so the import aborts with an invalid specifier error.

### To reproduce

```console
$ printf '[packages]\nrequests = "2.31.0"\n' > Pipfile
$ pdm import Pipfile
[RequirementError]: Invalid specifier for requests: 2.31.0: Invalid specifier: '2.31.0'
```

`requests = {version = "2.31.0"}` fails the same way.

### Expected Behavior

The dependency is imported as `requests==2.31.0`, the way pipenv reads it and the way the Poetry importer already handles versions without an operator.

### Environment Information

PDM main (09c6ada9), Python 3.12, Linux.

### Are you willing to submit a PR to fix this bug?

- [x] Yes, I would like to submit a PR.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
