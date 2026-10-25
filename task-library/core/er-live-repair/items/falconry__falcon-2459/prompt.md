## Issue (falconry/falcon)

Response cookies have an inconsistent same_site parameter
`Response.unset_cookie` has a `samesite` argument, and `Response.set_cookie` has a `same_site` argument, which does not match at all.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.

## Names the tests use

The project's tests for this issue use these names; give them exactly as listed:

- `Response.unset_cookie(..., same_site=...)` takes the keyword `same_site`, as `Response.set_cookie` does; the old keyword `samesite` still works but emits `falcon.util.deprecation.DeprecatedWarning` with a message containing `The "samesite" parameter is deprecated`.
