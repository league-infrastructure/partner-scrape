---
id: '007'
title: 'Places directory: model, static-roster source, curated dataset, and directory/
  scaffolding'
status: in-progress
use-cases:
- SUC-004
depends-on:
- '006'
github-issue: ''
issue: 35-standing-entities-clubs-and-places.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Places directory: model, static-roster source, curated dataset, and directory/ scaffolding

## Description

Build the new `partner_scrape/directory/` package and deliver the full
Places directory (issue 35's bounded, curated half — no split needed).
This ticket also does the shared scaffolding ticket 008 (Clubs) will
reuse: `directory/pipeline.py` (`run_directory()`), `directory/export.py`,
the `directory` CLI subcommand, and `mirror.py`/`MIRRORED_DATA_FILES`
wiring — sized here rather than duplicated in ticket 008, per
sprint.md's Architecture (ticket 008 depends on this ticket for exactly
that reason).

**`Place` model** (`directory/model.py` or `directory/places.py`, a
flat dataclass — not a shared base with `Club`, per sprint.md's Design
Rationale): name, category (makerspace / planetarium / observatory /
tide-pool / nature-center / library-maker-lab), description, website,
location fields + the shared geo-ladder's precision/never-guess
outputs (ticket 006), and a `sources` provenance field matching
`Team.sources`'s existing convention.

**Static-roster source**, reusing `teams/sources/static_roster.py`'s
shape (a committed curated file, `fetch()` reads local disk, never
calls the injected `Fetcher`): one curated data file listing every
place, covering every category issue 35 named:

- Makerspaces: SDPL IDEA Labs (the only free public ones), Atlas Labs
  (opening Jan 2027 — include with a clear "opening" note, not as
  already operating).
- Planetariums: Fleet Science Center, Palomar College.
- Observatories: Palomar Observatory, Mount Laguna Observatory.
- Tide pools: Cabrillo National Monument, Birch Aquarium.
- Nature centers: County Parks (relevant sites), Agua Hedionda
  Discovery Center, Living Coast Discovery Center, Tijuana River
  Estuary/NERR.
- Library maker labs: whichever of the newly-registered city libraries
  (ticket 003) have a maker-lab program — cross-check against ticket
  003's actual findings rather than assuming all six do.

Where a place is also a partner-roster org (e.g. Palomar Observatory,
Living Coast), reuse the same curated address/coordinates rather than
re-researching — but do not attempt an automatic cross-reference join
this sprint (out of scope; hand-copy the value).

**Export and wiring**: `directory/export.py` writes `places.json`
(with `clubs.json` as an empty/absent placeholder until ticket 008 —
do not block this ticket on Clubs existing). Add `"places.json"` to
`export/mirror.py`'s `MIRRORED_DATA_FILES`. Add a `directory`
subcommand to `cli.py`, structurally separate from `run`/`teams`
(matching this module's own established convention — never calls
`pipeline.run()` or `teams.pipeline.run_teams()`), with its own
mirroring step following the `teams` subcommand's exact pattern
(`cli.py:347`).

## Acceptance Criteria

- [ ] `partner_scrape/directory/` exists with a `Place` model, a
      static-roster source, `pipeline.py`, and `export.py`.
- [ ] Every place category named in issue 35 has at least one entry in
      the curated dataset; Atlas Labs is marked as opening Jan 2027,
      not as already operating.
- [ ] No place entry's coordinates come from a live geocoder — every
      one uses the shared geo-ladder (ticket 006) or a hand-curated
      address, never a guess.
- [ ] `directory` is a new `cli.py` subcommand, structurally separate
      from `run`/`teams`/`discover-candidates`, with its own
      `--dry-run`/`--no-mirror` handling mirroring the `teams`
      subcommand's existing shape.
- [ ] `places.json` is written and, on a non-dry-run invocation,
      mirrored into `MIRROR_SITE_DIRS` targets via the existing
      `mirror_site_data()` (extended `MIRRORED_DATA_FILES` allowlist),
      with no change to `mirror.py`'s copy logic itself.
- [ ] Existing `run`/`teams`/`discover-candidates` subcommands' flags,
      defaults, and printed output are unchanged (this module's own
      "purely additive" convention for new subcommands).
- [ ] Full test suite stays green, plus new hermetic tests for the
      `Place` model, the static-roster source, and `directory/export.py`.

## Testing

- **Existing tests to run**: `uv run pytest`, especially
  `export/mirror.py`'s and `cli.py`'s existing test coverage, to
  confirm the additive changes don't regress `run`/`teams`.
- **New tests to write**: fixture-based tests for the places
  static-roster source (following `tests/teams/test_sources_static_roster.py`'s
  shape — including a `Fetcher` test double that raises on any call,
  proving the source never touches the network); a `directory/export.py`
  test confirming `places.json`'s shape; a `cli.py` test for the new
  `directory` subcommand's argument parsing and mirror-step wiring.
- **Verification command**: `uv run pytest`, plus
  `uv run partner-scrape directory --dry-run -v` for a live smoke test.

## Implementation Plan

**Approach**: Mirror `teams/`'s existing module shape as closely as
sensible (model, sources, pipeline, export, registry, CLI subcommand)
without importing from `teams/` — only the shared geo-ladder (ticket
006) is a real dependency.

**Files to create/modify**:
- `partner_scrape/directory/__init__.py`, `model.py` (or `places.py`),
  `sources/static_roster.py` (or similar), `pipeline.py`, `export.py`,
  `registry/places.toml` (or a data file under `directory/data/`).
- `partner_scrape/export/mirror.py` — `MIRRORED_DATA_FILES` addition.
- `partner_scrape/cli.py` — new `directory` subcommand.
- `tests/directory/...` — new test package.

**Testing plan**: see Testing above.

**Documentation updates**: a new `directory/DESIGN.md`, following
`teams/DESIGN.md`'s existing shape (Purpose, module boundaries, the
"why a separate model from `Team`" rationale already captured in
sprint.md's Design Rationale — cite it rather than re-deriving it).
