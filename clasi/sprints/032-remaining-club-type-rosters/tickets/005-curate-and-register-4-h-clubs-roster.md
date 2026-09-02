---
id: '005'
title: Curate and register 4-H clubs roster
status: open
use-cases: [SUC-062]
depends-on: ['001']
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

- [ ] `directory/data/4-h-sd.tsv` exists, following `hack-club-sd.tsv`'s
      exact column shape, with `club_type = "4-h"`.
- [ ] Every club included is live-verified against UC ANR's own current
      San Diego County 4-H club listing (cite the source in the
      ticket's own notes).
- [ ] The roster spans, where the county's own listing supports it, more
      than one program area named in issue 35b (robotics, drones, AI,
      animal science) — not force-balanced if the county's real data
      skews toward one area.
- [ ] `directory/registry/4-h-sd.toml` registers the roster with
      `adapter_type = "club_static_roster"` and the correct
      `roster_path`.
- [ ] A `directory` dry-run confirms each entry parses; geocoding
      outcomes are recorded honestly per-entry (see Geocoding note
      above) — no assumption that every club is school-hosted.
- [ ] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [ ] The new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [ ] Full hermetic test suite passes; no test reaches a live network
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
