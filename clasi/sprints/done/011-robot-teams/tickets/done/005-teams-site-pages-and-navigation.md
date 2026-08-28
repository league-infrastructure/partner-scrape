---
id: '005'
title: Teams site pages and navigation
status: done
use-cases:
- SUC-004
depends-on:
- '004'
github-issue: ''
issue: robot-teams-scrape-locate-and-publish-san-diego-first-teams.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Teams site pages and navigation

## Description

Publish the visible `/teams` section — this is the ticket that turns
the pipeline built in tickets 001-004 into the "working, visible
`/teams` page" the sprint is scoped around. Index page with filters and
map, detail pages, and nav entries in both `Header.astro` and
`Footer.astro`. This is the issue's increment 4 and the last ticket in
this sprint (increment 5, FLL, is deferred — see `sprint.md`'s Goals).
Implements SUC-004.

Model `TeamCard.astro` on `OpportunityCard.astro`, **not**
`PartnerCard.astro` — confirmed during sprint planning that
`PartnerCard` wraps its whole card body in one outer `<a>`, so its
`<h3>` has no nested `<a>`, and the existing map script's
`card.querySelector('h3 a')` silently returns `null` (an existing,
live bug on the Partners map: popups fall back to `href="#"`).
`OpportunityCard` nests the title anchor inside `<h3>`
(`<h3><a href={...}>{title}</a></h3>`), so the same map pattern works.
Do not repeat `PartnerCard`'s structure for `TeamCard`.

## Acceptance Criteria

- [x] `site/src/components/TeamCard.astro` — modeled on
      `OpportunityCard.astro`'s structure (title anchor nested inside
      `<h3>`), not `PartnerCard.astro`. Every card carries a `data-type`
      (league/program) attribute so the filter engine
      (`scripts/filters.js`) can see it, matching
      `OpportunityCard`/`PartnerCard`'s existing convention.
- [x] `site/src/components/TeamFilters.astro` — clones
      `OpportunityFilters.astro`'s build-time facet-count pattern,
      faceted by league/program at minimum.
- [x] `site/src/pages/teams/index.astro` — copies
      `partners/index.astro`'s structure, keeping the `#results-grid`,
      `#map-container`, `.results-count`, `.view-toggle` element IDs
      `scripts/filters.js` finds by convention.
- [x] `site/src/pages/teams/[slug].astro` — `getStaticPaths()` over
      `teams.json`; reuses the existing `.detail-page` + mini-map
      pattern from `opportunities/[slug].astro`.
- [x] Map treatment respects `location_precision`: `school`/`zip`
      precision teams render as individual pins; `city` precision teams
      render as **one labelled badge per city** (e.g. "San Diego — 40
      teams"), never a jittered pin and never a plain unlabeled cluster
      marker. Teams with `location_precision: none` are omitted from
      the map but still appear in the list/filter view.
- [x] Every emitted URL goes through `const base =
      import.meta.env.BASE_URL.replace(/\/+$/, '')`, matching every
      existing page's convention.
- [x] "Teams" is added to **both** `Header.astro`'s and
      `Footer.astro`'s hard-coded nav lists (two separate edits — they
      are not shared data).
- [x] `just build`'s `/teams` page count equals the fixture
      `teams.json`'s exported team count.

## Implementation Plan

**Approach**: This ticket is almost entirely "copy an existing
Opportunities-section file, rename, adjust field names" — the
Opportunities section is the closer analog for both the map-anchor
structure (see Description) and the filter/detail-page conventions.
Do not invent new component patterns; deviations from
`OpportunityCard`/`OpportunityFilters`/`opportunities/index.astro`
should be justified by an actual `Team` field difference (e.g.
`location_precision`-aware map rendering has no `Opportunity` analog),
not style preference. Before this ticket can build or test against
real data, run `partner-scrape teams` once (locally, against this
repo's own `site/` checkout) so `site/src/data/teams.json` exists —
`getStaticPaths()` needs it the same way every existing data page needs
its JSON file present at build time (see `sprint.md`'s Migration
Concerns).

**Files to create**:
- `site/src/components/TeamCard.astro`
- `site/src/components/TeamFilters.astro`
- `site/src/pages/teams/index.astro`
- `site/src/pages/teams/[slug].astro`

**Files to modify**:
- `site/src/components/Header.astro` — add the "Teams" nav item.
- `site/src/components/Footer.astro` — add the "Teams" nav item to the
  "Explore" link group.
- `partner_scrape/teams/DESIGN.md` — this subsystem's doc is now
  complete across all four tickets; do a final read-through to confirm
  it describes the whole subsystem as actually built, not as
  originally drafted during sprint planning.

## Documentation

Finalize `partner_scrape/teams/DESIGN.md` (extended incrementally by
tickets 001-004) with the site-pages layer, and run `clasi design
validate` one more time to confirm the doc set is clean. This is also
the point at which the sprint's `design/` overlay
(`clasi/sprints/011-robot-teams/design/`) should be checked for
accuracy against what actually got built, ahead of sprint close
applying it to the canonical docs.

## Testing

- **Existing tests to run**: `uv run pytest`; `just build` for the
  existing site to confirm no regression in Opportunities/Partners
  pages.
- **New tests to write**:
  - A test (Python or a lightweight Astro/Playwright check, matching
    whatever convention `tests/test_site_data_access_page.py`-style
    tests in this repo already use) confirming `/teams` and
    `/teams/<slug>` build successfully against a fixture `teams.json`.
  - A structural check that `TeamCard.astro`'s title anchor is nested
    inside `<h3>` (not wrapping the card), guarding against
    reintroducing the `PartnerCard` map-popup defect.
  - A check that city-precision teams are grouped into per-city badges
    in the map-rendering script, not plotted as individual pins.
- **Verification command**: `uv run pytest && just build`
