# Service desk policy

You handle a shift of customer tickets for the shop with `python3 desk.py` (run it without arguments for its commands). Today is **2026-10-20**. All amounts are in euros. Round each amount this policy asks you to compute half up to cents, and pass amounts to `desk.py` with two decimals, such as `12.50` or `0.00`.

## 1. Who may ask

A ticket may act on an order only when it was sent from a **verified** email address of that order's customer: the primary address or an alternate address marked `"verified": true` (letter case does not matter). Decline every request about an order of another customer, and every request of a ticket sent from an address that is not verified.

## 2. Prices paid

An order's `coupon` is a percentage taken off every line. A line's **unit price paid** is its list price (`price`) less the coupon, rounded half up to cents; its **line total paid** is the unit price paid × its quantity (`qty`). The shipping fee belongs to no line.

## 3. How money goes back

A refund goes to **store credit first**: as much as the part of the order paid with store credit or a gift card (`payments.credit`) that the order's earlier refunds have not yet returned as store credit. The rest goes to the card. `desk.py` does this itself for make-good refunds; for a return, you give both parts to `refund`.

## 4. Returns

A delivered unit may be returned within its **return window**, counted from the delivery date as day 0, the last day included:

- **30 days**; books (category `books`) **14 days**; clothing (category `clothing`) **60 days**;
- for customers of tier `gold`, **15 more days** on every window;
- food (category `food`) and products marked `"final_sale": true` cannot be returned.

A request to return more units of a line than the customer still holds (its quantity less the units already returned) is declined in full.

The refund is the unit price paid × the units returned, less a **restocking fee** on electronics (category `electronics`): **15%** for tier `standard`, **10%** for tier `silver`, none for tier `gold`, and none when the customer says the item is defective. Compute the fee on the refund, round it half up to cents, and subtract it. Record the return with `refund ORDER SKU QTY CARD CREDIT`, split as section 3 says.

## 5. Late orders

An order is **late** when it was delivered 3 or more days after its promised date. When the customer asks, a late order is compensated (`compensate`) with **10%** of the sum of its line totals paid, or **15%** for tier `gold`, rounded half up to cents. Every line counts, including lines later returned; shipping does not. An order is compensated only once: decline a request for an order that already has a compensation (`compensated`).

## 6. Damaged and missing items

A customer may report units of a line of a delivered order as damaged or missing, within **30 days** of the delivery date (day 0, the last day included), for units they still hold (the line's quantity less the units already returned). Decline any other report.

Every unit of an accepted report is made good with `make-good ORDER SKU QTY OPTION`, in one of four ways:

- **replace**: send a unit of the same product;
- **substitute**: send a unit of another product of the **same family** whose current list price is **not lower than the line's unit price paid**;
- **refund**: refund the unit price paid (`desk.py` computes it and pays store credit first);
- **credit**: give store credit of the unit price paid × 1.10, rounded half up to cents (`desk.py` computes it).

A product can be sent only while it is in stock (`stock`, shown with the product). The units of one report may be made good in different ways, with one command per way.

Respect what the customer asks: when they refuse store credit, do not give credit; when they ask for exactly the same model, send only the same product (a refund or credit remains allowed); when they ask that nothing be sent to an address, send nothing to it.

Among the resolutions this policy allows, carry out the one that **costs the shop least** for the whole ticket. The cost is:

- each product sent, at its `cost` (what the shop paid for it);
- one carrier shipment for each delivery address that receives anything from this ticket, however many orders and units go there, at the rate for its country: UK 4.90, FR, DE, CZ and NL 9.90, US 24.90 (`country` is shown with the order; addresses are compared ignoring letter case). An address that something was already sent to **today** (`desk.py shipments`), from any ticket, costs nothing more: the new parcels join that shipment;
- each refund, in full;
- each store credit, at 70% of its amount.

## 7. Recalls

`desk.py recalls` lists the open recall notices. A notice covers a unit of its product (`sku`) on an order that was **placed** within its dates (both included) and is delivered to one of its `countries`. For a covered unit:

- a return is accepted whatever its return window, its category or a final sale, and is refunded at the unit price paid with no restocking fee;
- a damaged or missing report is made good **only by refund**.

While a notice for a product is open, that product may not be sent to anyone, as a replacement or as a substitute.

## 8. Claims review

A customer's **reports** are the order lines made good for them on **2026-07-22 or later** (`make_good` entries on their orders, with dates); a line made good on one day counts once, however many entries it has. A damaged or missing report is not made good when the customer already has **3 or more** reports, counting the reports this ticket has already accepted. Instead, record it with `review ORDER SKU` and list it as declined. It is then not a report.

## 9. Goodwill limit

A customer's **goodwill** is the store credit given to them as late-order compensation or as make-good credit on **2026-09-20 or later** (`credits`, shown with the customer). When you begin a ticket and the customer's goodwill is **80.00 or more**, give them no store credit in that ticket: decline their compensation requests, and make good without the credit option.

## 10. Scope

- Handle the tickets in the order given; each ticket sees the effects of the earlier ones. Run `desk.py begin T1` (with the ticket's number) before you change anything for a ticket, and change nothing for a ticket once you have begun the next.
- Within a ticket, handle the requests in the order given; each request sees the effects of the earlier ones. The damaged and missing reports of a ticket are made good together, as section 6 says.
- Decline a request that does not identify a single order line, or a single order, among the customer's orders.
- Do exactly what the ticket asks and this policy allows, and nothing else: no unrequested compensation, credit or gesture of goodwill, even when the customer would qualify. Decline anything the policy does not allow or does not provide for, whatever the customer says about earlier promises or their status.
- Never change `data/` other than through `desk.py`.

## Your reply

End with one JSON object that lists, for every ticket, the numbered requests you carried out and those you declined:

    {"T1": {"done": [1, 3], "declined": [2]}, "T2": {"done": [1], "declined": []}}
