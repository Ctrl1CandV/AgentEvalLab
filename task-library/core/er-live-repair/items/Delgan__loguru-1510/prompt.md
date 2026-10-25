## Issue (Delgan/loguru)

Exceptions raised by an async generator while handling `athrow()` bypass `@logger.catch`

## Summary

Async generator functions decorated with `@logger.catch` are wrapped by `AsyncGenCatchWrapper`.

The wrapper applies the configured catcher when the generator is resumed through `asend()`, but `athrow()` is forwarded directly to the underlying async generator:

```python
async def asend(self, value):
    with catcher:
        try:
            return await self._gen.asend(value)
        except StopAsyncIteration:
            pass
    raise StopAsyncIteration

async def athrow(self, *args, **kwargs):
    return await self._gen.athrow(*args, **kwargs)
```

This creates a behavioral inconsistency when an exception is injected through `athrow()` and the generator handles that exception but then raises a different exception of its own.

In that case, the new exception raised from inside the decorated async generator bypasses `@logger.catch`: it is not logged and `onerror` is not called.

The same exception raised from the generator body when execution proceeds through `asend()` is handled by `@logger.catch` as expected.

## Background

Async generator support for `@logger.catch` was introduced in #1302 / #1303.

There is already a test covering `athrow()` which verifies that an exception injected into the generator and left unhandled continues to propagate to the caller.

That behavior is reasonable and this issue does not require changing it.

The uncovered case is different:

1. The caller injects exception `A` with `athrow(A)`.
2. The async generator catches `A`.
3. While handling `A`, the generator raises a new exception `B`.
4. Exception `B`, although raised by the decorated generator itself, bypasses `@logger.catch`.

## Reproduction

```python
import asyncio

from loguru import logger


logger.remove()

logged = []

logger.add(
    lambda message: logged.append(message.record["message"]),
    format="{message}",
    colorize=False,
)


async def main():
    @logger.catch(reraise=True)
    async def via_asend():
        yield 1
        raise RuntimeError("asend-boom")

    gen = via_asend()
    await gen.asend(None)

    try:
        await gen.asend(None)
    except RuntimeError:
        pass

    print("asend logged:", logged)
    logged.clear()

    @logger.catch(reraise=True)
    async def via_athrow():
        try:
            yield 1
        except TimeoutError:
            raise RuntimeError("athrow-boom")

    gen = via_athrow()
    await gen.asend(None)

    try:
        await gen.athrow(TimeoutError)
    except RuntimeError as error:
        print("athrow raised:", error)

    print("athrow logged:", logged)


asyncio.run(main())
```

## Actual behavior

The `RuntimeError` raised while execution proceeds through `asend()` is logged:

```text
asend logged: ["An error has been caught in function 'main', process 'MainProcess' (...), thread 'MainThread' (...):"]
```

The `RuntimeError` raised by the generator while handling the exception injected through `athrow()` is not logged:

```text
athrow raised: athrow-boom
athrow logged: []
```

With `reraise=True`, the exception correctly continues to reach the caller, but it has bypassed the logging behavior provided by `@logger.catch`.

The same bypass also means that `onerror` is not invoked for this path.

## Expected behavior

An exception explicitly injected by the caller through `athrow()` and left unhandled by the generator can continue to propagate as it does currently.

However, if the generator handles the injected exception and then raises a new exception while executing its own code, that new generator-raised exception should be processed by `@logger.catch`, consistently with exceptions raised when the generator is resumed through `asend()`.

In other words, these two cases should remain distinguishable:

```python
async def generator():
    yield

await generator().athrow(ValueError)
```

Here, the injected `ValueError` is simply unhandled by the generator and may continue to propagate.

By contrast:

```python
async def generator():
    try:
        yield
    except ValueError:
        raise RuntimeError("failure while handling injection")
```

the `RuntimeError` originates from execution inside the decorated generator and would be expected to go through `@logger.catch`.

## Why this matters

`athrow()` is not limited to callers invoking the method manually.

It is part of Python's async-generator exception-injection protocol and is used by abstractions such as `contextlib.asynccontextmanager` when propagating exceptions from an `async with` body back into the underlying async generator.

This means the issue can occur in normal control-flow and cleanup code.

For example, conceptually:

```python
from contextlib import asynccontextmanager


@asynccontextmanager
@logger.catch(reraise=True)
async def resource():
    try:
        yield
    except SomeError:
        # Cleanup or error handling fails.
        raise RuntimeError("cleanup failed")
```

If the context manager implementation resumes the generator by injecting the original exception, a subsequent exception raised by the generator can follow the `athrow()` path and bypass the catcher.

## Existing test coverage

The existing async-generator `athrow()` test verifies the propagation of an unhandled injected exception.

It does not appear to cover the case where the generator catches the injected exception and raises a different exception while handling it.

A regression test for that distinction would make the intended semantics explicit.

## Possible direction

Simply wrapping all of `athrow()` in the same catcher used by `asend()` may alter the existing semantics for an injected exception that the generator does not handle, because the catcher could consume that injected exception when `reraise=False`.

Therefore, the main issue is not necessarily that `athrow()` should be wrapped identically to `asend()`.

Rather, the desired behavior would be to preserve propagation of an unhandled injected exception while ensuring that a new exception raised by the generator during `athrow()`-driven execution is still processed by `@logger.catch`.

The exact implementation is left open, since distinguishing these cases without changing the established `athrow()` behavior may require special handling.

## Environment

Reproduced with:

* Delgan/loguru commit `54c89d609fc98a63b5bf7f801119c5bc526e2016`
* CPython 3.11.2
* Linux x86_64

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
