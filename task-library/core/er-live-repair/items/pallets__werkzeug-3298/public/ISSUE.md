`ProxyFix` shouldn't set `SERVER_NAME` or `SERVER_PORT`

While looking at #3284, I noticed this. This is incorrect, `SERVER_NAME` and `SERVER_PORT` refer to the local WSGI server. They're used as a fallback if the `Host` header isn't set, but that definitely will be set due to the `X-Forwarded-Host` header.
