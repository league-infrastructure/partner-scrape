---
id: '006'
title: Curate and register Science Olympiad school teams roster
status: open
use-cases: [SUC-062]
depends-on: ['001']
github-issue: ''
issue: 35b-standing-entities-remaining-club-rosters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Curate and register Science Olympiad school teams roster

## Description

Research and curate a starter roster of San Diego-area Science Olympiad
school teams, then register it against the `Club` model via the
generalized `club_static_roster` source (ticket 001).

Issue 35b names no specific starting teams. Live-verify candidate teams
against California Science Olympiad's own regional/state
tournament results or a comparable official source (a school's own
program page naming an active Science Olympiad team, corroborated by a
tournament roster where possible) — Science Olympiad does not maintain
a single public "member directory" the way a locator-based program
does, so this ticket's research needs a competition-results-based
approach rather than a simple directory lookup.

**Geocoding note**: unlike Civil Air Patrol/Sea Cadets/most 4-H clubs,
Science Olympiad teams are explicitly school-based (issue 35b's own
phrasing: "school teams") — expect most entries to resolve at
`"school"` precision through the shared ladder's rungs 1-4, similar to
Hack Club and CyberPatriot.

Ordered fifth-of-six (second-to-last) in this sprint's ticket sequence:
school-based teams are geocodable the same way Hack Club/CyberPatriot
are, but Science Olympiad's lack of a single public roster/locator
(competition-results research instead) makes finding a citable, current
list more effortful than the CyberPatriot/CAP/Sea Cadets tickets, so it
is judged less likely to yield a full result on the first pass.

## Acceptance Criteria

- [ ] `directory/data/science-olympiad-sd.tsv` exists, following
      `hack-club-sd.tsv`'s exact column shape, with `club_type =
      "science-olympiad"`.
- [ ] Every team included is live-verified against a current,
      citable public source (a tournament results page, a school's own
      program page) — cite the source(s) in the ticket's own notes.
- [ ] If confident, current sources yield only a small handful of teams
      (or none), that is recorded as an honest finding rather than
      padded with unverified guesses — matching this sprint's calibrated
      "a curated list that turns out not to exist publicly should be a
      finding, not forced" expectation.
- [ ] `directory/registry/science-olympiad-sd.toml` registers the
      roster (if non-empty) with `adapter_type = "club_static_roster"`
      and the correct `roster_path`.
- [ ] A `directory` dry-run confirms each entry parses; geocoding
      outcomes are recorded honestly (expected mostly `"school"`
      precision per the Geocoding note, but not forced if a real entry
      doesn't resolve that way).
- [ ] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [ ] Any new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [ ] Full hermetic test suite passes; no test reaches a live network
      call.

## Implementation Plan

**Approach**: Live web research against California Science Olympiad's
own regional/state tournament results pages and individual San Diego
high/middle schools' own program pages, cross-checking each candidate
before inclusion. Curate the TSV only for genuinely confirmed teams.

**Files to create/modify**:
- `partner_scrape/directory/data/science-olympiad-sd.tsv` (new, possibly
  small if research yields few confirmed teams — see Acceptance
  Criteria)
- `partner_scrape/directory/registry/science-olympiad-sd.toml` (new,
  only if the roster is non-empty)

**Testing plan**: Reuse the generalized `club_static_roster` parsing
tests as a pattern; rely on existing registry-loader and
dataset-validity coverage. No live network in any test.

**Documentation updates**: A short note in `directory/DESIGN.md`
recording the roster's size, sources checked, and whether the "no
single public directory" constraint limited coverage — an honest
finding, not a gap to hide.
