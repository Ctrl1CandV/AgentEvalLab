"""The shop's data and the T2 tickets. Each ticket lists the desk.py commands that carry out what the policy allows,
and which numbered requests are done and declined. All were worked out by hand from POLICY.md; today is 2026-10-20.
"""


def line(sku, qty, price):
    return {"sku": sku, "qty": qty, "price": price, "state": "active", "returned": 0}


def order(customer, status, placed, promised, delivered, payment, address, lines, compensated=None):
    return {"customer": customer, "status": status, "placed": placed, "promised": promised, "delivered": delivered, "payment": payment,
            "address": address, "lines": lines, "refunds": [], "compensated": compensated}


BASE_DB = {
    "customers": {
        "C-1001": {"name": "Ana Ruiz", "email": "ana.ruiz@example.com", "tier": "standard", "credit": "0.00"},
        "C-1002": {"name": "Ben Okoro", "email": "ben@okoro.example", "tier": "gold", "credit": "0.00"},
        "C-1003": {"name": "Chen Wei", "email": "chen.wei@example.com", "tier": "standard", "credit": "5.00"},
        "C-1004": {"name": "Dana Kim", "email": "dana.k@example.com", "tier": "standard", "credit": "0.00"},
    },
    "products": {
        "EL-100": {"name": "Noise-cancelling headphones", "family": "headphones", "category": "electronics", "price": "129.00"},
        "EL-101": {"name": "Wired headphones", "family": "headphones", "category": "electronics", "price": "39.00"},
        "EL-102": {"name": "Studio headphones", "family": "headphones", "category": "electronics", "price": "159.00"},
        "EL-200": {"name": "E-reader", "family": "ereader", "category": "electronics", "price": "99.00"},
        "BK-300": {"name": "Atlas of Rivers", "family": "book", "category": "books", "price": "28.00"},
        "BK-301": {"name": "Field Guide to Moths", "family": "book", "category": "books", "price": "19.50"},
        "HM-400": {"name": "Linen throw", "family": "throw", "category": "home", "price": "45.00"},
        "HM-401": {"name": "Wool throw", "family": "throw", "category": "home", "price": "65.00"},
        "HM-402": {"name": "Cotton throw", "family": "throw", "category": "home", "price": "35.00"},
    },
    "orders": {
        "O-5001": order("C-1001", "processing", "2026-10-18", "2026-10-23", None, "card", "4 Elm Row, Leeds", [line("HM-400", 1, "45.00"), line("BK-300", 1, "28.00")]),
        "O-5002": order("C-1001", "delivered", "2026-10-01", "2026-10-06", "2026-10-10", "card", "4 Elm Row, Leeds", [line("EL-100", 1, "129.00")]),
        "O-5003": order("C-1002", "delivered", "2026-09-05", "2026-09-10", "2026-09-12", "card", "17 Dock Road, Bristol",
                        [line("EL-102", 2, "159.00"), line("HM-401", 1, "65.00")]),
        "O-5004": order("C-1003", "delivered", "2026-09-28", "2026-10-02", "2026-10-05", "gift_card", "2 Mill Lane, York",
                        [line("BK-301", 1, "19.50"), line("EL-200", 1, "99.00")]),
        "O-5005": order("C-1003", "shipped", "2026-10-17", "2026-10-21", None, "card", "2 Mill Lane, York", [line("HM-402", 2, "35.00")]),
        "O-5006": order("C-1004", "delivered", "2026-09-01", "2026-09-05", "2026-09-15", "card", "8 Park View, Bath", [line("HM-400", 1, "45.00")],
                        compensated="4.50"),
        "O-5007": order("C-1004", "delivered", "2026-10-05", "2026-10-09", "2026-10-09", "card", "8 Park View, Bath",
                        [line("HM-401", 1, "65.00"), line("EL-101", 1, "39.00")]),
        "O-5008": order("C-1002", "delivered", "2026-10-03", "2026-10-08", "2026-10-12", "card", "17 Dock Road, Bristol",
                        [line("EL-100", 2, "129.00"), line("BK-300", 1, "28.00")]),
    },
}

TICKETS = {
    "t01": {"sender": "ana.ruiz@example.com",
            "requests": ["Please cancel my order O-5001, I ordered by mistake."],
            "actions": [["cancel-order", "O-5001"]], "done": [1], "declined": []},
    "t02": {"sender": "ana.ruiz@example.com",
            "requests": ["I want to return the headphones from order O-5002. They work fine, they just are not comfortable.",
                         "That order also arrived late. I would like the compensation you offer for that."],
            "actions": [["refund", "O-5002", "EL-100", "1", "109.65", "original"], ["compensate", "O-5002", "12.90"]], "done": [1, 2], "declined": []},
    "t03": {"sender": "ben@okoro.example",
            "requests": ["Please take back one of the two studio headphones from order O-5003.",
                         "And swap the wool throw in that order for the linen throw."],
            "actions": [], "done": [], "declined": [1, 2]},
    "t04": {"sender": "chen.wei@example.com",
            "requests": ["The e-reader from order O-5004 is defective. I want my money back.",
                         "Please also take back the moth field guide from the same order.",
                         "Change the delivery address of order O-5005 to 9 Quay Street, Hull."],
            "actions": [["refund", "O-5004", "EL-200", "1", "99.00", "credit"]], "done": [1], "declined": [2, 3]},
    "t05": {"sender": "dana.k@example.com",
            "requests": ["Exchange the wool throw in order O-5007 for the cotton throw.",
                         "Exchange the wired headphones in O-5007 for the studio headphones.",
                         "Order O-5006 came ten days late. I would like compensation."],
            "actions": [["exchange", "O-5007", "HM-401", "HM-402"], ["add-credit", "C-1004", "30.00"]], "done": [1], "declined": [2, 3]},
    "t06": {"sender": "ana.ruiz@example.com",
            "requests": ["Please return the e-reader in order O-5004. It is defective.",
                         "And remove the Atlas of Rivers from my order O-5001; I will keep the throw."],
            "actions": [["cancel-line", "O-5001", "BK-300"]], "done": [2], "declined": [1]},
    "t07": {"sender": "BEN@OKORO.EXAMPLE",
            "requests": ["Return one of the two noise-cancelling headphones from order O-5008.",
                         "O-5008 was late. Please compensate me as your policy says.",
                         "Return the Atlas of Rivers from O-5008 as well."],
            "actions": [["refund", "O-5008", "EL-100", "1", "129.00", "original"], ["compensate", "O-5008", "28.60"],
                        ["refund", "O-5008", "BK-300", "1", "28.00", "original"]], "done": [1, 2, 3], "declined": []},
    "t08": {"sender": "chen.wei@example.com",
            "requests": ["Cancel order O-5005, please.",
                         "If you cannot, give me 10.00 of store credit for the trouble.",
                         "Order O-5004 was late too. I would like the compensation for that."],
            "actions": [["compensate", "O-5004", "11.85"]], "done": [3], "declined": [1, 2]},
}


def prompt(ticket_id):
    ticket = TICKETS[ticket_id]
    lines = [f"## Ticket {ticket_id.upper()}", "", f"From: {ticket['sender']}", ""]
    lines += [f"({number}) {text}" for number, text in enumerate(ticket["requests"], 1)]
    return "\n".join(lines) + "\n"
