---
id: '003'
title: Drop map and markers for unmappable opportunities
status: done
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: 20-drop-map-when-no-address.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Drop map and markers for unmappable opportunities

## Description

Issue 20: when an opportunity has no usable location (null/blank latitude/longitude, or the
`(0, 0)` case), no map or marker should render for it — neither an empty/placeholder map on the
detail page nor a marker on the Opportunities Map view.

Codebase-alignment finding from planning (see `sprint.md` Architecture > Design Rationale, "map/
marker omission uses one shared 'is this opportunity mappable' predicate"): both current checks
have the same latent gap — they treat the string `"0"` as a valid, truthy coordinate:

- `site/src/pages/opportunities/[slug].astro`'s `hasLocation = opp.latitude && opp.longitude &&
  !isNaN(parseFloat(opp.latitude))` — `"0"` is a non-empty string (truthy) and `parseFloat("0")`
  is `0`, not `NaN`, so `hasLocation` is `true` for `(0, 0)`.
- `site/src/pages/opportunities/index.astro`'s Map-view marker loop checks `isNaN(lat) ||
  isNaN(lng)` only — same gap, no `(0, 0)` exclusion.

Fix both by introducing and using one shared predicate, rather than patching each check
separately (which would leave two independently-drifting definitions of "mappable").

## Implementation Plan

### Approach

- Add a small pure function to `site/src/lib/helpers.ts`, e.g. `isMappable(lat, lng)`, that
  returns `false` for: missing/empty/non-numeric latitude or longitude, `NaN` after parsing, or
  both values equal to `0`. Returns `true` otherwise.
- `[slug].astro`: replace the current `hasLocation` expression with a call to `isMappable(opp.latitude,
  opp.longitude)`; when `false`, omit the `.detail-mini-map` element entirely (not just hide it —
  no empty/placeholder map should render, and no `#detail-map` id should exist for the inline
  `<script>` to find, avoiding a wasted Leaflet load for an opportunity with nothing to plot).
- `opportunities/index.astro`: in the Map view's marker-plotting loop (inside `initMap()`), add
  the same `isMappable` check before constructing each `L.circleMarker(...)` — alongside the
  existing `isNaN`/San-Diego-bounding-box checks, not replacing them (those remain valid
  additional filters).
- Consider (per `sprint.md` Open Question 3, left to this ticket) adding a small "Showing N of M
  opportunities with a location" note near the Map view toggle, using the existing `results-count`
  style pattern, so it's clear some results aren't plotted rather than looking like a
  silently-incomplete map. This is a nice-to-have, not a hard acceptance requirement (see
  Acceptance Criteria below).
- List and Calendar views are unaffected — they don't filter on location today and shouldn't
  start.

### Files to Modify

- `site/src/lib/helpers.ts` — new `isMappable()` predicate.
- `site/src/pages/opportunities/[slug].astro` — detail-page map section, gated by `isMappable`.
- `site/src/pages/opportunities/index.astro` — Map-view marker loop, gated by `isMappable`
  (optionally, the "N of M shown on map" note).

### Testing Plan

- No JS test framework in `site/`; verify manually against real data: find (or temporarily
  construct) a record with null lat/long and confirm no map section/marker; find a record with
  `latitude`/`longitude` both `"0"` and confirm the same; confirm a normally-located opportunity's
  map/marker is unaffected; confirm List/Calendar views still show the unmappable opportunity.
- `uv run pytest` unaffected (no Python files touched).

### Documentation Updates

None required.

## Acceptance Criteria

- [x] Detail page omits the map section entirely (no empty/placeholder map, no `#detail-map`
      element) when an opportunity has no real location — verified against a record with null
      lat/long and one with `(0, 0)`.
- [x] Map view plots no marker for an unmappable opportunity (null lat/long or `(0, 0)`).
- [x] A mappable opportunity's detail-page map and Map-view marker are unaffected.
- [x] List and Calendar views still show unmappable opportunities (unchanged).
- [x] `npm run build` succeeds.

## Testing

- **Existing tests to run**: none (no JS test framework); `uv run pytest` unaffected.
- **New tests to write**: none applicable; verified by manual check against real records plus a
  successful build, per the sprint's Test Strategy.
- **Verification command**: `npm run build`
