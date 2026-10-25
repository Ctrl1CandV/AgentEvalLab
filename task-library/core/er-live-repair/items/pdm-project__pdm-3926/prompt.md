## Issue (pdm-project/pdm)

`pdm import` writes an empty `dev = []` group when the Pipfile has no dev packages

### Describe the bug

pipenv creates an empty `[dev-packages]` table by default. Importing such a Pipfile leaves an empty `dev` group in `[dependency-groups]`.

### To reproduce

```console
$ printf '[packages]\nrequests = "*"\n\n[dev-packages]\n' > Pipfile
$ printf '[project]\nname="app"\nversion="0.1"\nrequires-python=">=3.10"\ndependencies=[]\n' > pyproject.toml
$ pdm import Pipfile
```

Result:

```toml
[dependency-groups]
dev = []
```

### Expected Behavior

No `[dependency-groups]` table, since there is nothing to put in it.

### Environment Information

PDM main (d8e75f01), Python 3.12, macOS.

### Are you willing to submit a PR to fix this bug?

- [x] Yes, I would like to submit a PR.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
