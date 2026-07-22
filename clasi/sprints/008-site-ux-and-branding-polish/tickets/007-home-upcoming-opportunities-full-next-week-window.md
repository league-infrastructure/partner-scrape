---
id: '007'
title: 'Home Upcoming Opportunities: full next-week window'
status: done
use-cases:
- SUC-007
depends-on:
- '006'
github-issue: ''
issue: 24-home-upcoming-opportunities-next-week.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Home Upcoming Opportunities: full next-week window

## Description

Issue 24: the home page's "Upcoming Opportunities" section currently selects the 4 soonest
upcoming opportunities (preferring free ones) via `index.astro`'s `.slice(0, 4)`. Replace this
with: all opportunities whose next occurrence (`date_start`) falls within today .. today+7 days
(inclusive), sorted by date ascending, with no arbitrary top-N cap.

**Depends on ticket 006** — issue 24's own notes tie it to the home-page rebuild ("build this
section as part of / alongside that work"), and this section's final position/styling is decided
by ticket 006's structure. This ticket changes the section's *selection logic*, not its visual
treatment (which ticket 006 already established).

## Implementation Plan

### Approach

- In `index.astro`, replace the current `upcoming` selection (`filter` by `date_start >= now`,
  sort by free-then-date, `.slice(0, 4)`) with a next-7-days window filter: `date_start >= now &&
  date_start <= now + 7 days`, sorted by date ascending (matching how the Opportunities list page
  already sorts — see `opportunities/index.astro`'s `sorted` array — for consistency across the
  site). Drop the "prefer free" sort tiebreak now that there's no cap forcing a choice between
  competing items — ascending date order alone is the natural read for "what's happening this
  week."
- No cap: render every opportunity in the window. If this makes the section visually long,
  prefer a scroll container or a "See all" link to `/opportunities` over silently dropping any —
  per the issue's explicit "no arbitrary top-N cap" requirement. A CSS-only bound (e.g.
  `max-height` + `overflow-y: auto` on the results container) is an acceptable, low-effort choice
  if the section would otherwise get unwieldy; a hard `.slice()` cap is not, regardless of size.
- Undated opportunities remain excluded (unchanged — `date_start` is required to have a "week" to
  belong to).
- `date_start` is already the next-upcoming occurrence for recurring opportunities (sprint 007's
  collapse fix, `partner_scrape/normalize/collapse.py`), so no additional recurrence handling is
  needed here.

### Files to Modify

- `site/src/pages/index.astro` — the `upcoming` selection query and its rendering (this section
  only; hero/cards/other sections belong to ticket 006, already landed).

### Testing Plan

- No JS test framework in `site/`; verify manually against real `opportunities.json` data: every
  opportunity with `date_start` in `[today, today+7d]` appears, sorted ascending; nothing in that
  window is missing; an opportunity just outside the window (day 8+) is correctly excluded.
- `uv run pytest` unaffected (no Python files touched).

### Documentation Updates

None required.

## Acceptance Criteria

- [x] All opportunities with `date_start` in `[today, today+7d]` (inclusive) appear in the
      "Upcoming Opportunities" section, sorted ascending by date.
- [x] No opportunity within that window is dropped for a "top N" cap.
- [x] Undated opportunities remain excluded from this section (unchanged).
- [x] If the section is long, it scrolls or links to the full Opportunities page rather than
      hiding results.
- [x] `npm run build` succeeds.

## Testing

- **Existing tests to run**: none (no JS test framework); `uv run pytest` unaffected.
- **New tests to write**: none applicable; verified by manual check against real exported data
  plus a successful build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
