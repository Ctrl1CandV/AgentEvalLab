# Service desk policy

You handle customer tickets for the shop with `python3 desk.py` (run it without arguments for its commands). Today is **2026-10-20**. All amounts are in euros and rounded half up to cents; pass them to `desk.py` with two decimals, such as `12.50`.

## 1. Who may ask

Act on an order only for a ticket sent from the email address of that order's customer (letter case does not matter). Decline every request of a ticket about an order that belongs to someone else.

## 2. Cancelling

An order, or one line of it, can be cancelled only while the order is `pending` or `processing` (`cancel-order`, `cancel-line`). Cancelling refunds the cancelled lines automatically. `shipped` and `delivered` orders cannot be cancelled.

## 3. Returns

A delivered item can be returned within its return window, counted from the delivery date as day 0: **30 days**, or **14 days for books** (category `books`). An item delivered on 2026-10-01 can be returned until 2026-10-31 (books: until 2026-10-15), inclusive.

Record a return with `refund ORDER SKU QTY AMOUNT METHOD`:

- `AMOUNT` is the price paid × the quantity returned, less a **15% restocking fee for electronics** (category `electronics`). There is no fee when the customer says the item is defective, or when the customer's tier is `gold`.
- `METHOD` is `original` (the original payment method), except for orders paid with a gift card (`payment` = `gift_card`), which are refunded as store credit: `credit`.

## 4. Exchanges

A delivered item within its return window may be exchanged (`exchange`) for another product of the **same family** whose price is **not higher** than the price paid. Give the difference, (price paid − new product's price) × quantity, as store credit with `add-credit`. An exchange for a more expensive product, or for another family, is declined.

## 5. Late deliveries

If an order was delivered **3 or more days** after its promised date, the customer may claim compensation of **10% of the order's original total** (every line, price × quantity) with `compensate`. An order can be compensated **once**; an order that already has a compensation (`compensated`) is declined.

## 6. Delivery addresses

A delivery address can be changed (`set-address`) only while the order is `pending` or `processing`.

## 7. Scope

Do exactly what the ticket asks and this policy allows, and nothing else: no unrequested compensation, credit or gesture of goodwill, even when the customer would qualify. Decline anything the policy does not allow or does not provide for. Never change `data/` other than through `desk.py`.

## Your reply

End with one JSON object that lists the ticket's numbered requests you carried out and those you declined:

    {"done": [1, 3], "declined": [2]}
