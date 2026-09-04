---
id: '001'
title: Generalize Team/League and add the generic team_static_roster source
status: done
use-cases:
- SUC-068
depends-on: []
github-issue: ''
issue: 47-generalize-teams-and-narrow-clubs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Generalize Team/League and add the generic team_static_roster source

## Description

`Team` (`partner_scrape/teams/model.py`) is currently robotics-only:
`League = Literal["FTC", "FRC", "FLL", "VEX"]`, with no `get_args()`-
derived `VALID_LEAGUES` frozenset (unlike `Club.ClubType`'s
`VALID_CLUB_TYPES`) because every existing source hands `league` a
single hard-coded literal it controls itself. This ticket lands the
model generalization sprint 036 depends on before any migration or new
data can happen: widen `League`, add `VALID_LEAGUES`, and add a new
teams-side generic curated static-roster source
(`team_static_roster.py`) mirroring `directory/sources/
club_static_roster.py`'s already-proven generalized shape (sprint 032)
rather than further overloading FLL's bespoke `static_roster.py`,
which carries real FLL-specific dirt (`_parse_area`, the
`Family/Community` sentinel, `PROGRAM_BY_RAW`) that a Science
Olympiad/CyberPatriot roster does not need. See sprint.md's
Architecture (Design Rationale) for the full alternatives-considered
writeup on both decisions this ticket implements.

This ticket adds the *mechanism* only — no new registry entries or
roster data files (ticket 002 migrates the first real content through
it).

## Acceptance Criteria

- [x] `teams/model.py`: `League` widens to include `"SCIOLY"` and
      `"CYBERPATRIOT"` (ticket 002's two migrated types); a new
      `VALID_LEAGUES: frozenset[str] = frozenset(get_args(League))` is
      added, matching `VALID_CLUB_TYPES`'s/`VALID_CATEGORIES`'s
      derivation pattern exactly.
- [x] No existing `Team` field changes shape or is added/removed;
      `TEAMS_SCHEMA_FIELDS` (derived from `dataclasses.fields(Team)`)
      is unchanged.
- [x] `teams/sources/team_static_roster.py` (new) implements the
      `TeamSource` protocol: `discover()`/`fetch()` read a committed
      TSV off disk exactly like `club_static_roster.py`'s
      `discover()`/`fetch()` (never calling the injected `Fetcher`);
      `extract()` builds one `Team` per row from `league`, `program`,
      `number`, `name`, `organization`, `org_type`, `city`,
      `postal_code`, `website` columns, validating `league` against
      the new `VALID_LEAGUES` (raising/skip-and-log per malformed row,
      matching `club_static_roster.py`'s `_extract_one` convention
      exactly) and stamping `Team.sources` from the registering
      `SourceConfig.source_id`, never a hard-coded literal.
- [x] Document, in this module's own docstring, that for a competition
      type with no official team-numbering registry, `number` holds a
      stable school-name slug instead of a sanctioned numeric
      designator, and `team_id = f"{league.lower()}-{number}"` is built
      identically to every other source (collision-free because school
      names are unique within one curated roster) — mirrors
      `Club.club_id`'s slug convention and the sprint-016 precedent of
      widening `number`'s semantics.
- [x] `teams/pipeline.py`'s `_TEAM_SOURCES` gains a
      `"team_static_roster": TeamStaticRosterSource()` entry. No change
      to `_SOURCE_LEAGUES`, `_check_sunset_seasons`, or any other
      pipeline stage's sequencing.
- [x] `teams/DESIGN.md` updated: document the widened `League`
      vocabulary's rationale (see sprint.md's Design Rationale for the
      content to transcribe) and the new source module's place in
      `teams/sources/`, alongside the existing four.
- [x] `tests/teams/test_sources_base.py`'s forbidden-import scan (no
      module under `teams/sources/` may import `adapters.base`) passes
      for the new module unmodified — no special-casing needed, the
      scan already covers every file in the package.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` in full;
  `tests/teams/test_model.py`, `tests/teams/test_export.py`,
  `tests/teams/test_pipeline.py` specifically (no regression to any
  existing FTC/FRC/FLL/VEX fixture or `TEAMS_SCHEMA_FIELDS`
  assertion).
- **New tests to write**:
  - `tests/teams/test_model.py`: `VALID_LEAGUES` contains exactly the
    widened value set; no existing `League`/`Team` field assertion
    changes.
  - `tests/teams/test_sources_team_static_roster.py` (new), mirroring
    `tests/directory/test_sources_club_static_roster.py`'s shape:
    `TestNeverTouchesFetcher` (a `Fetcher` double that raises on any
    call), per-row validation/skip-and-log for a malformed
    `league`/missing `number`/`name`, and `TestProvenance` (two
    registry entries with different `source_id`s produce
    distinguishable `Team.sources`).
  - `tests/teams/test_pipeline.py`: a fixture registry entry with
    `adapter_type = "team_static_roster"` dispatches correctly and
    participates in `merge_teams()`/`geocode_teams()` unchanged.
- **Verification command**: `uv run pytest`
