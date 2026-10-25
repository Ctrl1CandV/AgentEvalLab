Cancelling TCP receive leaves transport reads enabled on asyncio

### Environment
AnyIO 4.15.1 and master (`623a480`), CPython 3.12.14, Windows.

### Description
Cancelling a blocked `SocketStream.receive()` leaves the asyncio transport reading. If the connection remains open without further receives, incoming data continues accumulating in the unbounded Python receive queue.

In a TCP experiment, all 4 MiB sent after cancellation was buffered without an active receiver. This also affects TCP streams wrapped in TLS.

### Reproducer
```python
import anyio


async def main():
    async with await anyio.create_tcp_listener(
        local_host="127.0.0.1"
    ) as listener:
        port = listener.extra(anyio.abc.SocketAttribute.local_port)
        async with await anyio.connect_tcp("127.0.0.1", port) as stream:
            async with await listener.listeners[0].accept():
                with anyio.move_on_after(0.1):
                    await stream.receive()

                # Private attribute used only to inspect transport state.
                print(stream._transport.is_reading())  # True; expected False


anyio.run(main, backend="asyncio")
```

### Expected behavior
Transport reads should be paused after cancellation, restoring backpressure while allowing subsequent receives.

`SocketStream.receive()` currently skips `pause_reading()` when its wait is cancelled. I have a local `try/finally` fix and regression tests ready for a follow-up PR.
