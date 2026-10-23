#!/usr/bin/env python3
"""ledger.py: the finance desk's tool for the books in data/books.json.

    python3 ledger.py <command> [arguments]

Look-ups print JSON. Every command that changes the books is appended to data/audit.log. The tool checks that entries
are well formed; it does not check the finance manual (MANUAL.md). That is the job of whoever uses it.

Look-ups:
  accounts                          the chart of accounts
  periods                           which ledgers are open in each period
  rates CURRENCY                    EUR per unit of the currency, per business day
  partners [customers|vendors]      customers and vendors
  show-partner ID                   one customer or vendor
  open-items PARTNER                the partner's open receivables or payables: open amount and EUR balance
  show-document ID                  an invoice, credit note, purchase order, contract or inbox invoice, with its lines
  bank                              the bank lines
  cash                              today's payment run: the cash available per currency, its limits and its rates
  inbox                             the vendor invoices received, with their status
  receipts PO                       the goods received on a purchase order, with the EUR accrued per unit
  contracts                         subscription contracts
  approvers                         approvers and their limits
  entries [--document ID] [--account A] [--partner P]
                                    posted entries, optionally only those with a matching line

Changes:
  begin REQUEST                     start work on a request, such as R3 (recorded in the audit log)
  post FILE                         post the entry in a JSON file (or - for standard input):
                                      {"date": "2026-09-30", "memo": "...", "lines": [
                                        {"account": "1200", "credit": "120.00", "partner": "C-104",
                                         "document": "INV-5021", "currency": "USD", "amount": "131.40"},
                                        {"account": "1100", "debit": "120.00"}]}
                                    Each line has exactly one of debit and credit (a positive EUR amount with two
                                    decimals). Lines on 1200 and 2000 also name a partner, a document, its currency
                                    and the document amount the line moves (positive; a debit opens a receivable and
                                    clears a payable, a credit the reverse); no line may clear more than is open.
                                    Lines on 1210, 2010, 2150, 2160, 2200 and 2400 name a partner (except 2160) and a
                                    document. Debits and credits must be equal.
  set-status DOC STATUS             record an inbox invoice's outcome: posted, rejected, blocked or held
  pay DOC                           pay an open payable in today's payment run. The tool computes the amounts: the
                                    early-payment discount when today is within the vendor's discount window, the
                                    exchange difference at today's rate, and the transfer fee. It refuses a document
                                    that is disputed or settled, and a payment beyond the cash of its currency or
                                    beyond the run's limit on the number of payments.
"""
import json
import os
import re
import sys
from decimal import Decimal

BOOKS = os.path.join("data", "books.json")
AUDIT = os.path.join("data", "audit.log")
MONEY = re.compile(r"^[0-9]+\.[0-9]{2}$")
DATE = re.compile(r"^2026-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
OPEN_ITEMS = {"1200": "debit", "2000": "credit"}  # the side that opens a document on each account
PAYMENT_MEMO = "Payment run"
NAMED = {"1210", "2010", "2150", "2160", "2200", "2400"}


class Refused(Exception):
    pass


def money(value, name):
    if not isinstance(value, str) or not MONEY.match(value) or Decimal(value) <= 0:
        raise Refused(f"{name} must be a positive decimal with two places, such as 12.50: {value!r}")
    return Decimal(value)


def rate_on(books, currency, date):
    """EUR per unit of the currency on a date; a weekend takes the Friday before."""
    if currency == "EUR":
        return Decimal(1)
    series = books["rates"][currency]
    day = date
    for _ in range(10):
        if day in series:
            return Decimal(series[day])
        parts = [int(part) for part in day.split("-")]
        import datetime
        day = (datetime.date(*parts) - datetime.timedelta(days=1)).isoformat()
    raise Refused(f"no rate for {currency} on {date}")


def cents(value):
    from decimal import ROUND_HALF_UP
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def discount_today(books, record):
    """The early-payment discount of a payable paid today, in its own currency (zero outside the vendor's window)."""
    vendor = books["partners"][record["vendor"]]
    if vendor.get("discount_days") is None:
        return Decimal(0)
    import datetime
    window = (datetime.date.fromisoformat(record["date"]) + datetime.timedelta(days=vendor["discount_days"])).isoformat()
    return cents(Decimal(record["gross"]) * Decimal(vendor["discount_rate"])) if books["today"] <= window else Decimal(0)


def run_payments(books):
    """The payments already made in today's run: (count, {currency: cash paid}). The cash a payment uses is the amount
    it clears less the discount it took, so a discount leaves more of the run's cash for other payables."""
    today = books["today"]
    count, spent = 0, {}
    for entry in books["entries"]:
        if entry["date"] == today and entry["memo"].startswith(PAYMENT_MEMO):
            for line in entry["lines"]:
                if line["account"] == "2000":
                    count += 1
                    record = books["documents"].get(line["document"]) or books["inbox"].get(line["document"]) or {}
                    discount = discount_today(books, record) if record else Decimal(0)
                    spent[line["currency"]] = spent.get(line["currency"], Decimal(0)) + Decimal(line["amount"]) - discount
    return count, spent


def pay(books, document):
    """Pay an open payable in today's run, as section 7 of the manual describes."""
    record = books["documents"].get(document) or books["inbox"].get(document)
    if record is None or record.get("type") != "vendor-invoice" or record.get("status") not in (None, "posted"):
        raise Refused(f"no posted vendor invoice {document}")
    if record.get("disputed"):
        raise Refused(f"{document} is disputed and may not be paid")
    item = documents_of(books, "2000").get(document)
    if item is None or item["open"] <= 0:
        raise Refused(f"{document} is not open")
    settings = books["payment_run"]
    count, spent = run_payments(books)
    if count >= settings["max_payments"]:
        raise Refused(f"today's run may hold at most {settings['max_payments']} payments")
    currency = item["currency"]
    today = books["today"]
    discount = discount_today(books, record)
    amount = item["open"] - discount
    available = Decimal(settings["cash"][currency]) - spent.get(currency, Decimal(0))
    if amount > available:
        raise Refused(f"only {available} {currency} is left in today's run")
    today_rate = rate_on(books, currency, today)
    paid_eur = cents(amount * today_rate)
    discount_eur = cents(discount * today_rate)
    fee = Decimal(settings["fee_domestic"] if currency == "EUR" else settings["fee_foreign"])
    lines = [{"account": "2000", "debit": str(item["eur"]), "partner": record["vendor"], "document": document,
              "currency": currency, "amount": str(item["open"])},
             {"account": "1100", "credit": str(paid_eur + fee)},
             {"account": "6900", "debit": str(fee)}]
    if discount_eur > 0:
        lines.append({"account": "4910", "credit": str(discount_eur)})
    difference = item["eur"] - paid_eur - discount_eur
    if difference > 0:
        lines.append({"account": "7900", "credit": str(difference)})
    elif difference < 0:
        lines.append({"account": "7900", "debit": str(-difference)})
    entry = {"date": today, "memo": f"{PAYMENT_MEMO} {document}", "lines": lines}
    return post(books, entry)


def documents_of(books, account=None):
    """{document: {partner, currency, open, eur}} from the open-item lines of the ledger."""
    result = {}
    for entry in books["entries"]:
        for line in entry["lines"]:
            if line["account"] in OPEN_ITEMS and (account is None or line["account"] == account):
                item = result.setdefault(line["document"], {"account": line["account"], "partner": line["partner"], "currency": line["currency"],
                                                            "open": Decimal("0"), "eur": Decimal("0")})
                sign = 1 if ("debit" in line) == (OPEN_ITEMS[line["account"]] == "debit") else -1
                item["open"] += sign * Decimal(line["amount"])
                item["eur"] += sign * Decimal(line.get("debit") or line.get("credit"))
    return result


def check_entry(books, entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("lines"), list) or not entry["lines"]:
        raise Refused("an entry is an object with date, memo and a list of lines")
    if not isinstance(entry.get("date"), str) or not DATE.match(entry["date"]):
        raise Refused("date must be YYYY-MM-DD in 2026")
    if not isinstance(entry.get("memo", ""), str):
        raise Refused("memo must be text")
    debits = credits = Decimal("0")
    moves = {}
    for line in entry["lines"]:
        if not isinstance(line, dict) or line.get("account") not in books["accounts"]:
            raise Refused(f"unknown account in line {line!r}")
        if ("debit" in line) == ("credit" in line):
            raise Refused("each line has exactly one of debit and credit")
        value = money(line.get("debit") or line.get("credit"), "debit or credit")
        if "debit" in line:
            debits += value
        else:
            credits += value
        account = line["account"]
        allowed = {"account", "debit", "credit", "partner", "document", "currency", "amount"}
        if set(line) - allowed:
            raise Refused(f"unknown fields {sorted(set(line) - allowed)}")
        if account in OPEN_ITEMS:
            if line.get("partner") not in books["partners"] or not isinstance(line.get("document"), str) or line.get("currency") not in ("EUR", *books["rates"]):
                raise Refused(f"a line on {account} names a known partner, a document and its currency")
            amount = money(line.get("amount"), "amount")
            opens = ("debit" in line) == (OPEN_ITEMS[account] == "debit")
            key = line["document"]
            moves[key] = moves.get(key, Decimal("0")) + (amount if opens else -amount)
            known = documents_of(books, account).get(key)
            if known and (known["partner"] != line["partner"] or known["currency"] != line["currency"]):
                raise Refused(f"{key} belongs to {known['partner']} in {known['currency']}")
        elif account in NAMED:
            if not isinstance(line.get("document"), str) or (account != "2160" and line.get("partner") not in books["partners"]):
                raise Refused(f"a line on {account} names {'a document' if account == '2160' else 'a known partner and a document'}")
        elif "amount" in line or "currency" in line:
            raise Refused(f"a line on {account} has no document amount")
    if debits != credits:
        raise Refused(f"debits {debits} and credits {credits} differ")
    open_now = documents_of(books)
    for key, change in moves.items():
        if (open_now.get(key, {}).get("open", Decimal("0")) + change) < 0:
            raise Refused(f"the entry clears more of {key} than is open")


def post(books, entry):
    check_entry(books, entry)
    number = len(books["entries"]) + 1
    clean = {"id": f"JE-{number:05d}", "date": entry["date"], "period": entry["date"][:7], "memo": entry.get("memo", ""),
             "lines": [{key: value for key, value in line.items()} for line in entry["lines"]]}
    books["entries"].append(clean)
    return clean["id"]


def apply(books, command, args):
    """Apply one changing command; returns its output. Raises Refused."""
    if command == "begin":
        if len(args) != 1 or not re.fullmatch(r"R[0-9]+", args[0]):
            raise Refused("begin takes a request number such as R3")
        return "ok"
    if command == "post":
        if len(args) != 1 or not isinstance(args[0], dict):
            raise Refused("post takes one entry")
        return post(books, args[0])
    if command == "pay":
        if len(args) != 1 or not isinstance(args[0], str):
            raise Refused("pay takes one document")
        return pay(books, args[0])
    if command == "set-status":
        if len(args) != 2 or args[0] not in books["inbox"] or args[1] not in ("posted", "rejected", "blocked", "held"):
            raise Refused("set-status takes an inbox invoice and one of posted, rejected, blocked, held")
        books["inbox"][args[0]]["status"] = args[1]
        return "ok"
    raise Refused(f"unknown command {command}")


def look(books, command, args):
    if command == "accounts":
        return books["accounts"]
    if command == "periods":
        return books["periods"]
    if command == "rates":
        if len(args) != 1 or args[0] not in books["rates"]:
            raise Refused(f"rates takes one of {', '.join(sorted(books['rates']))}")
        return books["rates"][args[0]]
    if command == "partners":
        kind = args[0][:-1] if args and args[0] in ("customers", "vendors") else None
        return {key: partner for key, partner in sorted(books["partners"].items()) if kind is None or partner["kind"] == kind}
    if command == "show-partner":
        return books["partners"].get(args[0]) if args else None
    if command == "open-items":
        if not args:
            raise Refused("open-items takes a partner")
        return {key: {"account": item["account"], "currency": item["currency"], "open": str(item["open"]), "eur_balance": str(item["eur"])}
                for key, item in sorted(documents_of(books).items()) if item["partner"] == args[0] and item["open"] != 0}
    if command == "show-document":
        if not args:
            raise Refused("show-document takes an id")
        return books["documents"].get(args[0]) or books["inbox"].get(args[0]) or books["contracts"].get(args[0])
    if command == "bank":
        return books["bank"]
    if command == "cash":
        count, spent = run_payments(books)
        return {**books["payment_run"], "payments_made": count,
                "cash_left": {currency: str(Decimal(amount) - spent.get(currency, Decimal(0))) for currency, amount in books["payment_run"]["cash"].items()}}
    if command == "inbox":
        return {key: {"vendor": item["vendor"], "number": item["number"], "date": item["date"], "status": item["status"]} for key, item in sorted(books["inbox"].items())}
    if command == "receipts":
        if not args:
            raise Refused("receipts takes a purchase order")
        return [receipt for receipt in books["receipts"] if receipt["po"] == args[0]]
    if command == "contracts":
        return books["contracts"]
    if command == "approvers":
        return books["approvers"]
    if command == "entries":
        filters = dict(zip(args[::2], args[1::2]))
        if set(filters) - {"--document", "--account", "--partner"} or len(args) % 2:
            raise Refused("entries takes --document, --account and --partner filters")
        def matches(line):
            return all(line.get(key[2:]) == value for key, value in filters.items())
        return [entry for entry in books["entries"] if any(matches(line) for line in entry["lines"])]
    raise Refused(f"unknown command {command}")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, args = argv[0], argv[1:]
    with open(BOOKS, encoding="utf-8") as handle:
        books = json.load(handle)
    try:
        if command in ("begin", "post", "set-status", "pay"):
            if command == "post":
                if len(args) != 1:
                    raise Refused("post takes one file (or - for standard input)")
                try:
                    text = sys.stdin.read() if args[0] == "-" else open(args[0], encoding="utf-8").read()
                    args = [json.loads(text)]
                except (OSError, json.JSONDecodeError) as error:
                    raise Refused(f"cannot read the entry: {error}")
            output = apply(books, command, args)
            with open(BOOKS, "w", encoding="utf-8") as handle:
                json.dump(books, handle, indent=1, sort_keys=True)
            with open(AUDIT, "a", encoding="utf-8") as handle:
                handle.write(json.dumps([command, *args]) + "\n")
            print(output)
        else:
            print(json.dumps(look(books, command, args), indent=1, sort_keys=True))
    except Refused as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
