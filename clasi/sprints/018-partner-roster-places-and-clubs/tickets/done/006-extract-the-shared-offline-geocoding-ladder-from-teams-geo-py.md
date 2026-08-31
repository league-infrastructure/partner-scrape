---
id: '006'
title: Extract the shared offline geocoding ladder from teams/geo.py
status: done
use-cases:
- SUC-004
- SUC-005
depends-on: []
github-issue: ''
issue: 35-standing-entities-clubs-and-places.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Extract the shared offline geocoding ladder from teams/geo.py

## Description

Foundation ticket for issue 35's `directory/` module (tickets 007,
008). Places and Clubs need the same offline, "never guess" geocoding
precision ladder `teams/geo.py` already implements (zip-centroid,
city-centroid, and — for school-based clubs like Hack Club chapters —
the CDE/NCES school-matching rung). Per sprint.md's Design Rationale,
`directory/` must not depend on `teams/geo.py` directly (a
semantically backwards dependency: a general-purpose directory feature
depending on a robotics-competition-specific module) and must not
duplicate the ladder's logic (it has real, hard-won bug-fix history —
e.g. the fuzzy school-name matching and the "never guess" rung's exact
behavior are not trivial to re-derive correctly).

Extract the general-purpose rungs of `teams/geo.py`'s seven-rung ladder
into a new shared module (e.g. `partner_scrape/geo_ladder.py` — exact
name and API left to implementation, but it must be a module neither
`teams/` nor `directory/` is a submodule of, so both can depend on it
without an inversion). `teams/geo.py` becomes a thin wrapper: it calls
the shared ladder for the general-purpose rungs and layers
`Team`-specific behavior (setting `organization_website` from a
CDE-matched school's own record) on top, without changing any of
`Team`'s existing field semantics.

**This ticket's own output is invisible** — no new directory yet, no
new site page. Its only deliverable is the refactor plus proof that it
changed nothing observable about `teams/`'s existing behavior. Tickets
007/008 are the first real callers of the new shared module.

## Acceptance Criteria

- [x] A new shared module exists, exposing the general-purpose rungs
      (zip-centroid, city-centroid, "never guess" rung-7 honesty rule)
      as functions callable independent of `Team`.
- [x] `teams/geo.py`'s public API (`geocode_teams()` or equivalent) is
      unchanged in signature and behavior — every existing caller
      (`teams/pipeline.py`) works with zero changes.
- [x] Every existing `teams/` test passes unmodified against the
      refactored `teams/geo.py`.
- [x] A new regression test proves **byte-identical** `Team` geocoding
      output (latitude, longitude, `location_precision`,
      `matched_name`, `needs_review`, `organization_website`) for a
      representative fixture set, comparing pre-refactor and
      post-refactor runs — not just "still passes," but demonstrably
      unchanged.
- [x] The shared module has no import of anything under `teams/` (the
      dependency direction is `teams/geo.py → shared module`, never
      the reverse, and `directory/` will depend on the same shared
      module without touching `teams/` at all).
- [x] Full test suite stays green (this ticket's own regression test
      plus the full 1652-test baseline).

## Testing

- **Existing tests to run**: the full `teams/` test suite
  (`tests/teams/test_geo.py` and any other `teams/geo.py`-dependent
  tests) plus `uv run pytest` for the whole repo.
- **New tests to write**: the byte-identical-output regression test
  described above; unit tests for the shared module's own functions
  (zip/city centroid lookup, the "never guess" rule) independent of
  `Team`.
- **Verification command**: `uv run pytest`.

## Implementation Plan

**Approach**: Careful refactor-in-place, not a rewrite. Move code, do
not change behavior. Write the byte-identical regression test *before*
moving code (capture current output on the fixture set), then refactor
and confirm the captured output still matches.

**Files to create/modify**:
- New shared module (e.g. `partner_scrape/geo_ladder.py`).
- `partner_scrape/teams/geo.py` — thinned to a wrapper.
- `tests/` — new regression test plus relocated/new unit tests for the
  shared module.

**Testing plan**: see Testing above.

**Documentation updates**: `teams/DESIGN.md`'s existing description of
the seven-rung ladder should note the extraction and point at the new
shared module's own docstring for the general-purpose rungs, rather
than duplicating that description in two places.
