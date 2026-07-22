---
status: in-progress
sprint: 008
tickets:
- 008-001
---

# Calendar view: suppress "12:00 AM" for events with no real scraped time

Surfaced during sprint 007 (ticket 002, calendar view). Events whose
`date_start` is a bare date (scraped as `...T00:00:00`, i.e. no specific
time was available) render on the calendar as **"12:00 AM"** next to the
title. That reads as a real midnight start and is misleading.

## Fix
In `site/src/components/CalendarView.astro` (the `.cal-entry-time` render),
detect the midnight/no-time case and either omit the time entirely (show
just the title) or label it "All day". Consider the same treatment
anywhere else a time is shown for such records (e.g. the card/detail
date-time display) for consistency.

## Notes
- Low priority / polish; the calendar itself works correctly otherwise.
- Beware timezone: the stored value may carry an offset
  (`...T00:00:00-07:00`); decide midnight in the intended local wall-clock,
  matching how the calendar already buckets events by local day.
- Applies to both beta (`partner-scrape/site`) and production
  (`stem-ecosystem`).
