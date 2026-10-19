## Task: migrate the shop database to schema 2

Everything for this task is in the directory `public/` of the workspace. All paths below are relative to it, and the deliverables go there too; run your commands from inside it.

The workspace holds `shop.db`, a SQLite database in schema 1. Write `migrate.py`, which migrates a schema 1 database to schema 2 in place: `python3 migrate.py <database>`. Then run it on `shop.db`, so that the delivered `shop.db` is in schema 2. Use only the Python standard library (the `sqlite3` module is available; there is no `sqlite3` command-line tool).

`migrate.py` is also run on other schema 1 databases that you have not seen, so the migration must follow the rules below, not the particular data in `shop.db`.

### Schema 1

    CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT, joined TEXT NOT NULL);
    CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total TEXT NOT NULL, status INTEGER NOT NULL, placed TEXT NOT NULL);

### Schema 2

    CREATE TABLE customers (id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL, email TEXT, joined TEXT NOT NULL);
    CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), total_cents INTEGER NOT NULL,
                         currency TEXT NOT NULL, status TEXT NOT NULL, placed TEXT NOT NULL);
    CREATE INDEX idx_orders_customer ON orders(customer_id);
    CREATE TABLE migration_log (order_id INTEGER NOT NULL, reason TEXT NOT NULL);
    CREATE TABLE schema_version (version INTEGER NOT NULL);

After the migration, the database holds exactly these five tables and this one index, with these column names, types and NOT NULL constraints. `schema_version` holds one row, `2`. Every id is kept.

### Customers

- **Names.** Trim `name` and collapse each run of whitespace inside it to one space.
  - If the result contains a comma, it is `Last, First`: `last_name` is the trimmed text before the first comma, and `first_name` is the trimmed text after it.
  - Otherwise `last_name` is the last word, and `first_name` is everything before it. A name of one word has that word as `first_name`, and `""` as `last_name`.
  - Letter case is kept as written.
- **Emails.** Trim the email and lower-case it. An email that is empty after trimming becomes NULL; NULL stays NULL.
- **Dates.** `joined` is written `D/M/YYYY` (day first; day and month may have one or two digits) and becomes `YYYY-MM-DD`.

### Orders

- **Totals.** `total` is a currency symbol followed directly by an amount: `$` is `USD`, `€` is `EUR` and `£` is `GBP`. The amount has digits, optionally grouped in threes by commas (`1,234`), and optionally a point followed by one or two digits. It becomes `total_cents`, an integer number of cents, and `currency`. So `$1,234.5` is 123450 cents in USD, and `£0.07` is 7 cents in GBP.
- **Status.** 0 is `pending`, 1 is `paid`, 2 is `shipped` and 3 is `cancelled`.
- **Placed.** `placed` is written `D/M/YYYY H:MM` (24-hour clock; the hour may have one or two digits) and becomes `YYYY-MM-DDTHH:MM`, with a two-digit hour.
- **Orphans.** An order whose `customer_id` is NULL or names no customer is not migrated. Instead, a row `(order id, 'orphan')` is added to `migration_log`.

### Failure and repetition

- A total, status or date that does not follow these rules makes the whole migration fail: `migrate.py` exits with a non-zero status, and the database is left exactly as it was.
- Running `migrate.py` on a database that is already in schema 2 changes nothing and exits 0.

Deliver `migrate.py` and the migrated `shop.db`.
