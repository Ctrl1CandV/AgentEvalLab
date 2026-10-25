## Issue (slackapi/python-slack-sdk)

SocketModeClient.connect() retries forever against a permanently closed aiohttp ClientSession

## Title
SocketModeClient.connect() retries forever against a permanently closed aiohttp ClientSession

## Environment
- `slack_sdk` 3.43.0
- File: `slack_sdk/socket_mode/aiohttp/__init__.py`
- Relevant locations: session creation ~L130, `is_connected()` ~L321-334, `connect()` ~L347-409, `close()` ~L446-457

## Description

`SocketModeClient` (aiohttp implementation) keeps a single `aiohttp.ClientSession` for the client's entire lifetime — a reasonable design, per the comment at its creation: *"it is suggested you use a single session for the lifetime of your application, to benefit from connection pooling."* The bug isn't that design choice; it's that the unbounded retry loop doesn't handle that session ever entering a closed state.

`connect()` wraps reconnection attempts in `while True:` (~L352). On exception it logs `"Failed to connect (error: {e}); Retrying..."` (~L408) and loops again, reusing `self.aiohttp_client_session`. If that session itself has been closed (not just the individual WebSocket tracked as `self.current_session`), every subsequent retry fails identically forever with `RuntimeError: Session is closed` — nothing inside this loop ever recreates the session; that only happens when a new `SocketModeClient` instance is constructed from scratch.

Separately, `is_connected()` checks `self.current_session`/ping-pong state but does not check `self.aiohttp_client_session.closed`, so downstream consumers building their own health checks or watchdogs on top of this client have no way to detect this specific failure mode without reaching into a private-ish attribute themselves.

## Impact observed

In production, a consumer application's own reconnect watchdog (checking `is_connected()`) never detected this state, because the WebSocket layer could still look "connected enough" (some event types were still being delivered) while the HTTP session underneath was permanently dead. The client was stuck retrying every ~10 seconds for over 24 hours with no self-healing, until the whole process was restarted externally.

## Likely forced repro (not yet reduced to a minimal script)

1. Construct a `SocketModeClient` with a valid app token; `await client.connect()`.
2. `await client.aiohttp_client_session.close()` (or otherwise force it closed) while the connection is established.
3. Trigger a reconnect attempt (e.g. disconnect the network, or otherwise cause `connect()`'s loop to retry).
4. Observe it fails forever: `Failed to connect (error: Session is closed); Retrying...`
5. Observe `is_connected()` may not reflect the problem if `self.current_session` (the WebSocket) hasn't itself been marked closed/None.

## Suggested fixes (ranked)

1. **Preferred**: in `connect()`'s retry loop, check `self.aiohttp_client_session.closed` at the top of each iteration; if closed, recreate it (e.g. re-instantiate `aiohttp.ClientSession`) before retrying `ws_connect`.
2. **Minimum**: if recreating isn't desired, `raise` or `break` out of the loop when the session is closed, so the caller can rebuild the whole client instead of retrying forever against a dead one.
3. **Consumer-facing improvement**: reflect `aiohttp_client_session.closed` in `is_connected()` (or an equivalent health-check property), so consumers can detect this without reaching into a non-public attribute.

## Notes

We don't have a minimal standalone repro yet — this was diagnosed from production logs plus reading this source after a ~39 hour incident where a single client instance got stuck in this state. Happy to help characterize a repro further if useful. We've worked around this downstream by having our own consumer explicitly check `aiohttp_client_session.closed` before deciding whether to rebuild — happy to link that once it's merged, in case the pattern is useful context here too.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
