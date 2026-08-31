---
id: '007'
title: 'Places directory: model, static-roster source, curated dataset, and directory/
  scaffolding'
status: done
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

- [x] `partner_scrape/directory/` exists with a `Place` model, a
      static-roster source, `pipeline.py`, and `export.py`.
- [x] Every place category named in issue 35 has at least one entry in
      the curated dataset; Atlas Labs is marked as opening Jan 2027,
      not as already operating.
- [x] No place entry's coordinates come from a live geocoder — every
      one uses the shared geo-ladder (ticket 006) or a hand-curated
      address, never a guess.
- [x] `directory` is a new `cli.py` subcommand, structurally separate
      from `run`/`teams`/`discover-candidates`, with its own
      `--dry-run`/`--no-mirror` handling mirroring the `teams`
      subcommand's existing shape.
- [x] `places.json` is written and, on a non-dry-run invocation,
      mirrored into `MIRROR_SITE_DIRS` targets via the existing
      `mirror_site_data()` (extended `MIRRORED_DATA_FILES` allowlist),
      with no change to `mirror.py`'s copy logic itself.
- [x] Existing `run`/`teams`/`discover-candidates` subcommands' flags,
      defaults, and printed output are unchanged (this module's own
      "purely additive" convention for new subcommands).
- [x] Full test suite stays green, plus new hermetic tests for the
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

## Notes (ticket 007 completion, 2026-08-31)

**Module layout**: `partner_scrape/directory/` — `model.py` (`Place`
dataclass + `Category`/`Status`/`LocationPrecision` Literals and their
`VALID_*` frozenset derivations), `sources/base.py` (`PlaceSource`
protocol, `PlaceRef`/`RawPlaceResponse`, `run()`), `sources/
static_roster.py` (`StaticRosterSource`, reads `data/places.toml`),
`pipeline.py` (`run_directory()`, `_apply_geo_fallback()`), `export.py`
(`export_directory()`), `registry/places-sd.toml` (the one Place
Registry entry), `data/places.toml` (the curated dataset) plus
`data/zip-centroids.toml`/`city-centroids.toml` (committed duplicates
of `teams/data/`'s own files) and genuinely-empty `data/
sd-schools-public.tsv`/`sd-schools-private.tsv`/`school-overrides.toml`
(satisfy `geo_ladder.GeoLadder`'s constructor; Places never use the
school-matching rungs — see `directory/DESIGN.md` §4 for the full
"why duplicated, not imported" rationale).

**Place count by category (19 total)**: makerspace 3 (SDPL Central
IDEA Lab, SDPL Kilroy Realty/San Ysidro IDEA Lab, Atlas Labs),
planetarium 2 (Fleet Science Center, Palomar College), observatory 2
(Palomar, SDSU Mount Laguna), tide-pool 3 (Cabrillo National Monument,
Birch Aquarium's Preuss Tide Pool Plaza, La Jolla/Coast Blvd), nature-
center 5 (Agua Hedionda Discovery Center, Living Coast Discovery
Center, Tijuana River NERR Visitor Center, Mission Trails Visitor
Center, Louis A. Stelzer County Park Nature Center), library-maker-lab
4 (Oceanside, Carlsbad, Escondido, Chula Vista — Coronado and National
City were researched and found to have no public evidence of a
maker-lab program as of this ticket; correctly excluded, not assumed).
18 of 19 carry a hand-curated "address"-precision coordinate; Atlas
Labs (not yet open, no confident street-level coordinate to curate)
resolves via the shared `geo_ladder.GeoLadder`'s ZIP-centroid fallback
(ZIP 92154) at pipeline time.

**Export contract**: `places.json` — `{"meta": {"generated", "total",
"by_category", "by_location_precision"}, "places": [...]}`, written to
both `{site_dir}/src/data/places.json` and `{site_dir}/public/data/
places.json` (sprint 017's "one publish, two paths" convention, reused
unmodified). `clubs.json` is deliberately not written this ticket — see
`export.py`'s own docstring for why "absent," not an "empty
placeholder."

**CLI decision**: one `directory` subcommand, covering both Places
(this ticket) and the future Clubs (ticket 018-008) — per sprint.md's
Open Questions recommendation ("one directory command ... mirrors
teams"). `directory.pipeline.run_directory()` itself is where a future
Clubs dispatch is expected to be added (a new `_CLUB_SOURCES` table
and acquisition loop, following this module's shape), not a second CLI
subcommand.

**Files changed**: see the diff for the full list; summarized in
`directory/DESIGN.md` §2's file tree. Notably also touched:
`partner_scrape/export/mirror.py` (`"places.json"` added to
`MIRRORED_DATA_FILES`), `partner_scrape/cli.py` (`directory`
subcommand + `_run_directory` handler, purely additive), `tests/
test_export_mirror.py` (six new tests for the `places.json` allowlist
entry, mirroring the file's existing `teams.json` section).

**Test count**: 1804 passed (1698 baseline + 106 new: `tests/
directory/` — `test_model.py`, `test_sources_base.py`, `test_sources_
static_roster.py`, `test_pipeline.py`, `test_export.py`, `test_
dataset_validity.py`; `tests/test_cli_directory.py`; six additions to
`tests/test_export_mirror.py`).

**AC status**: all seven boxes checked above. No deferrals.

**Deviations from the plan**: none structural. The Implementation
Plan's parenthetical options were resolved as: `model.py` (not
`places.py`), TOML (not CSV/TSV) for the curated data file — see
`sources/static_roster.py`'s own docstring for why TOML fits this
dataset's shape better than the FLL roster's TSV precedent —
`registry/places-sd.toml` (not `registry/places.toml`, to leave room
for a future second Place Registry entry without a rename), and a
`data/places.toml` roster file under `directory/data/` rather than
folding the dataset into the registry TOML itself (keeps "which
sources are active" separate from "what data they read," matching
`teams/registry/fll-sd.toml` + `teams/data/fll-sd-teams.tsv`'s existing
split).
