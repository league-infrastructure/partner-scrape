---
id: '002'
title: Curate and register CyberPatriot teams roster
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

# Curate and register CyberPatriot teams roster

## Description

Research and curate a starter roster of San Diego-area CyberPatriot
teams (cyber-defense competition teams, typically hosted by a high
school's JROTC unit or CS/cyber program), then register it against the
`Club` model via the generalized `club_static_roster` source (ticket
001).

Issue 35b names a partial starting point, not a complete list: Del
Norte High School and Scripps Ranch High School, both cited as
CyberPatriot national finalists. Live-verify both against a current,
citable public source (AFA CyberPatriot's own results/finalist
announcements, a school's own press page, or comparable) before
recording them — do not transcribe the issue's own wording as if
already verified. Then search for additional San Diego County
CyberPatriot teams with a live, currently-published public record (a
regional/state finalist list, a school's own program page naming its
CyberPatriot team) — this is genuine content research, not a
speculative list. If no source beyond the two named finalists can be
live-verified, that is an acceptable, honestly-documented outcome; do
not pad the roster with unverified guesses.

Ordered second-to-first in this sprint's ticket sequence (after the
foundation ticket) because CyberPatriot is judged the club type most
likely to have a findable public roster — national/regional finalist
announcements are typically public and citable.

## Acceptance Criteria

- [x] `directory/data/cyberpatriot-sd.tsv` exists, following
      `hack-club-sd.tsv`'s exact column shape (`club_id`, `name`,
      `club_type`, `host_school`, `city`, `postal_code`, `website`,
      `meeting_note`, `status`, `status_note`), with `club_type =
      "cyberpatriot"`.
- [x] Del Norte HS and Scripps Ranch HS are present, each live-verified
      against a current public source (cite the source in the ticket's
      own notes, e.g. an implementation-plan "Sources checked" list).
- [x] Any additional team included is likewise live-verified against a
      current, citable public source — no team is added on the strength
      of the issue text alone.
- [x] `directory/registry/cyberpatriot-sd.toml` registers the roster
      with `adapter_type = "club_static_roster"` and the correct
      `roster_path`.
- [x] A `directory` dry-run (or equivalent test) confirms each entry
      parses and geocodes; since CyberPatriot teams are school-hosted,
      each entry is expected to resolve at `"school"` precision through
      the shared ladder's rungs 1-4 — any entry that instead falls to
      `"zip"`/`"city"`/`"none"`, or resolves with `needs_review = true`,
      is flagged honestly in the ticket's notes, not silently accepted
      or force-corrected.
- [x] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [x] The new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [x] Full hermetic test suite passes; no test reaches a live network
      call (live verification happens during ticket research, not
      inside a test).

## Implementation Plan

**Approach**: Live web research first (WebFetch/WebSearch against
AFA CyberPatriot's own site and school program pages), recording each
finding's source URL before writing any TSV row. Curate the TSV, add
the registry entry, then dry-run `directory` locally to inspect
geocoding output before finalizing.

**Files to create/modify**:
- `partner_scrape/directory/data/cyberpatriot-sd.tsv` (new)
- `partner_scrape/directory/registry/cyberpatriot-sd.toml` (new)

**Testing plan**: Reuse ticket 001's generalized `club_static_roster`
parsing tests as a pattern — add a small fixture-based parsing test for
this roster only if the data reveals a genuinely new shape (unlikely,
per sprint.md's Test Strategy); otherwise rely on the existing
registry-loader and dataset-validity coverage. No live network in any
test — `dangerouslyDisableSandbox: true` is for this ticket's own
research Bash calls, not for anything committed to the test suite.

**Documentation updates**: A short note in `directory/DESIGN.md`'s
existing "populated club types" status line (or a new Revision
paragraph, following ticket 001's precedent) recording the CyberPatriot
roster's size and any `needs_review` flags — mirroring
`directory/DESIGN.md`'s existing per-chapter Hack Club table style.


## Notes (implementation)

**Sources checked** (live-verified 2026-09-02):

- Del Norte High School: CyberPatriot XV Open Division National
  Champion ("CyberAegis Tempest," March 2023) and CyberPatriot XVI
  Open Division runner-up/third place ("CyberAegis
  Triton"/"CyberAegis Aegir," 2024) -- per AFA's own CyberPatriot
  XV/XVI announcement pages (afa.org) and Poway Unified School
  District's own news article
  (powayusd.com/apps/news/article/1784912). The program brands itself
  "CyberAegis San Diego" (cyberaegis.tech), spanning Oak Valley Middle
  School, Design39Campus, and Del Norte High School (its flagship
  school). Not found among CyberPatriot 18's (current season,
  concluded March 2026) national finalists per AFA's own CP18 finalist
  announcement -- recorded on its multi-season finalist/champion
  history, not a current-season placement. Flagged in DESIGN.md for a
  future recheck.
- Scripps Ranch High School: CyberPatriot 18 (2025-2026 season,
  concluded March 2026) All Service Division **National Champion**,
  Air Force JROTC "Terabyte Falcons" team -- per AFA's own CyberPatriot
  18 national finalist announcement (afa.org), the most current season
  available.
- Canyon Crest Academy (additional team found via live research, not
  named in the issue): CyberPatriot 18 Open Division national finalist
  (team ":3") -- per AFA's own CP18 finalist announcement, San
  Dieguito Union High School District's own social posts, and the
  team's own site (sites.google.com/view/cca-cyberpatriot/).

Also found but deliberately **not** included: Scouting America
Exploring Posts 2927/2928 (San Diego-based CP18 finalists,
"CyberAegis Hydra"/"Perseus"/"Corvus") -- excluded because they are
Scouting Explorer posts, not school-hosted clubs with one confidently
locatable meeting site, unlike this roster's three school-hosted
entries.

**Geocoding**: all three entries resolve at `"school"` precision
(rung-2 exact CDE match against `sd-schools-public.tsv`),
`needs_review = False` for all three. No entry fell to zip/city/none.

**Adjacent test fix required to keep the suite green**: adding a
second `club_static_roster` registry entry broke two pre-existing
test helpers that assumed exactly one such entry existed
(`test_club_dataset_validity.py`'s and
`test_sources_club_static_roster.py`'s `_real_clubs()`/
`_real_source_config()`, both scoped by bare `adapter_type ==
"club_static_roster"`) -- fixed to scope by `source_id ==
"hack-club-sd"` instead, since both files test the Hack Club roster
specifically. `test_pipeline.py`'s full-registry `clubs_meta.total`
assertions (pinned at `4`) updated to `7` (4 Hack Club + 3
CyberPatriot), matching the real registry's new content. See
`directory/DESIGN.md`'s sprint 032 ticket 002 Revision for the full
writeup.
