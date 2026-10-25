Queued standard handlers use the consumer thread instead of the producer thread

When a standard-library `logging.Handler` is added with `enqueue=True`, its `LogRecord.thread` and `threadName` describe Loguru's queue consumer (`loguru-writer-0`), rather than the thread that called `logger.info()`. With `enqueue=False`, they describe the producer as expected. A `logging.Filter` selecting the producer thread can therefore silently drop queued messages.

Minimal example:

```python
import logging
import sys
from threading import Thread

from loguru import logger

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(threadName)s %(message)s"))
logger.add(handler, format="{message}", enqueue=True)

thread = Thread(target=logger.info, args=("hello",), name="producer")
thread.start()
thread.join()
logger.complete()
```

Expected: `producer hello`. Actual: `loguru-writer-0 hello`.

Reproduced with Loguru 0.7.3, Python 3.11.16, macOS 27.0 (arm64). The queued record already retains the originating thread in `message.record["thread"]`; copying its ID and name to the standard `LogRecord` before handler filtering appears to preserve the expected behavior. This should respect `logging.logThreads=False`.

AI assistance was used to prepare this report and the reproducer.
