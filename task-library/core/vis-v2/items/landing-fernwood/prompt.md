## Brief: a landing page for Fernwood

**Audience.** Hikers and climbers aged 25–55 who buy fewer, better things.
**Tone.** Earthy, honest, quietly confident. Think workshop, not billboard.

**Content** (`public/content.json`): the hero, three products, the newsletter block and the footer. Use the copy exactly.

**The page must**
- open with the hero (`data-role="hero"`) carrying the heading and subheading;
- show the three products, each in an element with `data-role="product-card"` (name, price, description);
- have a newsletter form (`data-role="newsletter-form"`) with an "Email" field and an "Interest" select whose options are exactly Hiking, Climbing and Camping (a placeholder option with an empty value is allowed), and a subscribe button;
- on submit, an email that is not a full address (it needs a name, an "@", a domain and a dot in it) shows the error message in `data-role="form-error"` and never the success message; a valid one shows the success message in `data-role="form-success"`.
