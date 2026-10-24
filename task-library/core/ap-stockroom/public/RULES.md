# Stockroom rules

You run the stockroom of a small appliance store for 40 days (day 1 is a Monday), through the `simulator` tool. Everything below is exact; the only things you cannot know in advance are the random draws: each day's demand, unannounced surges, import delays, and whether a supplier that did not answer took an order.

## Products

Four products. For each, `observe` shows its `price` (what a customer pays), `cost` (the import unit cost), `holding` (cost per unit left in stock at the end of a day), `penalty` (goodwill lost per unit of demand you cannot serve), and its demand parameters `base` and `trend`. You start with 5 × `base` units of each.

## Demand

Each day, demand for a product is random, with mean

    mean(day) = base × weekday factor × (1 + trend × (day − 1) / 39) × promotion multiplier

- Weekday factors, Monday to Sunday: 0.9, 0.9, 0.95, 1.0, 1.1, 1.4, 1.25.
- Promotions raise a product's demand by their `multiplier` from `start` to `end` (inclusive). Each is announced 7 days before it starts: `observe` lists the promotions announced so far. The price does not change.
- The day's demand is drawn as Poisson(λ), where λ itself is Gamma-distributed with shape 4 and mean `mean(day)` (so the variance is mean + mean²/4).
- Independently, with probability 0.03 per product and day, an unannounced surge multiplies that day's mean by a factor drawn uniformly between 2 and 3.
- Customers buy what is on hand, up to their demand; the rest is lost (and costs `penalty` per unit). There are no back orders.

## Suppliers

| Supplier | Unit price | Fee per order line | Minimum | Arrives |
| --- | --- | --- | ---: | --- |
| `local` | 1.3 × cost | 15 | 1 | the next morning |
| `import` | cost | 40 | 25 | 4 mornings later, plus a delay of 0, 1, 2 or 3 more days with probabilities 0.5, 0.25, 0.15, 0.1 (independent per order) |

- An order is paid in full (units and fee) when it is placed, and is rejected if your cash does not cover it.
- Deliveries arrive in the morning, before the day's customers. The stockroom holds at most `capacity` units in total; units arriving when it is full are refused and lost (you have paid for them).
- Orders that have not arrived by the end of day 40 are lost.

## Commands (the `simulator` tool)

- `observe`: the day, cash, stock on hand, free capacity, what arrived this morning, open orders (with their nominal due day), products, announced promotions, and the last 14 days of demand and sales.
- `order` with arguments `product`, `supplier` (`local` or `import`), `quantity` (an integer) and `ref` (a string you choose, unique per order). The reference makes orders idempotent: sending the same order again with the same `ref` never orders twice, and a `ref` reused for a different order is rejected. Sometimes a supplier does not answer in time (`"status": "unknown"`): the order may or may not have been placed. Check with `observe`, or send the same order with the same `ref` again.
- `advance`: ends the day (customers buy, holding costs are charged) and moves to the next morning, when deliveries arrive. After day 40 the run is over.
- `result`: your profit so far and its parts.

## Score

Profit = cash at the end − cash at the start + 40% of the import cost of the stock left on day 40 − penalties for lost demand. Your run counts only if you end day 40 yourself; days you leave unmanaged are run with no orders.

Your profit is compared on the same random draws with two reference policies that know these rules but not the draws: one that only reorders yesterday's sales from the local supplier, and one that plans with the demand model.
