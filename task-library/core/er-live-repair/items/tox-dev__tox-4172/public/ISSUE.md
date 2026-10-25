TOML command references drop ignore/invert exit-code prefixes

## Issue

Native TOML command references lose the `-` (ignore nonzero exit) and `!` (invert exit result) prefixes. Those prefixes are stored as `Command` flags, but a referenced command is reconstructed from its `.args` alone. As a result, a command that should be ignored can fail a referenced environment, and an inverted command can produce a false green result.

This is the TOML reference path, distinct from the INI prefix issue #3856 (fixed in #3748). The command-list conversion from #4112 also retains this behavior.

## Environment

- macOS arm64; Python 3.11.16.
- Current `main` at `f2749b7a5a74ac26a70c617c83f02efea8aaa640` (local development build 4.66.1.dev1).

## Minimal example

```toml
[env_run_base]
package = "skip"

[env.original]
commands = [["-", "python", "-c", "raise SystemExit(1)"]]

[env.referenced]
commands = { replace = "ref", env = "original", key = "commands" }
```

Run `tox run --no-provision -e original,referenced`.

Expected: both environments succeed because the referenced command retains its ignore-exit prefix. Actual on current main: `original: OK`, `referenced: FAIL code 1`, overall exit 1. The analogous `!` reference also loses inversion.

I have a narrow local patch and 18 regression cases: 12 new cases fail on the unchanged base, all 18 pass with the patch, and 281 adjacent tests pass. Would a PR for this TOML-specific correction be welcome? AI assistance was used in reproduction, patching, and independent review.
