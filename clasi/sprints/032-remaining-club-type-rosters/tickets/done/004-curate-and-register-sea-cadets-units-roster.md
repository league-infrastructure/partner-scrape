---
id: '004'
title: Curate and register Sea Cadets units roster
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

# Curate and register Sea Cadets units roster

## Description

Research and curate a starter roster of San Diego-area U.S. Naval Sea
Cadet Corps (NSCC) units, then register it against the `Club` model via
the generalized `club_static_roster` source (ticket 001).

Issue 35b names no specific starting units — this ticket's research
starts from NSCC's own national unit locator to find San Diego-area
units (San Diego's Navy/Marine Corps presence makes a local unit
plausible, but this must be live-verified, not assumed). Live-verify
each unit's current name, training center/meeting location, and
whether it is still active before recording it.

**Geocoding note**: Like Civil Air Patrol squadrons, Sea Cadet units
typically meet at a naval installation, armory, or training center, not
a K-12 school — expect the shared ladder's school-matching rungs (1-4)
to miss and each entry to fall through honestly to zip/city precision
(rungs 5-6), per `sprint.md`'s Architecture "Geocoding note." This is
expected, not a defect.

Ordered fourth in this sprint's ticket sequence, after CyberPatriot and
Civil Air Patrol: NSCC maintains a national unit locator, so a citable
roster is plausible, but San Diego-area coverage (unlike CAP's
issue-35b-named squadrons) is not pre-confirmed and needs this ticket's
own research to establish whether it exists at all.

## Acceptance Criteria

- [x] `directory/data/sea-cadets-sd.tsv` exists, following
      `hack-club-sd.tsv`'s exact column shape, with `club_type =
      "sea-cadets"`.
- [x] Every unit included is live-verified against NSCC's own current
      national unit locator or a comparable official public source (cite
      the source in the ticket's own notes).
- [x] If no San Diego-area NSCC unit can be live-verified as currently
      active, this ticket records that as an honest finding (no
      fabricated entries) — the ticket's Description in `sprint.md`'s
      SUC-062 already anticipates this possible outcome shape (per
      Hack Club's own Helix Charter precedent for "flag it, don't force
      it").
- [x] `directory/registry/sea-cadets-sd.toml` registers the roster (if
      non-empty) with `adapter_type = "club_static_roster"` and the
      correct `roster_path`.
- [x] A `directory` dry-run confirms each entry parses; geocoding
      outcomes are recorded honestly (see Geocoding note above).
- [x] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [x] Any new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [x] Full hermetic test suite passes; no test reaches a live network
      call.

## Implementation Plan

**Approach**: Live web research against NSCC's own national unit
locator first; if that yields no confirmed San Diego-area unit, check
one or two corroborating sources (a unit's own social presence, local
Navy League chapter pages) before concluding none exists. Curate the
TSV only for genuinely confirmed units.

**Files to create/modify**:
- `partner_scrape/directory/data/sea-cadets-sd.tsv` (new, possibly with
  zero or few rows if research finds no confirmed unit — see Acceptance
  Criteria)
- `partner_scrape/directory/registry/sea-cadets-sd.toml` (new, only if
  the roster is non-empty)

**Testing plan**: Reuse the generalized `club_static_roster` parsing
tests as a pattern; rely on existing registry-loader and
dataset-validity coverage. No live network in any test.

**Documentation updates**: A short note in `directory/DESIGN.md`
recording either the curated roster (size, sources checked, expected
geocoding precision) or the honest "no confirmed San Diego-area unit
found as of this ticket" finding, matching this module's own "record
absence, don't force-include" convention (see the Coronado/National
City library precedent in `directory/DESIGN.md`).


## Notes (implementation)

**Sources checked** (live-verified 2026-09-02). Issue 35b named no
starting units for this type -- all four were found via this ticket's
own research, starting from NSCC's own national site and Navy League
San Diego's own current sponsor page:

- Escondido Battalion & Training Ship Kit Carson
  (escondidobattalion.org) -- founded 2011, drills two weekend days a
  month during the school year at Escondido Police & Fire HQ, 1163 N.
  Centre City Pkwy, Escondido, CA 92026. Strongest verification: a
  live, working, currently-maintained unit site.
- Gunfighter Squadron & Training Ship TopGun
  (sites.google.com/site/gunfightertopgun) -- aviation-oriented unit
  formed 1973, based at MCAS Miramar; own site lists an upcoming drill
  dated August 29, 2026, directly confirming current activity.
- Michael A. Monsoor Battalion -- construction-battalion-oriented unit
  at Marine Corps Base Camp Pendleton; confirmed active via a November
  13, 2023 NBC 7 San Diego news report on equipment stolen from the
  unit. No dedicated unit website found; listed on Navy League San
  Diego's own current youth-programs page
  (navyleague-sd.com/sea-cadets/).
- Chief MCM-14 Division -- named for the former mine-countermeasures
  ship USS Chief (MCM-14, now homeported in Japan), based at Naval
  Base San Diego; listed on Navy League San Diego's own current
  youth-programs page. Weakest verification of the four: no
  independent unit website, no dated recent activity found beyond the
  sponsor listing itself.

**Found but deliberately excluded** (honest finding, not a research
gap): Challenger Division / TS Columbia and Coronado Battalion, both
showing clear signs of current inactivity -- Challenger's own domain
(challenger-seacadets.org) no longer resolves (DNS failure), Coronado's
own domain (coronadoseacadets.org) serves a broken TLS certificate, and
independent search results describe on-base Sea Cadet activities at
Naval Amphibious Base Coronado as "currently suspended until further
notice." Not included, per this module's "flag it, don't force it"
convention applied to a whole entry.

**Geocoding**: Escondido Battalion (zip 92026, covered by the real
zip-centroids.toml) resolves at `"zip"` precision. The other three
(Miramar, Camp Pendleton, Naval Base San Diego) have zip codes not
covered by that file, so they fall one rung further to `"city"`
precision (San Diego/Oceanside city centroids) -- a real, non-guessed
ladder rung, not a fabricated coordinate. `needs_review = False` for
all four.

**Test-suite addition**: a new `TestRealSeaCadetsGeocoding` class in
`test_pipeline.py` (mirroring ticket 003's `TestRealCivilAirPatrolGeocoding`)
pins the real roster's mixed zip/city outcome end-to-end.
Full-registry `clubs_meta.total` assertions updated from `14` to `18`
(4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea Cadets). See
`directory/DESIGN.md`'s sprint 032 ticket 004 Revision for the full
writeup.
