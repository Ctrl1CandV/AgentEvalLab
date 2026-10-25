## Brief: an operations dashboard for Tidewater Logistics

**Audience.** Dispatchers who watch it all day on a large screen and check it on a laptop; they need to see trouble at a glance.
**Tone.** Calm, dense, precise. Information first; no marketing.

**Content** (`public/content.json`): the brand, the title, the four regions, the KPI labels, the chart title and 24 shipments (id, region, status, ETA, weight).

**The page must**
- show two KPIs: the number of shipments shown (`data-role="kpi-total"`) and how many of them are Delayed (`data-role="kpi-delayed"`), each as a number;
- list the shipments in a table (`data-role="shipments-table"`, one `tbody` row per shipment, showing at least the id, region, status and ETA);
- offer a region filter (`data-role="region-filter"`, a `select` with "All regions" and the four regions): choosing a region shows only its shipments, and both KPIs then count only those;
- show a chart of shipments by status (`data-role="chart"`, an SVG or canvas you draw, at least 200×120 pixels).
