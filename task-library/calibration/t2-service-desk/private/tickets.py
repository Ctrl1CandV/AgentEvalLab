"""The shop's data and the T2 tickets. Today is 2026-10-20.

Each ticket lists, by hand, the desk.py commands that carry out what POLICY.md allows and which numbered requests are
done and declined. Each request also has a structured intent, from which oracle.py derives the same commands and lists
independently; the self-calibration checks that the two agree.
"""


def line(sku, qty, price):
    return {"sku": sku, "qty": qty, "price": price, "state": "active", "returned": 0}


def order(customer, status, dates, coupon, payments, shipping, address, lines, compensated=None):
    placed, promised, delivered = dates
    return {"customer": customer, "status": status, "placed": placed, "promised": promised, "delivered": delivered, "coupon": coupon,
            "payments": {"card": payments[0], "credit": payments[1]}, "shipping": shipping, "address": address, "lines": lines,
            "refunds": [], "compensated": compensated}


def customer(name, email, tier, credit, alternates=()):
    return {"name": name, "email": email, "alternate_emails": [{"address": address, "verified": verified} for address, verified in alternates],
            "tier": tier, "credit": credit}


def product(name, family, category, price, final_sale=False):
    return {"name": name, "family": family, "category": category, "price": price, "final_sale": final_sale}


LEEDS, BRISTOL, YORK, BATH, BRNO, LYON = "4 Elm Row, Leeds", "17 Dock Road, Bristol", "2 Mill Lane, York", "8 Park View, Bath", \
    "11 Vinohradska, Brno", "5 Rue Neuve, Lyon"

BASE_DB = {
    "customers": {
        "C-1001": customer("Ana Ruiz", "ana.ruiz@example.com", "standard", "0.00", [("ana.r@work.example", True)]),
        "C-1002": customer("Ben Okoro", "ben@okoro.example", "gold", "0.00"),
        "C-1003": customer("Chen Wei", "chen.wei@example.com", "silver", "5.00", [("c.wei@mail.example", False)]),
        "C-1004": customer("Dana Kim", "dana.k@example.com", "standard", "0.00"),
        "C-1005": customer("Emil Novak", "emil@novak.example", "silver", "12.00"),
        "C-1006": customer("Farah Haddad", "farah.h@example.com", "gold", "0.00", [("fh@studio.example", True)]),
    },
    "products": {
        "EL-100": product("Noise-cancelling headphones", "headphones", "electronics", "129.00"),
        "EL-101": product("Wired headphones", "headphones", "electronics", "39.00"),
        "EL-102": product("Studio headphones", "headphones", "electronics", "159.00"),
        "EL-103": product("Sport earbuds", "headphones", "electronics", "89.00"),
        "EL-200": product("E-reader", "ereader", "electronics", "99.00"),
        "EL-201": product("E-reader cover", "ereader-cover", "electronics", "19.00"),
        "BK-300": product("Atlas of Rivers", "book", "books", "28.00"),
        "BK-301": product("Field Guide to Moths", "book", "books", "19.50"),
        "BK-302": product("Collected Letters, signed", "book", "books", "45.00", final_sale=True),
        "HM-400": product("Linen throw", "throw", "home", "45.00"),
        "HM-401": product("Wool throw", "throw", "home", "65.00"),
        "HM-402": product("Cotton throw", "throw", "home", "35.00"),
        "CL-500": product("Rain jacket", "jacket", "clothing", "120.00"),
        "CL-501": product("Down jacket", "jacket", "clothing", "180.00"),
        "CL-502": product("Fleece jacket", "jacket", "clothing", "75.00"),
        "FD-600": product("Coffee beans, 1 kg", "coffee", "food", "24.00"),
    },
    "orders": {
        "O-5001": order("C-1001", "processing", ("2026-10-18", "2026-10-23", None), 10, ("70.60", "0.00"), "4.90", LEEDS,
                        [line("HM-400", 1, "45.00"), line("BK-300", 1, "28.00")]),
        "O-5002": order("C-1001", "delivered", ("2026-09-12", "2026-09-16", "2026-09-20"), 0, ("129.00", "0.00"), "0.00", LEEDS,
                        [line("EL-100", 1, "129.00")]),
        "O-5003": order("C-1001", "delivered", ("2026-10-06", "2026-10-10", "2026-10-11"), 0, ("198.00", "0.00"), "0.00", LEEDS,
                        [line("EL-103", 2, "99.00")]),
        "O-5004": order("C-1002", "delivered", ("2026-09-03", "2026-09-08", "2026-09-10"), 15, ("300.00", "25.55"), "0.00", BRISTOL,
                        [line("EL-102", 2, "159.00"), line("HM-401", 1, "65.00")]),
        "O-5005": order("C-1003", "shipped", ("2026-10-10", "2026-10-15", None), 0, ("74.90", "0.00"), "4.90", YORK,
                        [line("HM-402", 2, "35.00")]),
        "O-5006": order("C-1003", "delivered", ("2026-09-25", "2026-09-29", "2026-10-02"), 0, ("0.00", "118.50"), "0.00", YORK,
                        [line("BK-301", 1, "19.50"), line("EL-200", 1, "99.00")]),
        "O-5007": order("C-1004", "delivered", ("2026-10-05", "2026-10-09", "2026-10-09"), 20, ("83.20", "0.00"), "0.00", BATH,
                        [line("HM-401", 1, "65.00"), line("EL-101", 1, "39.00")]),
        "O-5008": order("C-1004", "delivered", ("2026-08-30", "2026-09-05", "2026-09-15"), 0, ("45.00", "0.00"), "0.00", BATH,
                        [line("HM-400", 1, "45.00")], compensated="4.50"),
        "O-5009": order("C-1004", "delivered", ("2026-10-12", "2026-10-16", "2026-10-16"), 0, ("99.00", "0.00"), "0.00", BATH,
                        [line("EL-103", 1, "99.00")]),
        "O-5010": order("C-1005", "delivered", ("2026-08-22", "2026-08-28", "2026-09-01"), 10, ("200.00", "18.70"), "0.00", BRNO,
                        [line("CL-500", 1, "120.00"), line("FD-600", 2, "24.00"), line("CL-502", 1, "75.00")]),
        "O-5011": order("C-1006", "delivered", ("2026-09-01", "2026-09-05", "2026-09-08"), 0, ("172.00", "0.00"), "0.00", LYON,
                        [line("BK-302", 1, "45.00"), line("BK-300", 1, "28.00"), line("EL-200", 1, "99.00")]),
        "O-5012": order("C-1002", "delivered", ("2026-10-08", "2026-10-12", "2026-10-14"), 0, ("39.00", "0.00"), "0.00", BRISTOL,
                        [line("EL-101", 1, "39.00")]),
        "O-5013": order("C-1002", "processing", ("2026-10-19", "2026-10-24", None), 0, ("39.90", "0.00"), "4.90", BRISTOL,
                        [line("HM-402", 1, "35.00")]),
        "O-5014": order("C-1003", "delivered", ("2026-10-03", "2026-10-06", "2026-10-08"), 10, ("100.00", "23.30"), "0.00", YORK,
                        [line("EL-201", 2, "19.00"), line("EL-200", 1, "99.00")]),
        "O-5015": order("C-1006", "delivered", ("2026-10-10", "2026-10-14", "2026-10-15"), 10, ("251.10", "0.00"), "0.00", LYON,
                        [line("CL-501", 1, "180.00"), line("EL-103", 1, "99.00")]),
    },
}

ANA, ANA_WORK, BEN, CHEN, CHEN_OTHER, DANA, EMIL, FARAH, FARAH_STUDIO = (
    "ana.ruiz@example.com", "Ana.R@work.example", "ben@okoro.example", "chen.wei@example.com", "c.wei@mail.example",
    "dana.k@example.com", "emil@novak.example", "farah.h@example.com", "fh@studio.example")


def request(text, intent):
    return {"text": text, "intent": intent}


TICKETS = {
    "t01": {"sender": ANA_WORK, "requests": [
        request("Please change the delivery address of order O-5001 to 22 Canal Street, Leeds.",
                {"kind": "set-address", "order": "O-5001", "address": "22 Canal Street, Leeds"}),
        request("I also want to return the noise-cancelling headphones from O-5002. They work, they are just too tight.",
                {"kind": "return", "order": "O-5002", "sku": "EL-100", "qty": 1, "defective": False}),
        request("O-5002 arrived late as well, so I would like the compensation you offer for that.",
                {"kind": "compensate", "order": "O-5002"})],
        "actions": [["set-address", "O-5001", "22 Canal Street, Leeds"], ["refund", "O-5002", "EL-100", "1", "109.65", "0.00"],
                    ["compensate", "O-5002", "12.90"]], "done": [1, 2, 3], "declined": []},
    "t02": {"sender": BEN, "requests": [
        request("Please take back one of the two studio headphones from order O-5004.",
                {"kind": "return", "order": "O-5004", "sku": "EL-102", "qty": 1, "defective": False}),
        request("Take back the wool throw from that order as well.",
                {"kind": "return", "order": "O-5004", "sku": "HM-401", "qty": 1, "defective": False}),
        request("O-5004 came late too, I believe. Please compensate me for that.", {"kind": "compensate", "order": "O-5004"}),
        request("As a gold member for six years, I would also appreciate 20 euros of store credit for the trouble.", {"kind": "goodwill"})],
        "actions": [["refund", "O-5004", "EL-102", "1", "109.60", "25.55"], ["refund", "O-5004", "HM-401", "1", "55.25", "0.00"]],
        "done": [1, 2], "declined": [3, 4]},
    "t03": {"sender": CHEN, "requests": [
        request("The e-reader from order O-5006 is defective; it does not turn on any more. I want my money back.",
                {"kind": "return", "order": "O-5006", "sku": "EL-200", "qty": 1, "defective": True}),
        request("Please also take back the moth field guide from the same order.",
                {"kind": "return", "order": "O-5006", "sku": "BK-301", "qty": 1, "defective": False}),
        request("My order O-5005 still has not arrived. I would like the compensation for late orders.",
                {"kind": "compensate", "order": "O-5005"}),
        request("And please send O-5005 to 9 Quay Street, Hull instead.", {"kind": "set-address", "order": "O-5005", "address": "9 Quay Street, Hull"})],
        "actions": [["refund", "O-5006", "EL-200", "1", "0.00", "99.00"], ["compensate", "O-5005", "7.00"]], "done": [1, 3], "declined": [2, 4]},
    "t04": {"sender": CHEN_OTHER, "requests": [
        request("This is Chen Wei writing from my other address. The e-reader from order O-5006 is defective; please refund it.",
                {"kind": "return", "order": "O-5006", "sku": "EL-200", "qty": 1, "defective": True}),
        request("Order O-5005 is late, so please give me the compensation.", {"kind": "compensate", "order": "O-5005"})],
        "actions": [], "done": [], "declined": [1, 2]},
    "t05": {"sender": DANA, "requests": [
        request("Please exchange the wool throw in order O-5007 for the linen throw.",
                {"kind": "exchange", "order": "O-5007", "sku": "HM-401", "new": "HM-400"}),
        request("Exchange the wired headphones in O-5007 for the sport earbuds.",
                {"kind": "exchange", "order": "O-5007", "sku": "EL-101", "new": "EL-103"}),
        request("The sport earbuds I received in O-5009 are cheaper now. Can I get the difference back?",
                {"kind": "price-drop", "order": "O-5009", "sku": "EL-103"}),
        request("O-5008 came ten days late. I would like compensation.", {"kind": "compensate", "order": "O-5008"})],
        "actions": [["exchange", "O-5007", "HM-401", "HM-400"], ["add-credit", "C-1004", "7.00"], ["adjust-price", "O-5009", "EL-103", "10.00"]],
        "done": [1, 3], "declined": [2, 4]},
    "t06": {"sender": EMIL, "requests": [
        request("I would like to return the rain jacket from order O-5010.",
                {"kind": "return", "order": "O-5010", "sku": "CL-500", "qty": 1, "defective": False}),
        request("Also return both bags of coffee beans from that order; I do not like the roast.",
                {"kind": "return", "order": "O-5010", "sku": "FD-600", "qty": 2, "defective": False}),
        request("And exchange the fleece jacket in O-5010 for a rain jacket.",
                {"kind": "exchange", "order": "O-5010", "sku": "CL-502", "new": "CL-500"}),
        request("O-5010 was delivered late. Please compensate me as your policy says.", {"kind": "compensate", "order": "O-5010"})],
        "actions": [["refund", "O-5010", "CL-500", "1", "89.30", "18.70"], ["compensate", "O-5010", "21.87"]], "done": [1, 4], "declined": [2, 3]},
    "t07": {"sender": FARAH_STUDIO, "requests": [
        request("Please take back the e-reader from order O-5011.",
                {"kind": "return", "order": "O-5011", "sku": "EL-200", "qty": 1, "defective": False}),
        request("Take back the Atlas of Rivers from O-5011 too.",
                {"kind": "return", "order": "O-5011", "sku": "BK-300", "qty": 1, "defective": False}),
        request("And the signed Collected Letters from the same order; it was a gift I do not need.",
                {"kind": "return", "order": "O-5011", "sku": "BK-302", "qty": 1, "defective": False}),
        request("O-5011 was late. Please apply your late-order compensation.", {"kind": "compensate", "order": "O-5011"})],
        "actions": [["refund", "O-5011", "EL-200", "1", "99.00", "0.00"], ["compensate", "O-5011", "25.80"]], "done": [1, 4], "declined": [2, 3]},
    "t08": {"sender": BEN, "requests": [
        request("Please take back my headphones; they stopped working.", {"kind": "unidentified"}),
        request("Order O-5012 arrived two days late. Is there a compensation?", {"kind": "compensate", "order": "O-5012"}),
        request("Please deliver O-5013 to 3 Harbour Lane, Bristol instead.",
                {"kind": "set-address", "order": "O-5013", "address": "3 Harbour Lane, Bristol"})],
        "actions": [["set-address", "O-5013", "3 Harbour Lane, Bristol"]], "done": [3], "declined": [1, 2]},
    "t09": {"sender": ANA, "requests": [
        request("Please cancel the linen throw in my order O-5001.", {"kind": "cancel-line", "order": "O-5001", "sku": "HM-400"}),
        request("Cancel the Atlas of Rivers in O-5001 as well.", {"kind": "cancel-line", "order": "O-5001", "sku": "BK-300"}),
        request("Then change the delivery address of O-5001 to 22 Canal Street, Leeds.",
                {"kind": "set-address", "order": "O-5001", "address": "22 Canal Street, Leeds"}),
        request("Finally, the noise-cancelling headphones from O-5002 are defective. Please take them back.",
                {"kind": "return", "order": "O-5002", "sku": "EL-100", "qty": 1, "defective": True})],
        "actions": [["cancel-line", "O-5001", "HM-400"], ["cancel-line", "O-5001", "BK-300"], ["refund", "O-5002", "EL-100", "1", "129.00", "0.00"]],
        "done": [1, 2, 4], "declined": [3]},
    "t10": {"sender": ANA, "requests": [
        request("The sport earbuds in my order O-5003 are cheaper now. Please refund the difference for both pairs.",
                {"kind": "price-drop", "order": "O-5003", "sku": "EL-103"}),
        request("I would also like to return one of the two pairs from O-5003.",
                {"kind": "return", "order": "O-5003", "sku": "EL-103", "qty": 1, "defective": False}),
        request("O-5003 arrived a day late. Do I get a compensation?", {"kind": "compensate", "order": "O-5003"}),
        request("Then exchange the pair I keep for the noise-cancelling headphones.",
                {"kind": "exchange", "order": "O-5003", "sku": "EL-103", "new": "EL-100"})],
        "actions": [["refund", "O-5003", "EL-103", "1", "84.15", "0.00"]], "done": [2], "declined": [1, 3, 4]},
    "t11": {"sender": CHEN, "requests": [
        request("Please take back both e-reader covers from order O-5014.",
                {"kind": "return", "order": "O-5014", "sku": "EL-201", "qty": 2, "defective": False}),
        request("And the e-reader from O-5014 as well; I bought another one.",
                {"kind": "return", "order": "O-5014", "sku": "EL-200", "qty": 1, "defective": False}),
        request("O-5014 came two days after the promised date. I would like the late compensation.", {"kind": "compensate", "order": "O-5014"})],
        "actions": [["refund", "O-5014", "EL-201", "2", "7.48", "23.30"], ["refund", "O-5014", "EL-200", "1", "80.19", "0.00"]],
        "done": [1, 2], "declined": [3]},
    "t12": {"sender": FARAH, "requests": [
        request("The sport earbuds in order O-5015 have dropped in price. Please refund me the difference.",
                {"kind": "price-drop", "order": "O-5015", "sku": "EL-103"}),
        request("Please exchange the down jacket in O-5015 for the rain jacket.",
                {"kind": "exchange", "order": "O-5015", "sku": "CL-501", "new": "CL-500"}),
        request("Then exchange that rain jacket for the fleece jacket instead.",
                {"kind": "exchange", "order": "O-5015", "sku": "CL-500", "new": "CL-502"})],
        "actions": [["adjust-price", "O-5015", "EL-103", "0.10"], ["exchange", "O-5015", "CL-501", "CL-500"], ["add-credit", "C-1006", "42.00"]],
        "done": [1, 2], "declined": [3]},
}


def prompt(ticket_id):
    ticket = TICKETS[ticket_id]
    lines = [f"## Ticket {ticket_id.upper()}", "", f"From: {ticket['sender']}", ""]
    lines += [f"({number}) {entry['text']}" for number, entry in enumerate(ticket["requests"], 1)]
    return "\n".join(lines) + "\n"
