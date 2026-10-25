textual.log from worker thread is not working
Since textual 3.2.0 calling `textual.log` from a worker thread not longer works. If I revert to textual 3.1.1 logging from worker threads work correctly.

Here is an example:

```
from datetime import datetime

from textual import log, work
from textual.app import App, ComposeResult
from textual.widgets import Digits


class ClockApp(App):
    CSS = """
    Screen { align: center middle; }
    Digits { width: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Digits("")

    def on_ready(self) -> None:
        self.update_clock()
        self.set_interval(1, self.update_clock)

    def update_clock(self) -> None:
        clock = datetime.now().time()
        self.query_one(Digits).update(f"{clock:%T}")
        self.worker()

    @work(thread=True)
    async def worker(self) -> None:
        log("Log message")


if __name__ == "__main__":
    app = ClockApp()
    app.run()
```

The `Log message` is correctly logged in textual 3.1.1 but is not logged in textual 3.2.0
