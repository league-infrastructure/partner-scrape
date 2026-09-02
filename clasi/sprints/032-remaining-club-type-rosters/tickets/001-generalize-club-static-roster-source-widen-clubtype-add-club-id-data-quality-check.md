---
id: '001'
title: Generalize club static-roster source, widen ClubType, add club_id data-quality
  check
status: done
use-cases:
- SUC-061
depends-on: []
github-issue: ''
issue: 35b-standing-entities-remaining-club-rosters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Generalize club static-roster source, widen ClubType, add club_id data-quality check

## Description

Foundation ticket for sprint 032. No content population — this ticket
makes the existing `directory/` module able to accept curated rosters
for any club type, not just Hack Club, so tickets 002-007 can each
register one new club type without touching Python code. See
`sprint.md`'s Architecture section for the full rationale (Scope
Correction + Design Rationale) and `partner_scrape/directory/DESIGN.md`
§5's Open Question this ticket resolves.

Three changes, landed together:

1. **Widen `ClubType`** in `partner_scrape/directory/model.py` from
   `Literal["hack-club"]` to `Literal["hack-club", "cyberpatriot",
   "science-olympiad", "4-h", "girls-who-code", "civil-air-patrol",
   "sea-cadets"]`. `VALID_CLUB_TYPES` is already derived via
   `get_args()` — no further change needed there. No new field, no new
   dataclass.
2. **Generalize the static-roster source.** Rename
   `partner_scrape/directory/sources/hack_club_static_roster.py` to
   `club_static_roster.py`, its class `HackClubStaticRosterSource` to
   `ClubStaticRosterSource`. The module's logic is already generic
   (`_extract_one()` reads `club_type`/`status` from each TSV row and
   validates against the model's own `VALID_CLUB_TYPES`/
   `VALID_CLUB_STATUSES`) — only naming and defaults are Hack-Club-specific
   today. Make `SOURCE_NAME` per-registry-entry: read it from
   `SourceConfig.source_id` (each registry entry already has a unique
   `source_id`) instead of one hard-coded module-level constant, so a
   CyberPatriot roster's `Club.sources` provenance never reads
   `"hack_club_static_roster"`. `DEFAULT_ROSTER_PATH`'s hard-coded
   fallback to `hack-club-sd.tsv` may stay (it only applies when a
   registry entry omits `roster_path`, which every new entry will set
   explicitly) or be removed if simpler — implementor's judgment, not
   load-bearing.
3. **Update the one existing registry entry and the pipeline dispatch
   table together**: `directory/pipeline.py`'s `_CLUB_SOURCES` dict key
   changes from `"hack_club_static_roster"` to `"club_static_roster"`;
   `directory/registry/hack-club-sd.toml`'s `adapter_type` field changes
   to match, in this same ticket/commit — a partial rename would make
   `run_directory()` silently drop the Hack Club registry entry with a
   "no ClubSource registered" warning.
4. **Add data-quality coverage**: extend
   `tests/directory/test_dataset_validity.py` with a `Club`-side
   `club_id`-uniqueness/non-blank check, mirroring the existing
   Place-only `TestUniqueIds` class exactly (same shape, run against the
   accumulated `Club` list rather than `Place`). This guards every
   subsequent ticket's new `club_id`s, including across different TSV
   files.

Also update `partner_scrape/directory/DESIGN.md` with a short Revision
paragraph documenting the rename/generalization (mirroring this
document's own sprint-030 Revision precedent) — this is the canonical
architecture doc for the module; `sprint.md`'s Architecture section is
this sprint's pointer into it, not a replacement for it.

## Acceptance Criteria

- [x] `ClubType` (and therefore `VALID_CLUB_TYPES`) includes
      `"hack-club"`, `"cyberpatriot"`, `"science-olympiad"`, `"4-h"`,
      `"girls-who-code"`, `"civil-air-patrol"`, and `"sea-cadets"`.
- [x] `directory/sources/club_static_roster.py` exists with a
      `ClubStaticRosterSource` class; `hack_club_static_roster.py` no
      longer exists (renamed, not duplicated).
- [x] `SOURCE_NAME`/provenance is derived per registry entry (e.g. from
      `SourceConfig.source_id`), not a single hard-coded literal — a
      unit test asserts two different registry entries produce two
      different `Club.sources` values.
- [x] `directory/pipeline.py`'s `_CLUB_SOURCES` table key is
      `"club_static_roster"`; `directory/registry/hack-club-sd.toml`'s
      `adapter_type` is `"club_static_roster"`.
- [x] The four existing Hack Club chapters still parse and geocode
      identically to before the rename: same four `club_id`s, same
      `location_precision` per chapter (University City HS and La Jolla
      HS at rung 2 "school", Helix Charter HS at rung 3 "school" with
      `needs_review = true`, Mater Dei Catholic HS at rung 2 "school"),
      same `host_school_website` population pattern. A regression test
      pins this (re-run the existing Hack Club fixture/dataset test
      suite against the renamed module).
- [x] `tests/directory/test_sources_static_roster.py`'s (or the
      equivalent renamed test module's) `TestNeverTouchesFetcher`
      coverage still passes against the renamed/generalized source.
- [x] A new `Club`-side `club_id` uniqueness/non-blank test exists in
      `tests/directory/test_dataset_validity.py`, structurally mirroring
      `TestUniqueIds` for `Place`.
- [x] `directory/DESIGN.md` carries a Revision paragraph describing the
      rename/generalization, matching the existing Revision-section
      convention (sprint 030's own entry as the template).
- [x] Full hermetic test suite passes (`uv run pytest`); no test reaches
      a live network call.

## Implementation Plan

**Approach**: A mechanical rename + small generalization, not new
machinery. Do the rename first (get all existing Hack Club tests green
under the new name/paths) before widening `ClubType` — that way a test
failure is unambiguously attributable to one change or the other.

**Files to create/modify**:
- `partner_scrape/directory/model.py` — widen `ClubType`.
- `partner_scrape/directory/sources/hack_club_static_roster.py` →
  `partner_scrape/directory/sources/club_static_roster.py` (rename +
  generalize `SOURCE_NAME`).
- `partner_scrape/directory/pipeline.py` — `_CLUB_SOURCES` key and
  import path.
- `partner_scrape/directory/registry/hack-club-sd.toml` — `adapter_type`.
- Corresponding test files under `tests/directory/` — rename/update
  imports, add the new `Club`-side uniqueness test to
  `test_dataset_validity.py`.
- `partner_scrape/directory/DESIGN.md` — Revision paragraph.

**Testing plan**: Run the full existing `tests/directory/` suite after
the rename to confirm zero behavior change for Hack Club before adding
new coverage. Add the `Club`-side uniqueness test and a small
provenance test (two registry entries → two distinct `Club.sources`
values). No live network in any test.

**Documentation updates**: `directory/DESIGN.md` Revision paragraph
(see Description, above). No other module's docs are affected.
