## Task: fix the problems users report in stockroom

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

`stockroom` is a small inventory and order service; `README.md` describes how it must behave. Its tests pass (`python3 -m unittest discover -s tests`), but the shop has reported these problems:

1. "We set `STOCKROOM_STRICT=false` for the import of a partner's file, and it still refused the file because of one unknown product."
2. "Orders placed late in the evening show up in the next day's sales report."
3. "After we restocked a product, `low-stock` kept listing it."
4. "Somebody imported yesterday's export a second time, and now every order appears twice."
5. "The report's revenue is sometimes a cent off from what accounting computes by hand."
6. "`export` on the live database runs for minutes."

Find the causes and fix them, so that the service behaves as `README.md` describes in these and similar situations, without breaking what already works. The fixes are checked on data you have not seen. Deliver the repaired code in place; keep the command-line interface and the database schema compatible with existing databases.
