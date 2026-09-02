---
id: '005'
title: Curate and register 4-H clubs roster
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

# Curate and register 4-H clubs roster

## Description

Research and curate a starter roster of San Diego County 4-H clubs
(issue 35b's own figure: 22+ clubs, spanning robotics/drones/AI and
animal-science programs), then register it against the `Club` model via
the generalized `club_static_roster` source (ticket 001).

Live-verify each club against UC Agriculture and Natural Resources
(UC ANR)'s own San Diego County 4-H program page or club directory —
county 4-H programs are university-extension-run and typically publish
a current club listing. Given issue 35b's own "22+" figure, this ticket
does not need to exhaustively enumerate every club to satisfy Success
Criteria (a "starter roster," per `sprint.md`'s Success Criteria) — but
every club actually included must be live-verified against the county's
own current listing, not copied from a stale or third-party source.

**Geocoding note**: 4-H clubs meet at a mix of locations — some at a
school, many at a community center, grange hall, fairground, or
extension office. Do not assume every entry will resolve at `"school"`
precision; record each entry's actual `location_precision` honestly
(see `sprint.md`'s Architecture "Geocoding note").

Ordered fifth in this sprint's ticket sequence: county 4-H programs are
university-extension-run with a plausible public directory, but the
"22+ clubs across varied program areas" scope makes this more
research-intensive than CyberPatriot/CAP/Sea Cadets' more targeted
lists, so it is sequenced after those.

## Acceptance Criteria

- [x] `directory/data/4-h-sd.tsv` exists, following `hack-club-sd.tsv`'s
      exact column shape, with `club_type = "4-h"`.
- [x] Every club included is live-verified against UC ANR's own current
      San Diego County 4-H club listing (cite the source in the
      ticket's own notes).
- [x] The roster spans, where the county's own listing supports it, more
      than one program area named in issue 35b (robotics, drones, AI,
      animal science) — not force-balanced if the county's real data
      skews toward one area.
- [x] `directory/registry/4-h-sd.toml` registers the roster with
      `adapter_type = "club_static_roster"` and the correct
      `roster_path`.
- [x] A `directory` dry-run confirms each entry parses; geocoding
      outcomes are recorded honestly per-entry (see Geocoding note
      above) — no assumption that every club is school-hosted.
- [x] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [x] The new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [x] Full hermetic test suite passes; no test reaches a live network
      call.

## Implementation Plan

**Approach**: Live web research against UC ANR's San Diego County 4-H
program page/club directory, recording each club's current meeting
location and program focus before writing any TSV row. Curate the TSV,
add the registry entry, dry-run `directory` to inspect the geocoding
outcome.

**Files to create/modify**:
- `partner_scrape/directory/data/4-h-sd.tsv` (new)
- `partner_scrape/directory/registry/4-h-sd.toml` (new)

**Testing plan**: Reuse the generalized `club_static_roster` parsing
tests as a pattern; rely on existing registry-loader and
dataset-validity coverage. No live network in any test.

**Documentation updates**: A short note in `directory/DESIGN.md`
recording the 4-H roster's size, sources checked, and its mixed
geocoding-precision outcome (school vs. zip/city), consistent with the
Geocoding note's expectation.

## Notes (implementation)

**Sources checked** (live-verified 2026-09-02): UC ANR's own San Diego
County 4-H "Community Clubs" directory
(ucanr.edu/site/4-h-san-diego-county/community-clubs), cross-checked
against its four Area sub-pages (Area 1, 2, 4, 5 — Area 3 returns 404,
so it does not exist; the four sub-pages' club lists sum to the same
fourteen clubs the top-level page lists). Fourteen clubs curated, all
confirmed present with a named leader/contact on UC ANR's current page:
Fallbrook, Surfside, Valley Center, Valley Center Country, San
Dieguito, 56 Ranchers, Poway, Ramona Paisanos, Ramona Stars, Ramona
Wranglers, Santa Ysabel/Julian, Manzanita, Sagebrush, and Japatul.

Three clubs have their own public site, live-verified with meeting
location detail: Surfside 4-H (surfside4h.net — Vista Antique Steam
Engine Museum, 2040 N Santa Fe Ave, Vista CA 92083), San Dieguito 4-H
(sandieguito4h.com — Olivenhain Meeting Hall, 620 Melba Rd, Encinitas
CA 92024, first Thursday of the month), and Ramona Stars 4-H
(ramonastars4h.org — meets 2nd Wednesday of the month at the Ramona
Junior Fairgrounds). The other eleven have no independent public site
with a street address, so `host_school` is left blank and only
`city`/`postal_code` (the region's principal town, per UC ANR's own
regional grouping) is recorded — an honest partial-verification signal,
not a guessed address.

**Honest finding on program-area spread**: no San Diego-specific
robotics/drones/AI-branded 4-H club was found. San Diego County 4-H's
own materials describe robotics/STEM as one of "hundreds of projects"
available *within* each general community club, not a separately
branded club. The one "4-H Area14 Robotics Club" search turned up
(4histops.org/area14-robotics-club) is confirmed on live fetch to meet
in Bridgewater Township, **New Jersey** — a different county's 4-H
program sharing the generic "Area 14" name — and is deliberately
excluded. Poway 4-H's own site confirms a real, county-supported
program-area spread (animal science/livestock, STEM/veterinary
science, archery, gardening), and several club names (56 Ranchers,
Ramona Wranglers, Surfside, Sagebrush) suggest the county's real data
leans rural/animal-science, not evenly "force-balanced" across issue
35b's named areas — recorded honestly per this ticket's own AC, not
padded with a fabricated specialty club. `sandiegocounty4h.com` (an
apparent third-party/unofficial domain surfaced in search results) does
not resolve (DNS failure, confirmed via both `WebFetch` and `curl`) and
was not used as a source.

**Geocoding**: all fourteen entries resolve at `"zip"` precision — every
club's zip code is covered by the real, committed `zip-centroids.toml`,
so none falls through further to city precision, and (as expected,
none of these are school-hosted) no school-matching rung ever fires.
`needs_review = False` for all fourteen.

**Test-suite addition**: a new `TestReal4HGeocoding` class in
`test_pipeline.py` (mirroring ticket 004's `TestRealSeaCadetsGeocoding`)
pins the real roster's all-zip-precision outcome end-to-end.
Full-registry `clubs_meta.total` assertions updated from `18` to `32`
(4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea Cadets + 14
4-H). See `directory/DESIGN.md`'s sprint 032 ticket 005 Revision for
the full writeup.
