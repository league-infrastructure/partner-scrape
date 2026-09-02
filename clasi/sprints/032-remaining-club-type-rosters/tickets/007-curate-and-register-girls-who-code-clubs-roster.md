---
id: '007'
title: Curate and register Girls Who Code clubs roster
status: open
use-cases: [SUC-062]
depends-on: ['001']
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

- [ ] `directory/data/girls-who-code-sd.tsv` exists (possibly with zero
      rows, per the Description's honest-finding allowance), following
      `hack-club-sd.tsv`'s exact column shape, with `club_type =
      "girls-who-code"`.
- [ ] Every club actually included is live-verified against a genuinely
      public, citable source — never a login-gated locator result
      transcribed as if public, and never a guess.
- [ ] If no public San Diego-area GWC listing can be confirmed, the
      ticket records that finding explicitly (what was checked, what
      was found gated/unavailable) rather than leaving the gap
      unexplained.
- [ ] `directory/registry/girls-who-code-sd.toml` registers the roster
      (if non-empty) with `adapter_type = "club_static_roster"` and the
      correct `roster_path`.
- [ ] A `directory` dry-run confirms any entries parse and geocode; no
      assumption of a particular precision (GWC clubs may be
      school-hosted, library-hosted, or org-hosted).
- [ ] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [ ] Any new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [ ] Full hermetic test suite passes; no test reaches a live network
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
