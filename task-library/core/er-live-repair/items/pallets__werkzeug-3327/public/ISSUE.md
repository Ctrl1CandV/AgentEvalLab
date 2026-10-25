`Response.location` and `content_location` should use `iri_to_uri`

They currently store strings, then call `iri_to_uri` in `get_wsgi_headers`. And that's only done for WSGI, so sans-IO/ASGI doesn't get it. Instead, they should always be stored as URIs, and accessed as IRIs.

No other headers are "fixed" in `get_wsgi_headers`. `Response.headers` is considered "raw" values, where it's the responsibility of the code setting it to set a valid value. That's what the properties provide: set a Python value, get the right encoded header value.
