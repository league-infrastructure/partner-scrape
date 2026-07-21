# Add a Calendar view (List / Calendar / Map)

**Reported by stakeholder (Eric), 2026-07-20.**

The Opportunities page has a **List / Map** view toggle today
(`site/src/pages/opportunities/index.astro`, `.view-toggle` buttons). Add
a third view: **Calendar** — so the toggle is **List · Calendar · Map**.

## Calendar view spec
- A month-grid calendar starting with the **current month**.
- Show ~**3 months into the future** (current + next 2, navigable).
- Each event renders on its day as just **time + title** (compact) —
  clicking it goes to the opportunity detail page.
- Uses the same filtered set the List/Map views use (the filter sidebar
  should drive the calendar too).
- For recurring events, place them on their **upcoming occurrence date(s)**
  within the window (depends on issue 005's next-occurrence fix; at minimum
  place on `date_start`).

## Notes
- The map view is already wired via the `.view-toggle` + a hidden
  `#map-container`; add a `data-view="calendar"` button and a
  `#calendar-container` following the same show/hide pattern in the page's
  inline script.
- Build calendar from `opportunities.json` at build time (static), or in
  the client script from the already-rendered card data. A lightweight
  hand-rolled month grid is fine — no heavy calendar dependency needed.
- Applies to both beta and production; keep components in sync when
  promoting.
