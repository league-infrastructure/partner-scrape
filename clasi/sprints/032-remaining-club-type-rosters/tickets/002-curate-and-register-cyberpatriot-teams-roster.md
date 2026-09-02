---
id: '002'
title: Curate and register CyberPatriot teams roster
status: open
use-cases: [SUC-062]
depends-on: ['001']
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

- [ ] `directory/data/cyberpatriot-sd.tsv` exists, following
      `hack-club-sd.tsv`'s exact column shape (`club_id`, `name`,
      `club_type`, `host_school`, `city`, `postal_code`, `website`,
      `meeting_note`, `status`, `status_note`), with `club_type =
      "cyberpatriot"`.
- [ ] Del Norte HS and Scripps Ranch HS are present, each live-verified
      against a current public source (cite the source in the ticket's
      own notes, e.g. an implementation-plan "Sources checked" list).
- [ ] Any additional team included is likewise live-verified against a
      current, citable public source — no team is added on the strength
      of the issue text alone.
- [ ] `directory/registry/cyberpatriot-sd.toml` registers the roster
      with `adapter_type = "club_static_roster"` and the correct
      `roster_path`.
- [ ] A `directory` dry-run (or equivalent test) confirms each entry
      parses and geocodes; since CyberPatriot teams are school-hosted,
      each entry is expected to resolve at `"school"` precision through
      the shared ladder's rungs 1-4 — any entry that instead falls to
      `"zip"`/`"city"`/`"none"`, or resolves with `needs_review = true`,
      is flagged honestly in the ticket's notes, not silently accepted
      or force-corrected.
- [ ] No San Diego Math Circle, SDAA, or VEX-team entry is added.
- [ ] The new `club_id`s pass ticket 001's uniqueness/non-blank check.
- [ ] Full hermetic test suite passes; no test reaches a live network
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
