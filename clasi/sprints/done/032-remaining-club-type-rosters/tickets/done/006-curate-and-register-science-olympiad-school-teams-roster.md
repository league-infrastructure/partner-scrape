---
id: '006'
title: Curate and register Science Olympiad school teams roster
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

- [x] `directory/data/science-olympiad-sd.tsv` exists, following
      `hack-club-sd.tsv`'s exact column shape, with `club_type =
      "science-olympiad"`.
- [x] Every team included is live-verified against a current,
      citable public source (a tournament results page, a school's own
      program page) — cite the source(s) in the ticket's own notes.
- [x] If confident, current sources yield only a small handful of teams
      (or none), that is recorded as an honest finding rather than
      padded with unverified guesses — matching this sprint's calibrated
      "a curated list that turns out not to exist publicly should be a
      finding, not forced" expectation.
- [x] `directory/registry/science-olympiad-sd.toml` registers the
      roster (if non-empty) with `adapter_type = "club_static_roster"`
      and the correct `roster_path`.
- [x] A `directory` dry-run confirms each entry parses; geocoding
      outcomes are recorded honestly (expected mostly `"school"`
      precision per the Geocoding note, but not forced if a real entry
      doesn't resolve that way).
- [x] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [x] Any new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [x] Full hermetic test suite passes; no test reaches a live network
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

## Notes (implementation)

**Sources checked** (live-verified 2026-09-02): Duosmium Results'
archived official tournament results for the 2026 San Diego Regional
Science Olympiad Tournament, Division C (high school), held February
28, 2026 at the University of San Diego
(duosmium.org/results/2026-02-28_sCA_san_diego_regional_c/) — this
turned out to be exactly the "competition-results-based" source this
ticket's own Description anticipated, since Science Olympiad indeed
maintains no member directory. All 62 competing teams' host schools
were extracted and deduplicated to 24 unique San Diego County high
schools (several schools fielded multiple named teams, e.g. Canyon
Crest Academy fielded 5 and Scripps Ranch High School fielded 5 — one
`Club` record per school, not per named team, matching this module's
existing one-record-per-organization convention).

Also live-checked: the official regional tournament site
(scilympiad.com/sdso) returned HTTP 200 today, confirming it is
reachable and describes the regional's structure (San Diego + Imperial
County eligibility, three divisions). This updates sprint 029's own
finding that the same URL was unreachable (curl returning 000) at that
earlier time — recorded here per this project's own "record what a
source says today" verification standard, not a contradiction of that
earlier finding.

**Geocoding**: 23 of the 24 entries resolve at `"school"` precision —
Science Olympiad teams are genuinely school-based, matching the
Geocoding note's expectation. One of those 23, San Dieguito High School
Academy, is a legitimate rung-3 same-city fuzzy match (CDE's own record
is "San Dieguito HS Academy") and is correctly flagged `needs_review`
rather than silently trusted — this sprint's second such flag (after
Hack Club's own Helix Charter). One entry, The Preuss School UC San
Diego (a small charter school co-located on the UCSD campus), matches
no CDE/NCES school record at all and falls through honestly to the
ladder's non-school rungs rather than a forced match.

**Test-suite addition**: a new `TestRealScienceOlympiadGeocoding` class
in `test_pipeline.py` pins the real roster's 23-school/1-fallthrough
outcome end-to-end. The existing needs-review test
(`test_helix_charter_is_the_one_real_chapter_flagged_needs_review`) is
renamed to `test_two_real_chapters_are_flagged_needs_review` and
widened to expect both Helix Charter and San Dieguito Academy.
Full-registry `clubs_meta.total` assertions updated from `32` to `56`
(4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea Cadets + 14
4-H + 24 Science Olympiad). See `directory/DESIGN.md`'s sprint 032
ticket 006 Revision for the full writeup.
