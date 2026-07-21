---
id: '002'
title: Calendar view for the Opportunities page
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: 16-calendar-view.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Calendar view for the Opportunities page

## Description

Implements issue `16-calendar-view.md` and sprint 007's SUC-002. See
sprint.md's Architecture (Calendar View, Opportunities Index Page,
Client-side Filter Engine — Step 3 module table and the component
diagram) and Design Rationale for full context.

**Problem**: `site/src/pages/opportunities/index.astro` only offers
List and Map views via its `.view-toggle` (`data-view="grid"` /
`data-view="map"` buttons, an inline page script, and a hidden
`#map-container`). There is no way to browse by date, even though
every opportunity carries a `date_start`.

**Approach**:

1. Add a Calendar view — a new Astro component (e.g.
   `site/src/components/CalendarView.astro`) that, at build time, reads
   `opportunities.json` (same import already used by `index.astro`) and
   renders a month grid for the current month plus the next two months
   (~3 months total). Each dated opportunity renders on its day as
   compact time + title, linking to `${base}/opportunities/${slug}`
   (same `base`-prefixing pattern already used elsewhere, e.g.
   `OpportunityCard.astro`'s `href`). Undated opportunities
   (`date_start` falsy) are simply omitted — they remain List-only, per
   today's behavior for undated records.
   - Recurring opportunities are already collapsed to their
     next-upcoming occurrence by Normalize & Dedup
     (`partner_scrape/normalize/collapse.py`'s `_span()`, per the
     issue-005 fix) — `date_start` is already the right date to place
     each opportunity on; no client-side recurrence logic is needed.
   - Navigation between the 3 pre-rendered months can be simple
     prev/next buttons toggling which month block is visible
     (client-side show/hide of 3 pre-rendered blocks is simplest and
     avoids any new build-time routing). No navigation is required past
     the 3-month window (sprint.md Open Question 4) — that's an
     explicitly accepted limitation, not a bug.
   - No calendar-library dependency — hand-roll the month grid (plain
     HTML/CSS), matching the site's "no heavy calendar dependency,
     strict CSP" constraint.
   - **Important**: give each calendar day-entry the *same* `data-*`
     filter attributes `OpportunityCard.astro` gives its cards
     (`data-type`, `data-age`, `data-areas`, `data-cost`, `data-time`,
     `data-financial`, `data-ngss`, `data-attention`, `data-title`,
     `data-desc`) — this is how step 3 below keeps Calendar in sync
     with the filter sidebar without a second filtering mechanism.
2. Wire `site/src/pages/opportunities/index.astro`: add a third toggle
   button (`<button data-view="calendar">Calendar</button>`, between
   List and Map, so the toggle reads List · Calendar · Map) and a
   `#calendar-container` div (`style="display:none;"` by default,
   matching `#map-container`'s existing pattern), rendering
   `<CalendarView opportunities={sorted} />` inside it. Extend the
   existing inline toggle script's click handler with a third branch
   that shows `#calendar-container` and hides the other two — mirror
   the existing `if (btn.dataset.view === 'map') {...} else {...}`
   structure with a proper 3-way branch instead of a binary one.
3. Extend `site/src/scripts/filters.js` so Calendar's entries are
   filtered the same way cards are, **without corrupting the
   `"Showing X of Y"` counter** (sprint.md Design Rationale — this is a
   real risk caught during architecture review, not optional
   polish):
   - Extract the existing per-card matching logic inside
     `applyFilters()`'s `cards.forEach(...)` loop into a small shared
     predicate function, e.g. `matchesFilters(el, activeFilters,
     searchTerm)`, that takes one element and returns `true`/`false`.
   - Keep the existing `cards` query and the `results-count` update
     exactly as they are today — scoped to the card grid (e.g. change
     `document.querySelectorAll('[data-type]')` to something scoped to
     `#results-grid`, such as `document.querySelectorAll('#results-grid [data-type]')`,
     so a page-wide `[data-type]` selector doesn't also sweep up
     Calendar's entries and inflate the count).
   - Add a second, separately-scoped query for calendar entries (e.g.
     `document.querySelectorAll('#calendar-container [data-type]')`)
     and apply the same `matchesFilters` predicate to show/hide them —
     same `data-hidden` attribute convention cards already use — but
     **do not** fold this second node list into `cards.length` or
     `visibleCount`.
   - Call this second pass from the same places `applyFilters()` is
     already called (checkbox change, search input, clear buttons,
     `restoreFromURL()`), so Calendar always reflects the same filter
     state List does.

**Files**:
- New: `site/src/components/CalendarView.astro` (or equivalent name)
- Modify: `site/src/pages/opportunities/index.astro`
- Modify: `site/src/scripts/filters.js`

**Out of scope** (per sprint.md Scope): any calendar-library
dependency, external CDN/font, or runtime network fetch; navigation
past the pre-rendered 3-month window; promoting to production
`stem-ecosystem`.

## Acceptance Criteria

- [x] The `.view-toggle` reads List · Calendar · Map; clicking each
      button shows only that view's container.
- [x] Calendar renders a month grid starting at the current month, with
      the next two months (~3 total) reachable via in-page navigation.
- [x] Each dated opportunity appears on its `date_start` day as
      compact time + title, and clicking it navigates to
      `/opportunities/{slug}`.
- [x] An opportunity with no `date_start` never appears on the
      calendar (List view is unaffected either way).
- [x] Applying a sidebar filter (any checkbox group or the search box)
      changes which entries the calendar shows, matching what List
      would show for the same filter state.
- [x] The `"Showing X of Y"` count (visible in List view) is
      **unaffected** by Calendar being open or by Calendar's entries —
      it continues to reflect only the card grid's count, verified by
      comparing the count before and after Calendar markup is added to
      the DOM.
- [x] `npm run build` (in `site/`) succeeds.

## Testing

- **Existing tests to run**: none exist in `site/` — no JS test
  framework (`package.json` has no `test` script). Verification is
  `npm run build` plus the manual/behavioral checks above.
- **New tests to write**: none required (no framework to add tests
  to). Manually verify the filter-sync and counter-scoping behavior
  directly in a built/previewed page (`npm run preview`) since this is
  exactly the kind of DOM-interaction behavior a build success alone
  won't catch.
- **Verification command**: `npm run build` (run from `site/`).
- **Documentation**: none required beyond in-file comments on the new
  `matchesFilters` extraction in `filters.js`, explaining why the
  card-count query and the calendar-entry query are kept separate
  (reference this ticket / sprint.md's Design Rationale so a future
  editor doesn't "simplify" them back into one shared query).
