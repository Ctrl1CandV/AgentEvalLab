## Brief: a pricing page for Quanta

**Audience.** Owners of small firms comparing accounting tools; sceptical, busy, on desktop.
**Tone.** Crisp, trustworthy, modern finance without coldness.

**Content** (`public/content.json`): the hero, the billing labels and note, three plans with monthly prices and features, the currency and the call to action.

**The page must**
- show the three plans, each in an element with `data-role="plan-card"`, with its price in an element with `data-role="plan-price"` (the number, with the currency sign if you like);
- start on monthly prices; a billing toggle (`data-role="billing-toggle"`, a button or a switch) switches to yearly prices, which are the monthly price × 10 (the yearly note explains why), and back.
