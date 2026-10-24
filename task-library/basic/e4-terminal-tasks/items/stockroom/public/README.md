# stockroom

A small inventory and order service for a shop. Run it from this directory: `python3 -m stockroom.cli <command>`.

| Command | What it does |
| --- | --- |
| `init products.csv` | Creates the database if needed and loads (or replaces) products from a CSV with columns `sku,name,price,stock`. |
| `import orders.csv` | Imports orders from a CSV with columns `ref,placed,sku,qty`, one row per order line, and takes the ordered quantities out of stock. Prints `imported N orders, skipped M lines`. |
| `restock SKU QTY` | Adds `QTY` to a product's stock. |
| `low-stock` | Prints `SKU STOCK` for every product whose stock is below the threshold, ordered by SKU. |
| `report YYYY-MM-DD` | Prints the day's sales as JSON: `{"date", "orders", "revenue", "units"}`. |
| `export FILE` | Writes every order with its lines to `FILE` as JSON. |

## Configuration

`stockroom.toml` sets `database`, `timezone` (an IANA name), `strict`, `low_stock_threshold` and `cache_dir`. Environment variables override it: `STOCKROOM_DATABASE`, `STOCKROOM_TZ`, `STOCKROOM_STRICT` and `STOCKROOM_THRESHOLD`. `STOCKROOM_STRICT` accepts `true`/`false`, `1`/`0`, `yes`/`no` and `on`/`off`, in any letter case.

## Rules

- **Orders.** An order's `ref` identifies it; refs are case-sensitive, and spaces around a ref are not part of it. All rows with the same ref form one order, whose time is `placed` (ISO 8601 with a UTC offset) of its first row. An order whose ref is already in the database is not imported again and does not change stock.
- **Unknown SKUs.** In strict mode, an import that contains an unknown SKU fails with exit status 2 and imports nothing. Otherwise the rows with unknown SKUs are skipped (and counted as skipped lines), and an order left without lines is not imported.
- **Prices.** A line keeps the product's price at import time. Prices are decimal strings with up to three decimal places.
- **Reports.** A report covers one calendar day in the configured timezone. `orders` counts that day's orders, `units` maps each SKU sold that day to its quantity, ordered by SKU, and `revenue` is the exact sum of unit price × quantity over the day's lines, rounded half up to cents and written with two decimals.
- **Low stock.** The list may be cached for speed, but every change of stock (an import or a restock) must show in the next `low-stock`.
- **Export.** Orders appear in the order they were imported, each with its lines in the order they were imported: `[{"ref", "placed_utc", "lines": [{"sku", "qty", "unit_price"}]}]`. A shop's database holds tens of thousands of orders, and an export must take seconds, not minutes.

## Tests

`python3 -m unittest discover -s tests`
