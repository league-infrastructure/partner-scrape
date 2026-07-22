---
id: '001'
title: 'Calendar polish: suppress midnight time, separate today from its chips'
status: open
use-cases: [SUC-001]
depends-on: []
github-issue: ''
issue:
- 17-calendar-suppress-midnight-time.md
- 23-calendar-today-cell-blends-with-entries.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Calendar polish: suppress midnight time, separate today from its chips

## Description

Two independent, low-risk fixes to the Calendar view (`site/src/pages/opportunities/index.astro`'s
Calendar branch, rendered by `CalendarView.astro`), grouped into one ticket because they touch
the same component/CSS:

- **Issue 17**: events whose `date_start` has no real scraped time (a bare date, stored as
  `...T00:00:00`, optionally with a timezone offset like `...T00:00:00-07:00`) render on the
  calendar with a misleading `"12:00 AM"` label next to the title. `CalendarView.astro`'s
  `formatTime()` currently formats every `date_start` unconditionally.
- **Issue 23**: `global.css`'s `.calendar-day.today` and `.cal-entry` both use the exact same
  `var(--purple-light)` background, so today's cell — highlight, entry chips, and the 2px
  inter-entry gap — all render the same color and merge into one solid block, including the
  empty space below the last entry (rows are sized to the busiest day).

See `sprint.md` Architecture > Step 3 ("Calendar View", "Global Stylesheet — Calendar section")
and Use Cases > SUC-001 for full context.

## Implementation Plan

### Approach

- **Issue 17**: add a helper (in `CalendarView.astro` itself, alongside the existing `formatTime()`/
  `dayKey()` functions — this is presentation logic scoped to the calendar, not a general-purpose
  `helpers.ts` addition) that detects the no-real-time case and returns `null`/`''` (render no time
  span) or `"All day"` instead of a formatted time. Detect midnight in the *intended local
  wall-clock* time — the same convention `dayKey()` already uses for bucketing events by day —
  not naive UTC, since a bare date can carry `_TZ_OFFSET` (`-07:00`, see
  `partner_scrape/normalize/run.py`). A `Date` constructed from an ISO string with an explicit
  offset already reflects that offset when queried with `getHours()`/`getMinutes()` in the
  browser's local time only if the browser's local time *is* that offset — do not assume this;
  compare against the offset in the source string directly (e.g. regex-check for a literal
  `T00:00:00` immediately followed by nothing, `Z`, or a `±HH:MM` offset) rather than trusting
  `Date` object hour/minute getters, which are TZ-dependent on the client running the build.
- **Issue 23**: change `.calendar-day.today` to a border/outline-forward treatment (e.g. a
  stronger `border-color` plus a *much* lighter tint, or a top accent bar) that is visually
  distinct from `.cal-entry`'s `var(--purple-light)` fill — do not reuse the exact same CSS
  custom property value for both. Additionally give `.cal-entry` its own subtle border (or a
  slightly stronger/different fill) so entries stay visually separated from *any* cell
  background, not just today's — this generalizes the fix instead of special-casing today's
  cell alone, per issue 23's own "Fix direction" notes.
- Exact color/border values are an implementation detail left to this ticket (not pinned in
  sprint.md) — pick values that read clearly in both light and dark rendering the site already
  supports, if any (check `global.css` for existing dark-mode handling before introducing new
  hardcoded colors).

### Files to Modify

- `site/src/components/CalendarView.astro` — no-real-time detection + entry-time rendering.
- `site/src/styles/global.css` — `.calendar-day.today`, `.cal-entry` (and neighboring calendar
  rules as needed for the border/tint treatment).

### Testing Plan

- No JS test framework exists in `site/` (`package.json` has no `test` script) — behavioral
  verification is manual/visual plus a successful build.
- Manually verify: an opportunity with a bare `date_start` (no real time) shows no "12:00 AM";
  an opportunity with a real scraped time is unaffected; today's cell is visually distinct from
  its chips; a different day with multiple chips still shows clearly separated chips.
- `uv run pytest` is unaffected (no Python files touched) — not required evidence for this
  ticket, but should still pass if run.

### Documentation Updates

None required — this is a self-contained component/CSS fix with no external documentation
referencing the current time-display or today-cell behavior.

## Acceptance Criteria

- [ ] A bare-date opportunity's calendar entry shows no "12:00 AM" (time is omitted or replaced
      with "All day").
- [ ] The no-time detection is correct for both a naive bare date and one carrying a timezone
      offset (e.g. `...T00:00:00-07:00`), using the intended local wall-clock day/time —
      consistent with `dayKey()`'s existing day-bucketing convention.
- [ ] A timed opportunity's calendar entry is unaffected (still shows its real time).
- [ ] Today's `.calendar-day` is visually distinguishable from its own `.cal-entry` chips at a
      glance (not one solid-color block).
- [ ] Event chips are visually separated from each other and from the cell background on every
      day, not just today.
- [ ] `npm run build` succeeds.

## Testing

- **Existing tests to run**: none (no JS test framework in `site/`); `uv run pytest` unaffected.
- **New tests to write**: none applicable (no test framework); acceptance is verified by manual
  visual check plus a successful build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
