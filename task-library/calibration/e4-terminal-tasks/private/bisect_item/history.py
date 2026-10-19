"""The git history of the bisect item: a pricing module whose bulk discount broke for exactly 100 items in a commit
that also made an intended change (half-even rounding), with later features built on top.

build(directory) creates the repository with fixed authors and dates, so commit hashes are reproducible, and returns
the culprit commit hash.
"""
import os
import subprocess

V1 = '''"""Order pricing for the shop."""
from decimal import ROUND_HALF_UP, Decimal

VAT = Decimal("0.20")


def subtotal(items):
    return sum((Decimal(item["unit_price"]) * item["quantity"] for item in items), Decimal(0))


def quote(items):
    net = subtotal(items)
    tax = (net * VAT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"net": str(net), "tax": str(tax), "total": str(net + tax)}
'''

V4 = '''"""Order pricing for the shop."""
from decimal import ROUND_HALF_UP, Decimal

VAT = Decimal("0.20")


def subtotal(items):
    return sum((Decimal(item["unit_price"]) * item["quantity"] for item in items), Decimal(0))


def discount(items, amount):
    """5% off orders of 100 items or more."""
    quantity = sum(item["quantity"] for item in items)
    if quantity >= 100:
        return (amount * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(0)


def quote(items):
    net = subtotal(items)
    net -= discount(items, net)
    tax = (net * VAT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"net": str(net), "tax": str(tax), "total": str(net + tax)}
'''

V6 = '''"""Order pricing for the shop."""
from decimal import ROUND_HALF_UP, Decimal

VAT = Decimal("0.20")
COUPONS = {"WELCOME10": Decimal("0.10"), "SPRING5": Decimal("0.05")}


def subtotal(items):
    return sum((Decimal(item["unit_price"]) * item["quantity"] for item in items), Decimal(0))


def discount(items, amount, coupon=None):
    """5% off orders of 100 items or more; a coupon gives its own rate. The larger discount wins; they do not stack."""
    quantity = sum(item["quantity"] for item in items)
    rate = Decimal(0)
    if quantity >= 100:
        rate = Decimal("0.05")
    if coupon is not None:
        rate = max(rate, COUPONS.get(coupon, Decimal(0)))
    return (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quote(items, coupon=None):
    net = subtotal(items)
    net -= discount(items, net, coupon)
    tax = (net * VAT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"net": str(net), "tax": str(tax), "total": str(net + tax)}
'''

V9 = V6.replace('''from decimal import ROUND_HALF_UP, Decimal
''', '''from decimal import ROUND_HALF_UP, Decimal


class PricingError(ValueError):
    pass
''').replace('''    if coupon is not None:
        rate = max(rate, COUPONS.get(coupon, Decimal(0)))''', '''    if coupon is not None:
        if coupon not in COUPONS:
            raise PricingError(f"unknown coupon {coupon}")
        rate = max(rate, COUPONS[coupon])''')

# The culprit: a refactor that names the constants and switches money rounding to half-even (intended, FIN-212), and
# that turns ">= 100" into "> BULK_THRESHOLD" (the regression).
V10 = '''"""Order pricing for the shop."""
from decimal import ROUND_HALF_EVEN, Decimal

VAT = Decimal("0.20")
BULK_THRESHOLD = 100
BULK_RATE = Decimal("0.05")
COUPONS = {"WELCOME10": Decimal("0.10"), "SPRING5": Decimal("0.05")}
CENT = Decimal("0.01")


class PricingError(ValueError):
    pass


def money(amount):
    """Round to cents, half to even (finance rule FIN-212)."""
    return amount.quantize(CENT, rounding=ROUND_HALF_EVEN)


def subtotal(items):
    return sum((Decimal(item["unit_price"]) * item["quantity"] for item in items), Decimal(0))


def discount(items, amount, coupon=None):
    """Bulk discount for large orders; a coupon gives its own rate. The larger discount wins; they do not stack."""
    quantity = sum(item["quantity"] for item in items)
    rate = BULK_RATE if quantity > BULK_THRESHOLD else Decimal(0)
    if coupon is not None:
        if coupon not in COUPONS:
            raise PricingError(f"unknown coupon {coupon}")
        rate = max(rate, COUPONS[coupon])
    return money(amount * rate)


def quote(items, coupon=None):
    net = subtotal(items)
    net -= discount(items, net, coupon)
    tax = money(net * VAT)
    return {"net": str(net), "tax": str(tax), "total": str(net + tax)}
'''

V12 = V10.replace('''CENT = Decimal("0.01")
''', '''CENT = Decimal("0.01")
SHIPPING = Decimal("4.90")
FREE_SHIPPING_FROM = Decimal("50.00")
''').replace('''    tax = money(net * VAT)
    return {"net": str(net), "tax": str(tax), "total": str(net + tax)}''', '''    tax = money(net * VAT)
    shipping = Decimal(0) if net >= FREE_SHIPPING_FROM else SHIPPING
    return {"net": str(net), "tax": str(tax), "shipping": str(shipping), "total": str(net + tax + shipping)}''')

V14 = V12.replace('''VAT = Decimal("0.20")
''', '''VAT = {"EUR": Decimal("0.20"), "GBP": Decimal("0.20")}
''').replace('''SHIPPING = Decimal("4.90")
FREE_SHIPPING_FROM = Decimal("50.00")
''', '''SHIPPING = {"EUR": Decimal("4.90"), "GBP": Decimal("3.95")}
FREE_SHIPPING_FROM = {"EUR": Decimal("50.00"), "GBP": Decimal("45.00")}
''').replace('''def quote(items, coupon=None):
    net = subtotal(items)''', '''def quote(items, coupon=None, currency="EUR"):
    if currency not in VAT:
        raise PricingError(f"unsupported currency {currency}")
    net = subtotal(items)''').replace('''    tax = money(net * VAT)
    shipping = Decimal(0) if net >= FREE_SHIPPING_FROM else SHIPPING''', '''    tax = money(net * VAT[currency])
    shipping = Decimal(0) if net >= FREE_SHIPPING_FROM[currency] else SHIPPING[currency]''')

V15 = V14.replace('''CENT = Decimal("0.01")
''', '''CENT = Decimal("0.01")
MINIMUM_ORDER = Decimal("5.00")
''').replace('''    net = subtotal(items)
    net -= discount(items, net, coupon)''', '''    net = subtotal(items)
    if net < MINIMUM_ORDER:
        raise PricingError("below the minimum order")
    net -= discount(items, net, coupon)''')

TESTS = '''import unittest

from pricing import quote


class QuoteTest(unittest.TestCase):
    def test_simple_order(self):
        self.assertEqual(quote([{"unit_price": "10.00", "quantity": 2}])["total"], "24.0000")
'''
TESTS_BULK = TESTS + '''
    def test_bulk_discount(self):
        self.assertEqual(quote([{"unit_price": "1.00", "quantity": 150}])["net"], "142.50")
'''
TESTS_COUPON = TESTS_BULK + '''
    def test_coupon(self):
        self.assertEqual(quote([{"unit_price": "20.00", "quantity": 1}], coupon="WELCOME10")["net"], "18.00")
'''

README = "# pricing\n\n`quote(items)` prices an order: net amount, VAT at 20%, and the total.\n\nRun the tests with `PYTHONPATH=. python3 -m unittest discover -s tests`.\n"
CHANGELOG = "# Changelog\n\n## 1.1.0\n\n- Bulk discount of 5% for orders of 100 items or more.\n- Coupons WELCOME10 and SPRING5.\n"

STEPS = [
    ("Add order pricing", {"pricing.py": V1}),
    ("Add tests", {"tests/test_pricing.py": TESTS.replace("24.0000", "24.00")}),
    ("Add README", {"README.md": README}),
    ("Add a 5% bulk discount for orders of 100 items or more", {"pricing.py": V4}),
    ("Test the bulk discount", {"tests/test_pricing.py": TESTS_BULK.replace("24.0000", "24.00")}),
    ("Add coupons; the larger of bulk and coupon discount wins", {"pricing.py": V6, "tests/test_pricing.py": TESTS_COUPON.replace("24.0000", "24.00")}),
    ("Document coupons", {"README.md": README + "\nCoupons: WELCOME10 (10%) and SPRING5 (5%). The larger of the coupon and the bulk discount applies.\n"}),
    ("Add CHANGELOG", {"CHANGELOG.md": CHANGELOG}),
    ("Raise PricingError for unknown coupons", {"pricing.py": V9}),
    ("Refactor discount code and round money half to even (FIN-212)", {"pricing.py": V10}),
    ("Changelog: half-even rounding (FIN-212)", {"CHANGELOG.md": CHANGELOG + "\n## 1.2.0\n\n- Money is rounded to cents half to even, as finance requires (FIN-212).\n"}),
    ("Add shipping: 4.90, free from 50.00 net", {"pricing.py": V12}),
    ("Test shipping", {"tests/test_pricing.py": TESTS_COUPON.replace('["total"], "24.0000"', '["total"], "28.90"') + '''
    def test_free_shipping(self):
        self.assertEqual(quote([{"unit_price": "60.00", "quantity": 1}])["shipping"], "0")
'''}),
    ("Support GBP prices", {"pricing.py": V14}),
    ("Refuse orders below 5.00 net", {"pricing.py": V15}),
    ("README: currencies, shipping and the minimum order", {"README.md": README + "\nCoupons: WELCOME10 (10%) and SPRING5 (5%). The larger of the coupon and the bulk discount applies.\n"
                                                                     "\nCurrencies: EUR and GBP. Shipping is 4.90 EUR or 3.95 GBP, free from 50.00 EUR or 45.00 GBP net. Orders below 5.00 net are refused.\n"}),
    ("Test GBP", {"tests/test_pricing.py": TESTS_COUPON.replace('["total"], "24.0000"', '["total"], "28.90"') + '''
    def test_free_shipping(self):
        self.assertEqual(quote([{"unit_price": "60.00", "quantity": 1}])["shipping"], "0")

    def test_gbp(self):
        self.assertEqual(quote([{"unit_price": "10.00", "quantity": 2}], currency="GBP")["shipping"], "3.95")
'''}),
    ("Changelog: 1.3.0", {"CHANGELOG.md": CHANGELOG + "\n## 1.2.0\n\n- Money is rounded to cents half to even, as finance requires (FIN-212).\n"
                                           "\n## 1.3.0\n\n- Shipping costs, GBP, and a minimum order of 5.00.\n"}),
]
CULPRIT_STEP = 9
HEAD_PRICING = V15


def build(directory):
    """Create the repository in directory (which must not exist) and return the culprit commit hash."""
    os.makedirs(directory)
    def git(*args, when=None):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory, "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_AUTHOR_NAME": "Rin Okafor", "GIT_AUTHOR_EMAIL": "rin@shop.example", "GIT_COMMITTER_NAME": "Rin Okafor",
               "GIT_COMMITTER_EMAIL": "rin@shop.example"}
        if when:
            env.update({"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
        return subprocess.run(["git", *args], cwd=directory, env=env, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q", "-b", "main")
    culprit = None
    for index, (message, files) in enumerate(STEPS):
        for path, text in files.items():
            os.makedirs(os.path.join(directory, os.path.dirname(path)) or directory, exist_ok=True)
            with open(os.path.join(directory, path), "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        git("add", "-A")
        git("commit", "-q", "-m", message, when=f"2026-0{3 + index // 6}-{1 + index % 6 * 4:02d}T10:{index:02d}:00+00:00")
        if index == CULPRIT_STEP:
            culprit = git("rev-parse", "HEAD")
    return culprit
