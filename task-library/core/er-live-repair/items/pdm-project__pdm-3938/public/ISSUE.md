`pdm import` fails on a requirements.txt that starts with a UTF-8 BOM

### Describe the bug

`pdm import` can't read a requirements file saved with a UTF-8 BOM, which Notepad and some other Windows editors add. The BOM stays on the first line, so that line fails to parse and the import aborts, even if the line is just a comment. pip installs from the same file without problems.

### To reproduce

```console
$ printf '\xef\xbb\xbfrequests==2.31.0\nsix\n' > requirements.txt
$ pdm import requirements.txt
[RequirementError]: ﻿requests==2.31.0: Expected package name at the start of dependency specifier
    ﻿requests==2.31.0
    ^
```

The same happens when the first line is a comment (`# pinned`) or an option like `--index-url ...`.

### Expected Behavior

The BOM is ignored and both `requests==2.31.0` and `six` are imported, as pip does.

### Environment Information

PDM main (09c6ada9), Python 3.12, Linux.

### Are you willing to submit a PR to fix this bug?

- [x] Yes, I would like to submit a PR.
