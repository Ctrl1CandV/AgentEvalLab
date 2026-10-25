## Issue (pdm-project/pdm)

`pdm import` resolves relative Pipfile paths against the current directory

### Describe the bug

Local `path` entries in a Pipfile are relative to the Pipfile, which is pipenv's project directory. `pdm import` resolves them against the current directory instead, so importing a Pipfile that is not in the current directory points the dependency at the wrong place.

### To reproduce

```console
$ mkdir -p legacy/my-lib
$ printf '[project]\nname = "my-lib"\nversion = "1.0"\n' > legacy/my-lib/pyproject.toml
$ printf '[packages]\nmy-lib = {path = "./my-lib"}\n' > legacy/Pipfile
$ printf '[project]\nname="app"\nversion="0.1"\nrequires-python=">=3.10"\ndependencies=[]\n' > pyproject.toml
$ pdm import legacy/Pipfile
```

Result:

```toml
dependencies = [
    "my-lib @ file:///${PROJECT_ROOT}/my-lib",
]
```

`${PROJECT_ROOT}/my-lib` does not exist.

### Expected Behavior

`"my-lib @ file:///${PROJECT_ROOT}/legacy/my-lib"`, the same as the Poetry and flit importers, which already resolve relative paths from the file's own directory.

### Environment Information

PDM main (b8b21a9c), Python 3.12, Linux.

### Are you willing to submit a PR to fix this bug?

- [x] Yes, I would like to submit a PR.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
