---
id: '007'
title: Curate and register Girls Who Code clubs roster
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

# Curate and register Girls Who Code clubs roster

## Description

Research and curate a starter roster of San Diego-area Girls Who Code
(GWC) clubs, then register it against the `Club` model via the
generalized `club_static_roster` source (ticket 001).

Live-verify candidate clubs against Girls Who Code's own official club
locator/directory. GWC's official "Find a Club" tool is
application/login-gated for prospective members in many regions and
does not always expose a public, scrapable San Diego-area list — this
is a real possibility this ticket must test for directly, not assume
away. If a genuinely public, citable listing (the official locator, a
host school/library's own page naming its GWC club, a GWC regional
partner's public page) yields confirmed San Diego-area clubs,
live-verify and curate them. If it does not, record that as an honest,
documented finding — per this sprint's own calibration (a club type
whose curated list doesn't publicly exist is a finding, not something
to force) — rather than fabricating entries or scraping a login-gated
tool.

Ordered last (sixth of six) in this sprint's ticket sequence: GWC's
club-discovery mechanism is judged the least likely of the six to
expose a public, live-scrapable-by-hand roster, based on the program's
typical application-gated locator design — this ticket's own research
is what actually confirms or refutes that expectation for San Diego
specifically.

## Acceptance Criteria

- [x] `directory/data/girls-who-code-sd.tsv` exists (possibly with zero
      rows, per the Description's honest-finding allowance), following
      `hack-club-sd.tsv`'s exact column shape, with `club_type =
      "girls-who-code"`.
- [x] Every club actually included is live-verified against a genuinely
      public, citable source — never a login-gated locator result
      transcribed as if public, and never a guess.
- [x] If no public San Diego-area GWC listing can be confirmed, the
      ticket records that finding explicitly (what was checked, what
      was found gated/unavailable) rather than leaving the gap
      unexplained.
- [x] `directory/registry/girls-who-code-sd.toml` registers the roster
      (if non-empty) with `adapter_type = "club_static_roster"` and the
      correct `roster_path`.
- [x] A `directory` dry-run confirms any entries parse and geocode; no
      assumption of a particular precision (GWC clubs may be
      school-hosted, library-hosted, or org-hosted).
- [x] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [x] Any new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [x] Full hermetic test suite passes; no test reaches a live network
      call.

## Implementation Plan

**Approach**: Start with Girls Who Code's own official club
locator/directory and test directly whether it exposes a public,
scrapable-by-hand San Diego-area result (not an automated scrape — a
human/agent live-checking the page, per this sprint's "no live
scraping" design boundary, same as every other ticket in this sprint).
If gated or empty, check one or two corroborating public sources (a
library or school's own page naming its GWC club) before concluding
none is confirmable. Curate the TSV only for genuinely confirmed,
publicly-sourced clubs.

**Files to create/modify**:
- `partner_scrape/directory/data/girls-who-code-sd.tsv` (new, possibly
  empty/near-empty — see Acceptance Criteria)
- `partner_scrape/directory/registry/girls-who-code-sd.toml` (new, only
  if the roster is non-empty)

**Testing plan**: Reuse the generalized `club_static_roster` parsing
tests as a pattern; rely on existing registry-loader and
dataset-validity coverage. No live network in any test.

**Documentation updates**: A short note in `directory/DESIGN.md`
recording either the curated roster or the honest "no public San Diego
listing found" finding, matching this module's own "record absence,
don't force-include" convention. If this ticket is the sprint's last to
land, this note should also update `directory/DESIGN.md`'s top-level
status line to reflect the sprint's final state across all six club
types (which are populated, which are honest zero-result findings).

## Notes (implementation)

**Sources checked** (live-verified 2026-09-02), in the order this
ticket's Description prescribes:

1. GWC's own official club locator (girlswhocode.com/locations),
   directly tested per this ticket's own instruction not to assume the
   gate away — returns **HTTP 404**. No public, browsable San
   Diego-area listing exists there today, confirming this ticket's own
   "least likely of the six" framing for San Diego specifically.
2. San Diego Public Library's GWC programming — real (a named
   coordinator, Melissa Giffen, and multiple historical event
   listings), but not independently confirmable live: the events
   platform every past listing lived on
   (sandiego.librarymarket.com) is now fully decommissioned (every page
   returns "404 - Unknown site," confirmed via direct `curl`,
   bypassing that domain's own broken TLS cert), the library's new
   events platform (sandiego.events.mylibrary.digital) blocks
   automated fetches (403), and the one specific branch search results
   named (Scripps Miramar Ranch Library) is itself currently closed
   (reopening Winter 2026) per the City of San Diego's own library
   locations page. Deliberately **not** included as a roster entry —
   recorded here instead as a real but currently-unverifiable lead,
   per this ticket's own "never a guess" standard.
3. Canyon Crest Academy's Girls Who Code club — confirmed via CCA
   ASB's own current school-published approved-clubs roster (a Google
   Sheet CCA ASB's own club-list page links live today; exported and
   searched directly): "Girls Who Code" is a School Sponsored club,
   meeting Weekly-Thursdays-Lunch-F101, with a `@sduhsd.net`
   district-email faculty advisor and a named student president. One
   honest caveat: the sheet's own internal tab is titled "Approved
   Clubs 2024-2025" even though CCA ASB's own page frames this same
   linked sheet as "the 2025-2026... List... out now" — by this
   ticket's live-verification date the 2026-2027 school year has
   already begun, so this is the most current school-published list
   found, not necessarily a same-week-current one.

A targeted search for GWC clubs at several other well-known San Diego
high schools (Torrey Pines, Scripps Ranch, Del Norte, La Jolla High)
found none, consistent with GWC's genuinely small real San Diego
footprint rather than under-searching.

**Geocoding**: the one entry (Canyon Crest Academy, an already
known-good CDE school match from tickets 002 and 006's own rosters)
resolves at `"school"` precision, `needs_review = False`.

**Test-suite addition**: a new `TestRealGirlsWhoCodeGeocoding` class in
`test_pipeline.py` pins the real roster's single school-precision entry
end-to-end. Full-registry `clubs_meta.total` assertions updated from
`56` to `57` (4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea
Cadets + 14 4-H + 24 Science Olympiad + 1 Girls Who Code) — the
sprint's final combined club count. See `directory/DESIGN.md`'s sprint
032 ticket 007 Revision for the full writeup; that same Revision also
updates the module's top-level status line to reflect sprint 032's
completion across all six club types.
