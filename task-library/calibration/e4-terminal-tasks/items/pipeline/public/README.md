# Sales pipeline

`make` turns the regional sales exports in `raw/` into `report.csv`, the monthly revenue per region, and `make test` runs the tests. `make clean` removes everything the build creates.

1. `scripts/normalize.sh` merges every `raw/sales-*.csv` into `build/sales.csv` (`date,amount,store`).
2. `scripts/join.py` adds each sale's region from `raw/stores.csv` (`store_id,name,region`) and writes `build/joined.csv`.
3. `scripts/report.py` writes `report.csv` (`month,region,revenue`), ordered by month and then region, with each revenue rounded half up to cents.

## The exports

- Every export has a header line, `date,amount,store`, then one sale per line. Dates are `YYYY-MM-DD` and amounts are decimals.
- The regional offices export from different systems. Some files have Windows line endings, and some lack a line break after their last line. The EU office's files (`raw/sales-eu*.csv`) use `;` as the separator and `,` as the decimal mark, as in `2026-10-02;19,90;31`.
- Store ids are numbers: `7`, `07` and `007` are the same store, in the exports and in `raw/stores.csv`.
- Every sale belongs to a store in `raw/stores.csv`, so every sale counts towards some region.
- After any file in `raw/` changes, `make` must bring `report.csv` up to date.
