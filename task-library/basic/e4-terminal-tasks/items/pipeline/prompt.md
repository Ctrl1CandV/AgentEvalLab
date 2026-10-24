## Task: fix the sales pipeline

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

`make` turns the regional sales exports in `raw/` into `report.csv`; `README.md` describes the pipeline and the exports. Accounting reports two problems:

1. "The monthly revenue in `report.csv` is lower than the sum of the exports, for several regions."
2. "We moved a store to another region in `raw/stores.csv` and ran `make`, but the report still showed the old regions."

Find the causes and fix them, so that `make` produces the report `README.md` describes for any exports of the documented kinds, not only the files in `raw/` now. The fixes are checked by running `make` on exports you have not seen. Keep the steps, file names and formats; `make test` must keep passing.
