## Specification: ledger.py, an account ledger

Write `ledger.py` at the workspace root. `python3 ledger.py <input.json>` reads a list of events, applies them in order, prints one JSON object with the final accounts and the outcome of every event to standard output, then exits 0. Use only the Python standard library.

### Input

    {"events": [
      {"id": "e1", "type": "open", "account": "A", "currency": "EUR", "limit": "50.00"},
      {"id": "e2", "type": "deposit", "account": "A", "amount": "20.00"}
    ]}

Every event is an object with a string `id` and a string `type`. The other fields depend on the type. Amounts, limits and rates are JSON strings, never numbers.

### Currencies and amounts

- The currencies are `EUR` and `USD`, with 2 decimal places, and `JPY`, with 0.
- A valid amount in a currency is a string that matches `^[0-9]+(\.[0-9]+)?$`, has at most as many decimal places as the currency allows, and is greater than zero. So `"10.5"` is a valid EUR amount, and `"10.505"`, `"0.00"`, `"-5"`, `"1e3"` and `"5."` are not. `"100.0"` is not a valid JPY amount. An invalid or missing amount gives `INVALID_AMOUNT`.
- A valid rate is a string that matches `^[0-9]+(\.[0-9]+)?$`, with any number of decimal places, and is greater than zero.
- Use exact decimal arithmetic; never binary floating point.

### Accounts

An account has a currency, a balance (starting at 0), an overdraft limit, a set of active holds and a frozen flag (starting false). Its **available** amount is balance + limit − the sum of its active holds.

### Events

| Type | Fields | Effect |
| --- | --- | --- |
| `open` | `account`, `currency`, optional `limit` | Creates the account. `limit` defaults to 0. If given, it must be `"0"` or a valid amount in the account's currency. |
| `deposit` | `account`, `amount` | balance += amount. |
| `withdraw` | `account`, `amount` | Needs amount ≤ available. balance −= amount. |
| `transfer` | `from`, `to`, `amount`, optional `rate` | `amount` is in the `from` currency and needs amount ≤ available of `from`. Between accounts of the same currency, `rate` must be absent. Between different currencies, `rate` is required, and the credited amount is amount × rate rounded to the `to` currency's decimal places, **half to even**. A credited amount that rounds to zero gives `INVALID_AMOUNT`. `from` −= amount, `to` += credited amount. |
| `hold` | `account`, `hold`, `amount` | Reserves funds: needs amount ≤ available, then adds an active hold with the id given in `hold`. The balance does not change. |
| `release` | `hold` | Removes an active hold. The balance does not change. |
| `capture` | `hold`, optional `amount` | Takes money from an active hold's account: `amount` defaults to the whole hold and must not exceed it. balance −= amount, and the hold is no longer active; any remainder is released. A capture is not checked against available, because the hold already reserved the money. |
| `freeze`, `unfreeze` | `account` | Sets or clears the frozen flag. Freezing a frozen account, or unfreezing an unfrozen one, is allowed and changes nothing. |
| `reverse` | `target` | Undoes the money movement of an earlier event (see Reversals). |

A frozen account cannot pay out: it cannot be the `account` of a `withdraw` or `hold`, the `from` of a `transfer`, or the account of a held amount being captured. It can still receive deposits and transfers, and its holds can be released.

### Reversals

- The target must be the id of an earlier event of type `deposit`, `withdraw` or `transfer` whose status was `ok`, and that has not already been reversed. Otherwise the reversal gives `NOT_REVERSIBLE`. A reversal itself cannot be reversed.
- Reversing a `withdraw` adds its amount back.
- Reversing a `deposit` takes its amount back out, and needs amount ≤ available on that account.
- Reversing a `transfer` gives the `from` account back the original amount and takes the credited amount back out of the `to` account. It needs credited amount ≤ available on the `to` account.
- Reversals ignore frozen flags.

### Duplicate event ids

An event whose `id` was used by any earlier event, whatever that event's outcome, is not applied. Its status is `duplicate`. When a reversal targets an id that was used more than once, it refers to the first event with that id.

### Errors and their order

An event either applies completely or not at all. When several errors apply, the first one in this order is reported:

1. An `id` already used: status `duplicate`, no error code.
2. `UNKNOWN_TYPE`: the type is not one of the types above.
3. For `open`: `UNKNOWN_CURRENCY`, then `DUPLICATE_ACCOUNT` (the account already exists), then `INVALID_AMOUNT` (bad `limit`). Nothing else applies to `open`.
4. `UNKNOWN_ACCOUNT`: an `account`, `from` or `to` that does not exist, or is missing.
5. `UNKNOWN_HOLD` for `release` and `capture`: no active hold has that id. `NOT_REVERSIBLE` for `reverse`.
6. `SAME_ACCOUNT`: a transfer whose `from` and `to` are the same account.
7. `ACCOUNT_FROZEN`: the paying account is frozen.
8. `INVALID_AMOUNT`: the `amount`, which is in the paying account's currency. For `capture`, this applies only when `amount` is given.
9. `INVALID_RATE`: a transfer between different currencies without a valid `rate`, or a transfer within one currency that has a `rate`.
10. `INVALID_AMOUNT`: the credited amount of a transfer rounds to zero.
11. `DUPLICATE_HOLD`: a `hold` whose hold id was used by an earlier successful `hold`.
12. `EXCEEDS_HOLD`: a capture amount larger than the hold.
13. `INSUFFICIENT_FUNDS`: not enough available, as each type requires.

### Output

Print one JSON object:

    {"accounts": {"A": {"currency": "EUR", "balance": "20.00", "available": "70.00", "frozen": false}},
     "results": [{"id": "e1", "status": "ok", "error": null}, {"id": "e2", "status": "ok", "error": null}]}

- `accounts` has every opened account. Amounts are strings with exactly the currency's decimal places, such as `"20.00"`, `"-3.50"` or `"1500"`, and a negative value has a leading `-`. Zero is written without a sign.
- `results` has one entry per event, in input order, including duplicates. `status` is `ok`, `rejected` or `duplicate`. `error` is the error code for `rejected`, and `null` otherwise.

### Example

    {"events": [
      {"id": "1", "type": "open", "account": "A", "currency": "EUR"},
      {"id": "2", "type": "open", "account": "B", "currency": "JPY"},
      {"id": "3", "type": "deposit", "account": "A", "amount": "10.00"},
      {"id": "4", "type": "transfer", "from": "A", "to": "B", "amount": "2.50", "rate": "161.3"},
      {"id": "4", "type": "deposit", "account": "A", "amount": "99.00"},
      {"id": "5", "type": "withdraw", "account": "A", "amount": "8.00"}
    ]}
    -> {"accounts": {"A": {"currency": "EUR", "balance": "7.50", "available": "7.50", "frozen": false},
                     "B": {"currency": "JPY", "balance": "403", "available": "403", "frozen": false}},
        "results": [{"id": "1", "status": "ok", "error": null}, {"id": "2", "status": "ok", "error": null},
                    {"id": "3", "status": "ok", "error": null}, {"id": "4", "status": "ok", "error": null},
                    {"id": "4", "status": "duplicate", "error": null},
                    {"id": "5", "status": "rejected", "error": "INSUFFICIENT_FUNDS"}]}

(2.50 × 161.3 = 403.25, which rounds to 403.)

Deliver `ledger.py` and a short README.md. Test your implementation against your own cases. The hidden tests cover every rule above, and each rule area is scored separately.
