# Task: Visual Design (VIS v2)

Design and build the static web page the brief below describes, for a fictional product. The brief fixes the product, the copy and data (in `public/content.json`), what the page must do, and the hooks the checks use; the visual design is yours, and it is what is compared.

## Deliverable

- A static site in `site/`: `site/index.html`, with any CSS, JavaScript, images (SVG or data URIs) and fonts you write yourself inside `site/`. No external requests: no CDNs, web fonts or images from the network (the page is opened from its files, offline).
- Use the copy and data in `public/content.json` exactly; do not rewrite it. Decorative microcopy may be added.
- Put the `data-role` attributes the brief lists on the elements it names: the checks find elements by them. Everything else (structure, classes, styling) is yours.

## How it is judged

- **Function** (checked by script in headless Chromium, at 1440×900 and 390×844): the page loads without script errors, the listed roles are present, nothing scrolls horizontally at either width, every form control has a label, and the behaviours the brief lists work exactly as stated.
- **Design**: screenshots of your page are compared, in pairs, with other pages for the same brief, by judges who see only the screenshots and the brief. They weigh hierarchy, typography, spacing, colour, consistency and fitness for the brief's audience.

Accessibility counts in both: text contrast of at least 4.5:1 (3:1 for large text), visible keyboard focus, labelled controls, targets of at least 24×24 CSS pixels for primary controls.

End with a short summary of your design decisions.
