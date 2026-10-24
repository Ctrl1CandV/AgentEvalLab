#!/usr/bin/env python3
"""Hidden checks of the bisect item, run inside the sandbox from a directory that holds the candidate's pricing.py.

Prints one JSON object {check: true/false}. Each check holds several cases; a crash fails only that case's check.
"""
import json
import sys

sys.path.insert(0, ".")


def run(cases):
    try:
        import pricing
        return all(case(pricing) for case in cases)
    except Exception:
        return False


def raises(function):
    try:
        function()
    except ValueError:
        return True
    return False


def q(pricing, items, **options):
    return pricing.quote([{"unit_price": price, "quantity": quantity} for price, quantity in items], **options)


CHECKS = {
    # The regression: exactly 100 items get the bulk discount again.
    "regression-fixed": [
        lambda p: q(p, [("1.00", 100)])["net"] == "95.00",
        lambda p: q(p, [("2.00", 60), ("0.50", 40)])["net"] == "133.00",
        lambda p: q(p, [("1.00", 100)], currency="GBP")["shipping"] == "0",
        lambda p: q(p, [("1.00", 99)])["net"] == "99.00",
    ],
    # The intended change of the same commit stays: half-even rounding of the discount and the tax.
    "rounding-kept": [
        lambda p: q(p, [("0.25", 105), ("1.05", 1)])["net"] == "25.94",
        lambda p: q(p, [("10.025", 1)])["tax"] == "2.00",
    ],
    # Features added after the culprit keep working.
    "later-features": [
        lambda p: q(p, [("10.00", 2)])["shipping"] == "4.90",
        lambda p: q(p, [("60.00", 1)])["shipping"] == "0",
        lambda p: q(p, [("10.00", 2)], currency="GBP")["shipping"] == "3.95",
        lambda p: q(p, [("46.00", 1)], currency="GBP")["shipping"] == "0",
        lambda p: raises(lambda: q(p, [("4.99", 1)])),
        lambda p: raises(lambda: q(p, [("10.00", 1)], currency="USD")),
        lambda p: q(p, [("10.00", 2)])["total"] == "28.90",
    ],
    # Behaviour from before the culprit is unchanged.
    "coupons": [
        lambda p: q(p, [("20.00", 1)], coupon="WELCOME10")["net"] == "18.00",
        lambda p: q(p, [("1.00", 150)], coupon="SPRING5")["net"] == "142.50",
        lambda p: q(p, [("1.00", 150)], coupon="WELCOME10")["net"] == "135.00",
        lambda p: raises(lambda: q(p, [("20.00", 1)], coupon="FREE")),
    ],
}

if __name__ == "__main__":
    print(json.dumps({name: run(cases) for name, cases in CHECKS.items()}))
