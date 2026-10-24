#!/usr/bin/env python3
"""Reference implementation of the E2 ledger specification (items/ledger/prompt.md). Standard library only."""
import json
import re
import sys
from decimal import ROUND_HALF_EVEN, Decimal

PLACES = {"EUR": 2, "USD": 2, "JPY": 0}
NUMBER = re.compile(r"^[0-9]+(\.[0-9]+)?$")
TYPES = {"open", "deposit", "withdraw", "transfer", "hold", "release", "capture", "freeze", "unfreeze", "reverse"}


class Rejected(Exception):
    def __init__(self, code):
        self.code = code


def amount(value, currency):
    """A valid amount in the currency, or None."""
    if not isinstance(value, str) or not NUMBER.match(value):
        return None
    decimals = len(value.split(".")[1]) if "." in value else 0
    number = Decimal(value)
    return number if decimals <= PLACES[currency] and number > 0 else None


def rate(value):
    if not isinstance(value, str) or not NUMBER.match(value):
        return None
    number = Decimal(value)
    return number if number > 0 else None


def text(value, currency):
    quantized = value.quantize(Decimal(1).scaleb(-PLACES[currency]))
    if quantized == 0:
        quantized = abs(quantized)
    return f"{quantized:f}"


class Ledger:
    def __init__(self):
        self.accounts = {}
        self.holds = {}          # hold id -> (account, amount), active holds only
        self.used_holds = set()  # ids of every successful hold
        self.seen = set()
        self.done = {}           # event id -> (event, effect) for ok deposits, withdrawals and transfers
        self.reversed = set()

    def available(self, name):
        account = self.accounts[name]
        held = sum((value for owner, value in self.holds.values() if owner == name), Decimal(0))
        return account["balance"] + account["limit"] - held

    def account(self, event, field):
        name = event.get(field)
        if not isinstance(name, str) or name not in self.accounts:
            raise Rejected("UNKNOWN_ACCOUNT")
        return name

    def apply(self, event):
        kind = event.get("type")
        if kind not in TYPES:
            raise Rejected("UNKNOWN_TYPE")
        getattr(self, "do_" + kind)(event)

    def do_open(self, event):
        currency = event.get("currency")
        if currency not in PLACES:
            raise Rejected("UNKNOWN_CURRENCY")
        if event.get("account") in self.accounts:
            raise Rejected("DUPLICATE_ACCOUNT")
        limit = Decimal(0)
        if "limit" in event:
            if event["limit"] != "0":
                limit = amount(event["limit"], currency)
                if limit is None:
                    raise Rejected("INVALID_AMOUNT")
        self.accounts[event["account"]] = {"currency": currency, "balance": Decimal(0), "limit": limit, "frozen": False}

    def paying(self, name):
        if self.accounts[name]["frozen"]:
            raise Rejected("ACCOUNT_FROZEN")

    def money(self, event, name):
        value = amount(event.get("amount"), self.accounts[name]["currency"])
        if value is None:
            raise Rejected("INVALID_AMOUNT")
        return value

    def funds(self, name, value):
        if value > self.available(name):
            raise Rejected("INSUFFICIENT_FUNDS")

    def do_deposit(self, event):
        name = self.account(event, "account")
        value = self.money(event, name)
        self.accounts[name]["balance"] += value
        self.done[event["id"]] = ("deposit", name, value)

    def do_withdraw(self, event):
        name = self.account(event, "account")
        self.paying(name)
        value = self.money(event, name)
        self.funds(name, value)
        self.accounts[name]["balance"] -= value
        self.done[event["id"]] = ("withdraw", name, value)

    def do_transfer(self, event):
        source, target = self.account(event, "from"), self.account(event, "to")
        if source == target:
            raise Rejected("SAME_ACCOUNT")
        self.paying(source)
        value = self.money(event, source)
        source_currency, target_currency = self.accounts[source]["currency"], self.accounts[target]["currency"]
        if source_currency == target_currency:
            if "rate" in event:
                raise Rejected("INVALID_RATE")
            credited = value
        else:
            factor = rate(event.get("rate"))
            if factor is None:
                raise Rejected("INVALID_RATE")
            credited = (value * factor).quantize(Decimal(1).scaleb(-PLACES[target_currency]), rounding=ROUND_HALF_EVEN)
            if credited == 0:
                raise Rejected("INVALID_AMOUNT")
        self.funds(source, value)
        self.accounts[source]["balance"] -= value
        self.accounts[target]["balance"] += credited
        self.done[event["id"]] = ("transfer", source, value, target, credited)

    def do_hold(self, event):
        name = self.account(event, "account")
        self.paying(name)
        value = self.money(event, name)
        if event.get("hold") in self.used_holds:
            raise Rejected("DUPLICATE_HOLD")
        self.funds(name, value)
        self.holds[event["hold"]] = (name, value)
        self.used_holds.add(event["hold"])

    def active_hold(self, event):
        hold = event.get("hold")
        if not isinstance(hold, str) or hold not in self.holds:
            raise Rejected("UNKNOWN_HOLD")
        return hold

    def do_release(self, event):
        del self.holds[self.active_hold(event)]

    def do_capture(self, event):
        hold = self.active_hold(event)
        name, held = self.holds[hold]
        self.paying(name)
        value = self.money(event, name) if "amount" in event else held
        if value > held:
            raise Rejected("EXCEEDS_HOLD")
        del self.holds[hold]
        self.accounts[name]["balance"] -= value

    def do_freeze(self, event):
        self.accounts[self.account(event, "account")]["frozen"] = True

    def do_unfreeze(self, event):
        self.accounts[self.account(event, "account")]["frozen"] = False

    def do_reverse(self, event):
        target = event.get("target")
        if target not in self.done or target in self.reversed:
            raise Rejected("NOT_REVERSIBLE")
        effect = self.done[target]
        if effect[0] == "deposit":
            self.funds(effect[1], effect[2])
            self.accounts[effect[1]]["balance"] -= effect[2]
        elif effect[0] == "withdraw":
            self.accounts[effect[1]]["balance"] += effect[2]
        else:
            _, source, value, receiver, credited = effect
            self.funds(receiver, credited)
            self.accounts[receiver]["balance"] -= credited
            self.accounts[source]["balance"] += value
        self.reversed.add(target)

    def run(self, events):
        results = []
        for event in events:
            identifier = event["id"]
            if identifier in self.seen:
                results.append({"id": identifier, "status": "duplicate", "error": None})
                continue
            self.seen.add(identifier)
            try:
                self.apply(event)
                results.append({"id": identifier, "status": "ok", "error": None})
            except Rejected as rejected:
                results.append({"id": identifier, "status": "rejected", "error": rejected.code})
        accounts = {name: {"currency": account["currency"], "balance": text(account["balance"], account["currency"]),
                           "available": text(self.available(name), account["currency"]), "frozen": account["frozen"]}
                    for name, account in self.accounts.items()}
        return {"accounts": accounts, "results": results}


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(Ledger().run(data["events"])))


if __name__ == "__main__":
    main()
