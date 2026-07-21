# Don't show past dates: recurring events display their first-ever occurrence

**Reported by stakeholder (Eric), 2026-07-20, from the live beta.**

A bunch of events look like they're in the past. Root cause found: they're
recurring/ongoing series that are correctly still active, but the card
shows the WRONG date.

- The export keeps an event when `date_end >= today` — correct for a
  weekly class or monthly program that started months ago and still runs.
- But `normalize/collapse.py` sets the collapsed record's `date_start` to
  the **first-ever** occurrence, and the site displays `date_start`. So an
  ongoing weekly program shows e.g. `2025-04-25` or `2026-02-15` — looks
  like a past event.

Diagnosed: 14 of 246 opportunities have `date_start` before today; **all
14** have `date_end` in the future (ongoing), 0 are genuinely past. Examples:
"Astrophotography Workshop" start 2025-04-25 (ends 2026-10-03), "Overnight
Adventure @ USS Midway" start 2026-02-07 (ends 2026-08-22).

## Fix (data side — best UX)
- `normalize/collapse.py`: set a collapsed recurring record's `date_start`
  to the **next upcoming occurrence** (earliest instance `>= today`), not
  the first-ever. Keep `date_end` = last occurrence. Needs `today` injected
  (keep it testable). Update the "Repeats N times through <end>"
  availability to reflect remaining count if easy.
- Single, non-recurring ongoing programs (exhibit runs like "Under the Sea
  I SPY", Jun–Aug) that have a past `date_start` but future `date_end`:
  clamp the effective displayed start to today ("available now") so no card
  ever shows a past date.

Net: nothing on the site should display a date earlier than today.
Applies to both beta and production.
