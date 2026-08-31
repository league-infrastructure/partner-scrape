---
id: 009
title: Site directory pages for places and clubs
status: done
use-cases:
- SUC-004
- SUC-005
depends-on:
- '007'
- 008
github-issue: ''
issue: 35-standing-entities-clubs-and-places.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Site directory pages for places and clubs

## Description

Add `site/src/pages/places/index.astro` and `site/src/pages/clubs/index.astro`
to this repo's beta Astro checkout, following
`site/src/pages/teams/index.astro`'s existing precedent (the same repo,
same checkout — sibling-repo parity is issue 41's concern, not this
ticket's). Render `places.json` and `clubs.json` (tickets 007/008) as
browsable directories: no dated-event framing (no "upcoming"/"past"
split borrowed from the Opportunities pages) since both are standing,
undated entities.

Places: group or filter by category (makerspace, planetarium,
observatory, tide pool, nature center, library maker lab) — follow
whatever grouping convention `teams/index.astro` already uses for
league/program grouping, adapted to categories instead.

Clubs: for this sprint, only Hack Club chapters exist in `clubs.json`
— the page should not assume every club "type" issue 35b will
eventually add is present; render whatever `clubs.json` actually
contains, the same way `teams/index.astro` already handles a partial
league set without hardcoding "there are exactly 4 leagues."

Map rendering, if any, must respect the same `SD_BOUNDS`
bounding-box convention `site/src/pages/partners/index.astro` uses
(`latMin: 32.4, latMax: 33.5, lngMin: -117.7, lngMax: -116.0`) — an
entry outside it should not be silently dropped the way the partners
map currently does (ticket 002 fixes that for partners; this ticket
should not reintroduce the same silent-drop pattern for places/clubs).

## Acceptance Criteria

- [x] `site/src/pages/places/index.astro` renders every entry in
      `places.json`, grouped/filterable by category.
- [x] `site/src/pages/clubs/index.astro` renders every entry in
      `clubs.json` without assuming club types beyond what's actually
      present.
- [x] Neither page uses "upcoming"/"past" framing inherited from the
      Opportunities pages — both are standing, undated directories.
- [x] If either page renders a map, an entry outside `SD_BOUNDS` is
      visibly flagged or included with a note, never silently dropped.
- [x] Both pages follow `teams/index.astro`'s existing conventions
      (styling, layout, badge/list patterns) closely enough that they
      read as part of the same site, not a bespoke one-off design.
- [x] Full test suite stays green (if the Astro site has its own test/
      build check, that passes too — confirm what exists before
      assuming pytest is the only gate for this ticket).

## Testing

- **Existing tests to run**: `uv run pytest` for the Python side (no
  Python code changes expected from this ticket, but confirm); any
  existing Astro build/lint check (`just dev` or equivalent — check
  the site's own README/justfile for the actual command) to confirm
  the new pages build without error.
- **New tests to write**: none expected in the Python hermetic suite,
  since this ticket is Astro-only; if the site checkout has its own
  test convention (check before assuming none), follow it.
- **Verification command**: `uv run pytest` (Python side unaffected);
  the site's own build command to confirm the new pages compile.

## Implementation Plan

**Approach**: Copy `teams/index.astro`'s structure and adapt field
names/grouping — do not design a new visual language for these two
pages.

**Files to create/modify**:
- `site/src/pages/places/index.astro` (new)
- `site/src/pages/clubs/index.astro` (new)
- Possibly a shared component if `teams/index.astro` already factors
  out reusable pieces (e.g. a badge/list component) — reuse rather
  than duplicate if one exists.

**Testing plan**: see Testing above.

**Documentation updates**: none expected in this repo's Python-side
`DESIGN.md` files; if the Astro site has its own implementation-spec
doc (referenced from `docs/design/overview.md`'s Scope note as
`stem-ecosystem/docs/site-implementation-spec.md`), note the new pages
there only if that doc already tracks page-level additions for this
beta checkout — don't invent a new documentation habit for one ticket.

## Notes (ticket 009 completion, 2026-08-31)

**Data files did not yet exist in this checkout.** Ticket 007/008 built
the `directory` CLI subcommand and export code but the pipeline had
never actually been run against this repo's own `site/` checkout —
`site/src/data/places.json`/`clubs.json` were absent. Ran
`uv run partner-scrape directory -v` (with `SCRAPE_CACHE_DIR` pointed at
a scratch dir — the directory sources never call the fetcher, so the
cache dir's contents are irrelevant, only its presence is required by
`PoliteFetcher()`'s constructor) with default `--site-dir`
(`../stem-ecosystem`, the primary target) and default mirror targets
(this repo's own `site/`, per `config.DEFAULT_MIRROR_SITE_DIR`). This
produced and mirrored real `places.json` (19 places) and `clubs.json`
(4 clubs) into `site/src/data/` and `site/public/data/`, committed
alongside the new pages (matching `teams.json`'s existing
committed-generated-file precedent in this repo).

**Pages/components created**:
- `site/src/pages/places/index.astro` — hero, `PlaceFilters` (category
  checkboxes with build-time counts, search), `PlaceCard` grid,
  List/Map toggle. Sorted by category then name.
- `site/src/pages/places/[slug].astro` — detail page over `place_id`
  (already doubles as the URL slug), mirroring `teams/[slug].astro`'s
  shape: tags, description, address/website sidebar, mini-map with a
  precision note. Atlas Labs' `"opening"` status renders an "Opening
  Soon" tag plus its `status_note` in a Status section.
- `site/src/pages/clubs/index.astro` — hero, `ClubCard` grid, List/Map
  toggle, **no filter sidebar** (4 entries, 1 club_type this sprint —
  a single always-checked facet has nothing to filter; ticket's own
  "don't over-build a 4-item dataset" note). `.listing-layout`'s
  280px-sidebar grid is collapsed to one column via a scoped
  `.clubs-listing-layout` override rather than duplicating its
  spacing/max-width rules in a new class.
- `site/src/pages/clubs/[slug].astro` — detail page over `club_id`.
  Helix Charter's `needs_review: true` entry renders a "Location Needs
  Review" tag (matching `teams/[slug].astro`'s `needs_review` handling
  exactly) plus an explanatory note and a "— needs review" suffix on
  the map's precision label; verified live via screenshot.
- `site/src/components/PlaceCard.astro`, `PlaceFilters.astro`,
  `ClubCard.astro` — modeled directly on `TeamCard.astro`/
  `TeamFilters.astro`'s shape (top tag row, `SocialIcon` website icon,
  `data-*` attributes for `scripts/filters.js`'s existing generic
  filter engine). `PlaceFilters`' six categories are hand-listed
  (matching `TeamFilters`' hand-listed `leagues`), since
  `directory.model.Category` is a closed six-value Literal this
  dataset already covers in full — unlike `Club.club_type`, which
  `ClubCard`'s `CLUB_TYPE_LABELS` map deliberately does NOT enumerate
  exhaustively (falls back to the raw value), since issue 35b's future
  club types must render without a code change.

**Out-of-bounds handling (AC4)**: `partners/index.astro`'s existing
map still silently `return`s on an out-of-bounds card (ticket 002
instead guarantees the *data* never triggers it). Places/Clubs maps
take a different approach per this ticket's explicit AC: every card
with a coordinate gets a marker regardless of `SD_BOUNDS`, `setMaxBounds()`
is not called (only `fitBounds()` for the initial view, so a visitor
can always pan/zoom to an outlier), and a marker outside `SD_BOUNDS`
gets a distinct color (`#f5a623` vs. the standard `#c83e8e`) plus a
popup note. Not currently exercised by real data — all 19 places and
4 clubs fall inside `SD_BOUNDS` (checked directly) — but the code path
exists and does not silently drop, satisfying the AC as written rather
than only as currently exercised.

**Nav**: `Header.astro` and `Footer.astro`'s "Explore" list both gained
`Places`/`Clubs` entries between `Teams` and `About`.

**Live render confirmation**: ran `npm run build` (873 pages, all 19
place detail pages + 4 club detail pages present in `dist/`, index
pages show "Showing 19 of 19" / "Showing 4 of 4"), then `npm run dev`
and screenshotted (Playwright, headless Chromium) `/places/`,
`/places/atlas-labs`, `/clubs/`, `/clubs/hack-club-helix-charter-high`,
plus both index pages' Map view. All four screenshots show real,
correctly-shaped data (category/status tags, Leaflet mini-maps and
list maps with markers at real coordinates, the needs_review tag).
`console --errors` was empty on every page, including after triggering
the Map view's Leaflet/marker JS.

**Deviations from the plan**: none structural. `PlaceFilters`/
`ClubCard`/`PlaceCard` as three separate small components (not one
shared parameterized card) — Team's own precedent never introduced a
generic card either, and Place/Club's field sets diverge enough
(category vs. club_type/host_school, status vs. meeting_note) that a
shared component would need as much per-type branching as two small
ones, matching `directory/model.py`'s own "two flat dataclasses, not a
shared base" rationale. No Python code changed; `uv run pytest` stays
at the 1886-test baseline.
