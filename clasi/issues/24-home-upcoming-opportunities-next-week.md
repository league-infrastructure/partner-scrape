---
status: pending
---

# Home page: "Upcoming Opportunities" should show the entire next week

On the home page (`site/src/pages/index.astro`), the "Upcoming
Opportunities" section should display **all** opportunities occurring in the
**next 7 days** (today through one week out) — the entirety of the next
week, not just a capped handful.

## Do
- Select opportunities whose next occurrence / `date_start` falls within
  today .. today+7 days (inclusive), and render all of them in the
  section (sorted by date ascending, matching the Opportunities list).
- No arbitrary "top N" cap for that window — show the whole week. If the
  layout needs a bound, prefer scroll or a "see all" link to the full
  Opportunities page rather than silently dropping events.
- Undated opportunities are excluded from this section (they have no week).

## Notes
- `date_start` is already the next-upcoming occurrence for recurring events
  (post issue-005 collapse fix), so week-window filtering is straightforward.
- Ties into the home-page rebuild [[22-home-page-from-sdstemecosystem.md]];
  build this section as part of / alongside that work.
- Applies to both beta (`partner-scrape/site`) and production
  (`stem-ecosystem`).
