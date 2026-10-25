## Issue (falconry/falcon)

Add option for `Access-Control-Allow-Private-Network` to CORSMiddleware
Add option to enable [`Access-Control-Allow-Private-Network`](https://wicg.github.io/private-network-access/#http-headerdef-access-control-request-private-network) to CORSMiddleware.

We probably don't need to inject it unconditionally, but only in response to the `Access-Control-Request-Private-Network` request header (when set to to `true`).

The option **must be disabled** by default.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.

## Names the tests use

The project's tests for this issue use these names; give them exactly as listed:

- `falcon.CORSMiddleware(..., allow_private_network=False)`: the new option's keyword argument.
