---
id: '002'
title: Migrate Science Olympiad and CyberPatriot from Club to Team
status: done
use-cases:
- SUC-069
depends-on:
- '001'
github-issue: ''
issue: 47-generalize-teams-and-narrow-clubs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Migrate Science Olympiad and CyberPatriot from Club to Team

## Description

Sprint 032 curated 24 Science Olympiad school teams and 3 CyberPatriot
teams into `Club` (`directory/data/science-olympiad-sd.tsv`,
`cyberpatriot-sd.tsv`), each already geocoded via
`directory.pipeline._apply_club_geocoding()` (23/24 Science Olympiad at
school precision, San Dieguito High School Academy flagged
`needs_review = true`; all 3 CyberPatriot at school precision — see
`directory/DESIGN.md`'s sprint 032 revision for the verified detail).
These are competition teams, not clubs, per issue 47's meets-vs-competes
rule. This ticket moves them to `Team`, through the
`team_static_roster.py` source ticket 001 built, **preserving** their
verified geocoding rather than re-deriving it from scratch.

Preservation is achieved architecturally, not by inventing a bypass:
`teams.geo.SchoolIndex` (used by `run_teams()`) is a documented
behavior-identical subclass of the same `geo_ladder.GeoLadder`
`_apply_club_geocoding()` already used, and `directory/data/`'s school
directories are a byte-identical copy of `teams/data/`'s own — so
running the exact same `host_school`/`city`/`postal_code` strings
through `teams.geo.geocode_teams()` deterministically reproduces the
original match. This ticket's job is to prove that, not assume it: the
diff check below is a hard gate before any `Club` data is deleted.

## Acceptance Criteria

- [x] `teams/data/science-olympiad-sd.tsv` and `cyberpatriot-sd.tsv`
      (new) carry `league="SCIOLY"`/`"CYBERPATRIOT"`,
      `program="Science Olympiad"`/`"CyberPatriot"`, `number` set to a
      stable school-name slug (per ticket 001's documented convention),
      `name`, `organization`/`org_type="school"`, `city`,
      `postal_code`, `website` copied verbatim from the corresponding
      `directory/data/*.tsv` row. The `meeting_note` narrative
      (tournament placements, program descriptions) is **not** carried
      over — `Team` has no field for it and `Team.description` is
      structurally reserved for LLM-generated content only (see
      sprint.md's Migration Concerns for why this is an accepted,
      documented scope boundary, not an oversight).
- [x] `teams/registry/science-olympiad-sd.toml`,
      `cyberpatriot-sd.toml` (new), `adapter_type =
      "team_static_roster"`, enabled, `roster_path` pointing at the new
      TSVs, header comments crediting sprint 032's original curation
      research (org_name/citation continuity, not re-verified from
      scratch this ticket).
- [x] A real pipeline run (`run_teams()` with the new registry entries
      active) produces 27 new `Team` records (24 Science Olympiad + 3
      CyberPatriot); `teams.json`'s `total` goes from 278 to 305.
- [x] **Diff-check gate**: for every one of the 27 migrated rows, the
      resulting `Team.location_precision`/`latitude`/`longitude`/
      `matched_name`/`needs_review` is byte-identical to the
      corresponding pre-migration `Club` row's values (captured from
      the current committed `data/clubs.json` before this ticket
      touches anything). San Dieguito's `needs_review = true` survives
      unchanged; the other 26 non-flagged matches survive unchanged. A
      divergence found here is resolved via a `school-overrides.toml`
      entry (the ladder's existing escape hatch) before proceeding —
      never accepted silently and never worked around by inventing a
      new preservation mechanism.
- [x] Only after the diff-check gate passes: `directory/registry/
      science-olympiad-sd.toml`, `cyberpatriot-sd.toml` and
      `directory/data/science-olympiad-sd.tsv`, `cyberpatriot-sd.tsv`
      are deleted; `directory/model.py`'s `ClubType` narrows to drop
      `"science-olympiad"`/`"cyberpatriot"` (now
      `Literal["hack-club", "girls-who-code", "4-h",
      "civil-air-patrol", "sea-cadets"]` — the latter three still drop
      in ticket 003). This lands in the same commit as the registry/
      data removal so no commit ever has a `ClubType` value with no
      backing registry entry, or vice versa.
- [x] A real `uv run partner-scrape directory` run after removal shows
      `clubs.json`'s `total` drop from 57 to 30 (Science Olympiad/
      CyberPatriot gone; 4-H/Civil Air Patrol/Sea Cadets/Hack Club/
      Girls Who Code still present, ticket 003's concern).
- [x] `teams/DESIGN.md` and `directory/DESIGN.md` each get a short note
      recording the migration (what moved, when, why) — full
      contract-level documentation lands in ticket 004.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/
  tests/directory/` in full. `tests/directory/
  test_dataset_validity.py`'s `Club`-side `club_id` uniqueness check
  must still pass against the reduced dataset.
- **New tests to write**:
  - A fixture-driven regression test (new, e.g. `tests/teams/
    test_migration_science_olympiad_cyberpatriot.py` or folded into
    `tests/teams/test_sources_team_static_roster.py`) asserting the
    committed `teams/data/science-olympiad-sd.tsv`/`cyberpatriot-sd.tsv`
    rows, geocoded through the real committed `teams/data/` school
    directories, reproduce a fixture snapshot of the pre-migration
    `Club` rows' five geocoding fields exactly — this is the permanent,
    re-runnable form of the one-time diff-check gate above.
  - Update any test in `tests/directory/` that hard-codes the old
    57-club total, the old 7-value `ClubType` set, or references a
    `science-olympiad-sd`/`cyberpatriot-sd` registry entry.
- **Verification command**: `uv run pytest`, plus one real (network-
  free, since both new sources are local-file reads)
  `uv run partner-scrape teams --dry-run -v` and
  `uv run partner-scrape directory --dry-run -v` to inspect the actual
  before/after payloads (`dangerouslyDisableSandbox` not required for
  this step — no network is touched by either).
