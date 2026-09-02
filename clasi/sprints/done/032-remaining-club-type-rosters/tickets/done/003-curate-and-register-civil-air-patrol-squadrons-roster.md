---
id: '003'
title: Curate and register Civil Air Patrol squadrons roster
status: done
use-cases:
- SUC-062
depends-on:
- '001'
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

- [x] `directory/data/civil-air-patrol-sd.tsv` exists, following
      `hack-club-sd.tsv`'s exact column shape, with `club_type =
      "civil-air-patrol"`.
- [x] Squadron 144, Squadron 201, and Group 8 are present, each
      live-verified against CAP's own current public unit
      locator/directory (cite the source in the ticket's own notes).
- [x] Any additional San Diego-area squadron found via the same live
      unit locator is likewise live-verified before inclusion.
- [x] `directory/registry/civil-air-patrol-sd.toml` registers the roster
      with `adapter_type = "club_static_roster"` and the correct
      `roster_path`.
- [x] A `directory` dry-run confirms each entry parses; geocoding
      outcomes (expected to land mostly at `"zip"`/`"city"` precision,
      per the Description's Geocoding note) are recorded honestly in the
      ticket's own notes, not force-corrected toward a "school" match.
- [x] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [x] The new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [x] Full hermetic test suite passes; no test reaches a live network
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


## Notes (implementation)

**Sources checked** (live-verified 2026-09-02): California Wing's own
Group 8 "Find a Squadron" locator
(group8ca.cap.gov/join-cap/find-a-squadron) names six subordinate
squadrons; each squadron's own *.cap.gov site gives its current
meeting address, confirmed individually:

- Group 8 HQ: group8ca.cap.gov/about/about-group-8,
  group8ca.cap.gov/about/contact-us -- administrative headquarters,
  4231 Balboa Ave #3040, San Diego, CA 92117.
- Squadron 144 (San Diego Cadet Squadron 144): sq144.cap.gov/contact-us
  -- meets at the CA Air National Guard base, 7288 Convoy Terrace, San
  Diego, CA 92111.
- Squadron 201 (South San Diego Cadet Squadron 201):
  southsandiego.cap.gov/about/about-us -- meets at VFW Post 2111, 299 I
  St, Chula Vista, CA 91910.
- Squadron 47 (Skyhawk Composite Squadron 47): skyhawks.cap.gov --
  meets at McClellan-Palomar Airport, 2206 Palomar Airport Rd,
  Carlsbad, CA 92011.
- Squadron 57 (San Diego Senior Squadron 57): sq57.cap.gov -- meets at
  Gillespie Field, 1960 Joe Crosson Dr, El Cajon, CA 92020.
- Squadron 87 (Fallbrook Senior Squadron 87): fallbrook.cap.gov --
  meets at the "Scout Shack," 231 East Hawthorne St, Fallbrook, CA
  92028 (near Fallbrook Airpark).
- Squadron 714 (Escondido Cadet Squadron 714): escondido.cap.gov --
  meets in Classroom F-203, 1868 E Valley Pkwy, Escondido, CA 92027 --
  this address is Escondido Charter High School's own campus.

Issue 35b named Squadrons 144, 201, and Group 8 as a starting point --
all three found and verified. Four more squadrons were found via the
same live Group 8 locator and each individually verified before
inclusion, per the AC's "any additional squadron... likewise
live-verified" requirement.

**Geocoding outcome**: six of seven entries (Group 8 HQ, 144, 201, 47,
57, 87) fall through honestly to `"zip"` precision as predicted by the
ticket's own Geocoding note -- none needed `needs_review`. One
exception: Squadron 714 genuinely meets on Escondido Charter High
School's own campus, so it correctly resolves at `"school"` precision
via the shared ladder's exact CDE match (`needs_review = False`) -- an
honest match on the real data, not forced and not suppressed.

**Adjacent test fixes required to keep the suite green**: two
pre-existing tests hard-coded "every real Club is school-hosted," true
only while every registered club type happened to be school-hosted
(true for Hack Club + ticket 002's CyberPatriot, false once this
ticket's mostly-non-school CAP roster registers):
`test_pipeline.py`'s renamed
`test_every_real_school_hosted_club_resolves_to_school_precision_never_a_guess`
now scopes to `club_type in {"hack-club", "cyberpatriot"}`, and
`test_club_dataset_validity.py`'s
`TestRealPipelineGeocodingResolvesEveryChapterHonestly._real_geocoded_clubs()`
now scopes to `club_type == "hack-club"` (matching that module's own
documented scope). A new `TestRealCivilAirPatrolGeocoding` class in
`test_pipeline.py` pins the real CAP roster's own mixed zip/school
outcome end-to-end. Full-registry `clubs_meta.total` assertions in
`test_pipeline.py` updated from `7` to `14` (4 Hack Club + 3
CyberPatriot + 7 Civil Air Patrol). See `directory/DESIGN.md`'s sprint
032 ticket 003 Revision for the full writeup.
