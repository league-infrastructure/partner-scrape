---
id: 009
title: Site directory pages for places and clubs
status: open
use-cases:
- SUC-004
- SUC-005
depends-on:
- '007'
- '008'
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

- [ ] `site/src/pages/places/index.astro` renders every entry in
      `places.json`, grouped/filterable by category.
- [ ] `site/src/pages/clubs/index.astro` renders every entry in
      `clubs.json` without assuming club types beyond what's actually
      present.
- [ ] Neither page uses "upcoming"/"past" framing inherited from the
      Opportunities pages — both are standing, undated directories.
- [ ] If either page renders a map, an entry outside `SD_BOUNDS` is
      visibly flagged or included with a note, never silently dropped.
- [ ] Both pages follow `teams/index.astro`'s existing conventions
      (styling, layout, badge/list patterns) closely enough that they
      read as part of the same site, not a bespoke one-off design.
- [ ] Full test suite stays green (if the Astro site has its own test/
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
