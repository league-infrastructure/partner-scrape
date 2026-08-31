---
id: 008
title: Clubs data model and Hack Club chapters proof of concept
status: in-progress
use-cases:
- SUC-005
depends-on:
- '006'
- '007'
github-issue: ''
issue: 35-standing-entities-clubs-and-places.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Clubs data model and Hack Club chapters proof of concept

## Description

Add the `Club` model to `partner_scrape/directory/` (built by ticket
007) and populate it with exactly one club type: Hack Club chapters —
the only type issue 35 already cites a ready curated source for
(`finder.hackclub.com`'s static list). Every other club type named in
the original issue (CyberPatriot, Science Olympiad, 4-H, Girls Who
Code, Civil Air Patrol, Sea Cadets) is out of scope, split to issue
35b for a future sprint (sprint.md's Design Rationale explains why:
each needs its own curated-list research pass this sprint has no room
for alongside issues 32 and 43).

**`Club` model**: a separate flat dataclass from `Place` (not a shared
base — sprint.md's Design Rationale), fields covering: name,
organization type or program (Hack Club specifically — kept general
enough that issue 35b's future club types fit without a model change),
host school/organization where applicable, location fields + the
shared geo-ladder's precision/never-guess outputs (ticket 006,
including the school-matching rung, since Hack Club chapters are
school-hosted), website/social where the chapter has its own, and a
`sources` provenance field.

**Hack Club static-roster source**: read a committed, curated file
listing known San Diego chapters — at minimum University City HS, La
Jolla HS, Helix Charter, Mater Dei Catholic (named in issue 35);
research `finder.hackclub.com` for any additional San Diego-area
chapters and include them if found, noting the file's curation date so
staleness is visible later. Same shape as
`teams/sources/static_roster.py`: `fetch()` reads local disk, never
calls the injected `Fetcher`.

**Explicit exclusions** (per sprint.md's Design Rationale, to prevent
future double-registration): San Diego Math Circle and SDAA are single
organizations, not multi-chapter clubs — they belong in the partner
roster (tickets 003/004), not here. VEX teams already arrive via
`teams/sources/robotevents.py` (sprint 016) and are also out of scope
for this ticket.

**Export**: extend `directory/export.py` (built by ticket 007) to also
write `clubs.json`, reusing the same shape/conventions `places.json`
already established. Already covered by ticket 007's
`MIRRORED_DATA_FILES`/`directory` CLI-subcommand wiring — this ticket
adds the data, not new plumbing.

## Acceptance Criteria

- [ ] `directory/` has a `Club` model, structurally separate from
      `Place` (no shared base class).
- [ ] Every Hack Club chapter named in issue 35 (University City HS,
      La Jolla HS, Helix Charter, Mater Dei Catholic) has a `Club`
      record; any additional chapters found via
      `finder.hackclub.com` are included with the same rigor.
- [ ] Each chapter's location precision comes from the shared
      geo-ladder (ticket 006), including a real attempt at the
      school-matching rung for its host school — never a guessed
      coordinate.
- [ ] San Diego Math Circle and SDAA are **not** present as `Club`
      records anywhere in `directory/`'s data.
- [ ] `clubs.json` is written via the same `directory/export.py` and
      `directory` CLI subcommand ticket 007 built, with no new CLI
      surface or mirror-wiring change needed.
- [ ] Full test suite stays green, plus new hermetic tests for the
      `Club` model and the Hack Club static-roster source.

## Testing

- **Existing tests to run**: `uv run pytest`, including ticket 007's
  new `directory/` test suite (this ticket must not regress it).
- **New tests to write**: fixture-based tests for the `Club` model and
  the Hack Club static-roster source, following
  `tests/teams/test_sources_static_roster.py`'s shape (a `Fetcher`
  test double that raises on any call); a test confirming
  `clubs.json`'s shape via `directory/export.py`.
- **Verification command**: `uv run pytest`, plus
  `uv run partner-scrape directory --dry-run -v` to confirm both
  `places.json` and `clubs.json` would be produced together.

## Implementation Plan

**Approach**: Extend the `directory/` package ticket 007 built, adding
the `Club` model and its one populated source. No new CLI/mirror
plumbing — reuse ticket 007's.

**Files to create/modify**:
- `partner_scrape/directory/model.py` (or `clubs.py`) — `Club` dataclass.
- `partner_scrape/directory/sources/hack_club_static_roster.py` (or
  similar) — the curated-file source.
- `partner_scrape/directory/data/hack-club-sd.tsv` (or similar) — the
  committed curated chapter list.
- `partner_scrape/directory/export.py` — extended to also write
  `clubs.json`.
- `tests/directory/...` — new tests.

**Testing plan**: see Testing above.

**Documentation updates**: `directory/DESIGN.md` (created by ticket
007) gets a section on the `Club` model and the Math
Circle/SDAA/VEX exclusions, so a future sprint picking up issue 35b
does not need to re-derive that reasoning.
