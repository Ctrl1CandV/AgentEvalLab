## Issue (pallets/flask)

IPv6 addresses parsed incorrectly because of `.partition(":")`?

Hi, I checked the code and saw that two places use `.partition(":")` on addresses, and IPv6 addresses contain ":".

This breaks 1. `session_transaction` value setting, and 2. `Flask.run()` if `SERVER_NAME` is set. I've already prepared two tests that fail, you can use them to reproduce:

1. In `test_testing.py`
```
def test_session_transaction_ipv6(app):
    base_url = "http://[::1]:8000/"
    client = app.test_client()

    @app.get("/")
    def index():
        return str(flask.session.get("value"))

    with client.session_transaction(base_url=base_url) as sess:
        sess["value"] = 42

    assert client.get("/", base_url=base_url).text == "42"
```

2. Add one case to `test_run_from_config`
```
(None, None, "[::1]:8080", "::1", 8080),
```

Is this known and intended? I could send the patches for these two places.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
