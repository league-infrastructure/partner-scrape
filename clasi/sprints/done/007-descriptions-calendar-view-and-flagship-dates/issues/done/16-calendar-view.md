---
status: done
sprint: '007'
tickets:
- 007-002
---

# Add a Calendar view (List / Calendar / Map)

The Opportunities page has a **List / Map** view toggle today
(`site/src/pages/opportunities/index.astro`, `.view-toggle` buttons). Add a
third view: **Calendar** — so the toggle is **List · Calendar · Map**.
Reported by the stakeholder.

## Spec
- A month-grid calendar starting with the **current month**.
- Show ~**3 months into the future** (current + next 2, navigable).
- Each event renders on its day as just **time + title** (compact); clicking
  it goes to the opportunity detail page.
- Uses the same filtered set the List/Map views use (the filter sidebar
  drives the calendar too).
- For recurring events, place them on their upcoming occurrence within the
  window; at minimum place on `date_start` (which is now the next-upcoming
  occurrence after the issue-005 collapse fix).

## Implementation notes
- The map view is already wired via `.view-toggle` + a hidden
  `#map-container`; add a `data-view="calendar"` button and a
  `#calendar-container`, following the same show/hide pattern in the page's
  inline script (`site/src/scripts/filters.js` / the page script).
- Build the calendar from `opportunities.json` at build time (static) or in
  the client script from the already-rendered card data. A lightweight
  hand-rolled month grid is fine — no heavy calendar dependency (strict CSP,
  static build).
- Undated opportunities simply don't appear on the calendar (they remain in
  List view).

## Acceptance
- Toggle shows three views; Calendar renders a month grid from the current
  month with ~3 months navigable.
- Events appear on their day showing time + title, linking to detail.
- Filtering the sidebar updates which events show on the calendar.

## Note
Applies to both beta and production; keep components in sync when promoting.
Source: `site/docs/issues/006-calendar-view.md`.
