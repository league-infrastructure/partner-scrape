---
id: '004'
title: Curate and register Sea Cadets units roster
status: open
use-cases: [SUC-062]
depends-on: ['001']
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

- [ ] `directory/data/sea-cadets-sd.tsv` exists, following
      `hack-club-sd.tsv`'s exact column shape, with `club_type =
      "sea-cadets"`.
- [ ] Every unit included is live-verified against NSCC's own current
      national unit locator or a comparable official public source (cite
      the source in the ticket's own notes).
- [ ] If no San Diego-area NSCC unit can be live-verified as currently
      active, this ticket records that as an honest finding (no
      fabricated entries) — the ticket's Description in `sprint.md`'s
      SUC-062 already anticipates this possible outcome shape (per
      Hack Club's own Helix Charter precedent for "flag it, don't force
      it").
- [ ] `directory/registry/sea-cadets-sd.toml` registers the roster (if
      non-empty) with `adapter_type = "club_static_roster"` and the
      correct `roster_path`.
- [ ] A `directory` dry-run confirms each entry parses; geocoding
      outcomes are recorded honestly (see Geocoding note above).
- [ ] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [ ] Any new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [ ] Full hermetic test suite passes; no test reaches a live network
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
