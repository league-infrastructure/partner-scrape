---
id: '003'
title: Curate and register Civil Air Patrol squadrons roster
status: open
use-cases: [SUC-062]
depends-on: ['001']
github-issue: ''
issue: 35b-standing-entities-remaining-club-rosters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Curate and register Civil Air Patrol squadrons roster

## Description

Research and curate a starter roster of San Diego-area Civil Air Patrol
(CAP) cadet squadrons, then register it against the `Club` model via
the generalized `club_static_roster` source (ticket 001).

Issue 35b names three specific units as a starting point: Squadron 144,
Squadron 201, and Group 8. Live-verify each against CAP's own current
public unit locator/directory (California Wing's own site, or CAP
National's unit finder) — confirm each still exists, its current
meeting location, and its formal name, rather than transcribing the
issue text as pre-verified.

**Geocoding note**: CAP squadrons typically meet at their own
facilities (an airport hangar, an armory, a community/civic building),
not a K-12 school campus. `Club.host_school` (the field
`_apply_club_geocoding()` passes to the shared ladder) should still
carry whatever organization/location name is available (e.g. the
meeting site's name), but expect the ladder's school-matching rungs
(1-4) to miss for most or all entries — that is the correct, honest
outcome, not a defect (see `sprint.md`'s Architecture "Geocoding note").
Confirm each entry falls through cleanly to a zip/city-precision
coordinate (rungs 5-6) using the squadron's own `city`/`postal_code`,
rather than treating a `"zip"`/`"city"` result as something to chase
into a false "school" match.

Ordered third in this sprint's ticket sequence: CAP is a public,
government-affiliated youth program with an official, typically public
unit locator, so a citable roster is expected to exist, though squadron
meeting locations (not schools) mean the geocoding outcome differs from
CyberPatriot's.

## Acceptance Criteria

- [ ] `directory/data/civil-air-patrol-sd.tsv` exists, following
      `hack-club-sd.tsv`'s exact column shape, with `club_type =
      "civil-air-patrol"`.
- [ ] Squadron 144, Squadron 201, and Group 8 are present, each
      live-verified against CAP's own current public unit
      locator/directory (cite the source in the ticket's own notes).
- [ ] Any additional San Diego-area squadron found via the same live
      unit locator is likewise live-verified before inclusion.
- [ ] `directory/registry/civil-air-patrol-sd.toml` registers the roster
      with `adapter_type = "club_static_roster"` and the correct
      `roster_path`.
- [ ] A `directory` dry-run confirms each entry parses; geocoding
      outcomes (expected to land mostly at `"zip"`/`"city"` precision,
      per the Description's Geocoding note) are recorded honestly in the
      ticket's own notes, not force-corrected toward a "school" match.
- [ ] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [ ] The new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [ ] Full hermetic test suite passes; no test reaches a live network
      call.

## Implementation Plan

**Approach**: Live web research against CAP California Wing's own
squadron locator (and CAP National's, if the Wing site is incomplete),
recording each squadron's current meeting address/city before writing
any TSV row. Curate the TSV, add the registry entry, dry-run
`directory` to inspect the geocoding outcome.

**Files to create/modify**:
- `partner_scrape/directory/data/civil-air-patrol-sd.tsv` (new)
- `partner_scrape/directory/registry/civil-air-patrol-sd.toml` (new)

**Testing plan**: Reuse the generalized `club_static_roster` parsing
tests as a pattern; rely on existing registry-loader and
dataset-validity coverage unless this roster's data reveals a genuinely
new parsing shape. No live network in any test.

**Documentation updates**: A short note in `directory/DESIGN.md`
recording the CAP roster's size, sources checked, and the expected
zip/city-precision geocoding outcome (so a future reader doesn't mistake
it for an oversight).
