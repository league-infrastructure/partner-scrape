---
status: in-progress
sprint: 008
tickets:
- 008-001
---

# Calendar: "today" cell blends into one big box (same color as entries)

On the Calendar view, the current day (e.g. Wednesday the 22nd) looks like
one big solid box — the individual event entries lose their separation and
there's a large filled area of empty space at the bottom of the cell. Other
days render fine (distinct entry chips on a white cell).

## Root cause (found)
In `site/src/styles/global.css`, the "today" highlight and the event chips
use the **same background color**:
- `.calendar-day.today { background: var(--purple-light); }`
- `.cal-entry { background: var(--purple-light); }`

So on today's cell, the cell fill and every entry are the same
`--purple-light`. The 2px inter-entry gap shows the cell behind it — also
`--purple-light` — so the chips visually merge into one block, and the
empty space below the last entry (the row is as tall as the busiest day's
cell) is filled with the same purple → the "big empty box" look.

## Fix direction
Make the "today" indicator distinguishable from the entry chips, e.g.:
- Give `.calendar-day.today` a **border / outline** (or a top accent bar)
  instead of a full-cell background fill; or
- Use a **much lighter tint** for the today cell than the entry chips; and/or
- Give `.cal-entry` a subtle border or slightly stronger fill so chips stay
  visually separate on any cell background.

## Notes
- Also reconsider the empty-space-at-bottom generally: grid rows size to the
  busiest day, so light days have trailing empty space — fine when it's
  white, jarring when it's a filled highlight. A border-only "today" fixes
  the worst of it.
- Related: [[17-calendar-suppress-midnight-time]] (same Calendar view).
- Applies to both beta (`partner-scrape/site`) and production
  (`stem-ecosystem`).
