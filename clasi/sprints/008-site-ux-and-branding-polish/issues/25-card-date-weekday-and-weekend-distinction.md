---
status: in-progress
sprint: 008
tickets:
- 008-002
---

# Event card date: include day of week + distinguish weekdays from weekends

On the opportunity card, show the **day of the week** as part of the date
(e.g. "Wed, Jul 22" instead of just "Jul 22"), and give **weekends a
subtle but visible visual distinction** from weekdays so they're easy to
scan for.

## Where
- `site/src/lib/helpers.ts` — `formatDate()` builds the card date string
  (used by `OpportunityCard.astro`'s `.opp-card-date`). Add the weekday to
  the formatted output.
- `site/src/components/OpportunityCard.astro` — `.opp-card-date` span.

## Do
- Prepend the abbreviated weekday to the date (Mon–Sun).
- Mark weekend dates (Sat/Sun) so CSS can style them distinctly — e.g. a
  `data-weekend="true"` attribute or a `.weekend` class on the date element
  — then apply a **subtle but visible** treatment (e.g. a slightly different
  color/weight or a small accent), not a loud one.
- Keep it correct for timezone-bearing values (`...T17:00:00-07:00`) — use
  the intended local wall-clock day, consistent with how the calendar
  buckets days.

## Notes
- Undated opportunities: no weekday shown (unchanged).
- Consider applying the same weekday treatment on the detail page date for
  consistency.
- Applies to both beta (`partner-scrape/site`) and production
  (`stem-ecosystem`).
