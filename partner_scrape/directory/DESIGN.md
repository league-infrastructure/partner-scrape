# directory

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-31 (sprint 018, ticket 007 — Places directory shipped) · **Status:** Places complete; Clubs (ticket 018-008) not yet built

---

## 1. Purpose

`partner_scrape/directory/` acquires and publishes San Diego's curated,
undated "standing entity" directories — Places (this ticket: a "where
to go any day" reference of makerspaces, planetariums, observatories,
tide pools, nature centers, and library maker labs) and, from ticket
018-008 onward, Clubs (Hack Club chapters as the sprint's one proof-of-
concept type). It generalizes the pattern `teams/` already proved for
FIRST robotics teams (sprint 011/012): a standing directory entity has
no date, no recurrence, and no relevance gate, none of which the
existing `Opportunity` pipeline's abstractions are built around. See
`teams/DESIGN.md` §1 for the identical argument made for `Team` — this
module is the second (and third) instance of that same shape, not a
new architectural idea.

## 2. Orientation

**Ticket 018-006** extracted the general-purpose parts of `teams/
geo.py`'s seven-rung offline geocoding ladder into a new shared module,
`partner_scrape/geo_ladder.py` (`GeoLadder`), specifically so this
module could depend on it without depending on `teams/` or duplicating
its logic. See that module's own docstring for the full rung-by-rung
description; this document does not re-derive it.

**Ticket 018-007 (this ticket)** built the whole `directory/` package
and shipped the full Places directory:

```
partner_scrape/directory/
  model.py              Place dataclass, Category/Status/LocationPrecision
                         Literals + their VALID_* frozenset derivations
  sources/
    base.py              PlaceSource protocol (discover/fetch/extract),
                          PlaceRef/RawPlaceResponse, run() chaining helper
    static_roster.py      StaticRosterSource -- reads directory/data/
                          places.toml straight off disk, never touches
                          the injected Fetcher
  pipeline.py            run_directory(): Place Registry -> PlaceSource(s)
                          -> _apply_geo_fallback() (GeoLadder rungs 5-6
                          only) -> export_directory()
  export.py              export_directory(): writes places.json to both
                          src/data/ and public/data/ (sprint 017's "one
                          publish, two paths" convention)
  registry/
    places-sd.toml        the one Place Registry entry, adapter_type =
                          "static_roster"
  data/
    places.toml            the curated 19-place dataset itself
    zip-centroids.toml,     committed duplicates of teams/data/'s own
    city-centroids.toml,    files (see "Why directory/data/ duplicates
    school-overrides.toml,  teams/data/" below) -- school-overrides.toml
    sd-schools-public.tsv,  and both school TSVs are genuinely EMPTY
    sd-schools-private.tsv  (header rows only) as of this ticket
```

`cli.py` gained a `directory` subcommand (`_add_directory_subcommand`/
`_run_directory`), structurally parallel to `teams`'s own subcommand,
and `export/mirror.py`'s `MIRRORED_DATA_FILES` gained `"places.json"`.
Both are purely additive — no existing `run`/`teams`/
`discover-candidates` flag, default, or printed line changed.

**Places count and category coverage (as of this ticket):** 19 curated
places — 3 makerspaces, 2 planetariums, 2 observatories, 3 tide-pool
sites, 5 nature centers, 4 library maker labs. Every category issue 35
named has at least one entry. 18 of 19 carry a hand-curated,
address-precision coordinate; the 19th (`atlas-labs`, not yet open —
see below) resolves through the shared ladder's ZIP-centroid fallback
to a real, in-bounds coordinate (ZIP 92154 centroid).

**Library maker labs were cross-checked, not assumed.** Ticket
018-003 registered six newly-added city libraries to the partner
roster (Oceanside, Carlsbad, Escondido, Coronado, Chula Vista, National
City) but did not research which of them actually run a maker-lab
program. This ticket did that research directly: Oceanside (Discovery
Lab), Carlsbad (Exploration HUB at Dove Library), Escondido (free 3D
printing + monthly TinkerCAD classes), and Chula Vista (Innovation
Station at the Civic Center branch) all have a confirmed, named
program. No public evidence of a maker-lab program was found for
Coronado or National City as of this ticket — both are correctly
**absent** from `places.toml`, not force-included. If either city
launches one later, add it as a new `[[place]]` entry; do not assume
absence means "not yet researched."

**Atlas Labs is included per issue 35's explicit instruction, marked
`status = "opening"`, never `"open"`.** It is a members-only ($69/mo+)
hardware makerspace at 2293 Verus Street (Otay Mesa), opening January
2027 — confirmed live against its own site. `status_note` carries the
human-readable detail. This is the one entry `_extract_one()`'s
validation actively enforces: any entry with `status != "open"` must
carry a non-empty `status_note`, or the roster fails to parse that
entry (logged and skipped, not silently published without context).

## 3. Constraints and Invariants

- **`directory/` must never import `teams/`, anywhere in the package —
  and the reverse must also never happen.** Sprint 018's Design
  Rationale: importing `teams/` from `directory/` (or vice versa) is
  "a semantically backwards dependency" and risks a future circular
  import. Both modules depend on the shared `geo_ladder.GeoLadder`
  instead. `tests/directory/test_sources_base.py`'s
  `test_no_module_anywhere_under_directory_package_imports_teams` scans
  every `.py` file under `partner_scrape/directory/` via `ast`,
  matching `tests/teams/test_sources_base.py`'s own forbidden-import
  precedent — a future addition to this package that adds the
  forbidden import fails this test too, not just today's code.
- **Never register with `adapters.base.ADAPTERS`.** A place source
  registered there would become reachable from `pipeline.run()`, which
  would hand a `Place` object to `normalize.run()` — a type it does
  not expect — and crash. `PlaceSource` (`sources/base.py`) is its own
  `Protocol` with no import relationship to `adapters.base` at all,
  the identical guarantee `teams.sources.base.TeamSource` already
  established.
- **`sources/static_roster.py` never calls the injected `Fetcher`,
  structurally, not just by convention.** `discover()` returns a
  single `PlaceRef` whose `url` is a local filesystem path;
  `StaticRosterSource.fetch()` reads it via `Path.read_text()` and
  ignores `fetcher` entirely. `tests/directory/
  test_sources_static_roster.py`'s `TestNeverTouchesFetcher` asserts
  this with a `Fetcher` double that raises on any call, run through
  the full `sources.base.run()` chain — the same "runtime-call
  assertion" `teams/sources/static_roster.py`'s own test module uses.
- **Places never route through the shared ladder's organization-name
  school-matching rungs (1-4).** A `Place` has no sponsoring
  organization to match against a school directory — it is a venue,
  not a team. `directory.pipeline._apply_geo_fallback()` calls
  `GeoLadder.resolve_zip()`/`resolve_city()` directly (rungs 5-6 only),
  never `GeoLadder.locate()`, which would attempt the school rungs
  first. This is a deliberate scope narrowing versus `teams.geo.
  SchoolIndex.resolve()`, which does use the full ladder because a
  `Team`'s `organization` field is exactly what the school rungs are
  for.
- **No place entry's coordinates ever come from a live geocoder.**
  Every `Place.latitude`/`longitude` is either "address" precision
  (hand-curated directly in `places.toml`, verified against the
  venue's own site or a corroborating public source before being
  entered — never passed through a geocoding API) or "zip"/"city"
  precision (the shared ladder's own offline centroid tables) or
  entirely absent (`"none"`, never guessed).
  `tests/directory/test_dataset_validity.py`'s
  `TestNoLiveGeocodedCoordinate` and `tests/directory/
  test_sources_static_roster.py`'s
  `test_no_source_ever_calls_a_live_geocoder` both assert this
  structurally: the static-roster source itself only ever produces
  `"address"` or `"none"`.
- **`related_partner_id` is a deliberate, hand-verified join, never
  auto-derived.** Sprint 018 ticket 007's own instruction: "do not
  attempt an automatic cross-reference join this sprint... hand-copy
  the value." Every non-`None` `related_partner_id` in `places.toml`
  was checked against `site/src/data/partners.json`'s own `id` field
  by hand at authoring time; `tests/directory/test_dataset_validity.py`'s
  `TestRelatedPartnerIdJoinIntegrity` re-verifies every one still
  resolves to a real roster row (the same spot-check discipline ticket
  003's own `TestBatchARegistryJoinIntegrity` established) and spot-
  checks four of them against the expected org name.
- **`clubs.json` does not exist yet.** `directory/export.py`'s
  `export_directory()` has no `clubs` parameter at all as of this
  ticket — see that module's own docstring for why this is a
  deliberate "absent," not an "empty placeholder." Ticket 018-008 adds
  it when the `Club` model exists.
- **`directory` is one CLI subcommand covering both Places and the
  future Clubs, not two.** Per sprint.md's Open Questions
  recommendation ("one directory command ... mirrors teams"), left to
  ticket 007/008's judgment — this ticket's judgment call. Ticket
  018-008 is expected to extend `run_directory()`'s own dispatch (a new
  `_CLUB_SOURCES` table and acquisition loop, following this module's
  shape), not add a second CLI subcommand.

## 4. Design

**Why `Place` is a separate flat dataclass from `Team` (and the future
`Club`), not a shared base class.** See sprint.md's Design Rationale in
full; not re-derived here beyond the one-line summary already in
`directory/model.py`'s own docstring: a `Club` has membership/program
concerns a `Place` doesn't, and vice versa for hours/category concerns
— forcing a shared base would either grow speculative optional fields
on both or under-model one of them. Field-name duplication (`website`,
location fields, `sources`) with `Team` is accepted, matching the
existing `Team`/`Event` precedent.

**Why TOML, not TSV, for `places.toml` — unlike the FLL roster's
TSV.** `teams/data/fll-sd-teams.tsv` derives from an upstream export
with a fixed, narrow six-column shape. This dataset has no upstream
export at all — every row was hand-researched from each venue's own
site or a corroborating public source (see `sources/
static_roster.py`'s own docstring for the full accounting, including
the web searches that determined which city libraries actually run a
maker-lab program). Each `Place` carries substantially more fields
than a flat delimited table renders cleanly, and this codebase already
uses TOML for exactly this shape of curated data
(`school-overrides.toml`, `zip-centroids.toml`) — an array of tables
(`[[place]]`) is the better fit. This is a data-format choice, not a
behavioral one; every FLL-precedent behavior (never touch `fetcher`,
per-entry failure isolation, a local-path ref) is reused unchanged.

**Why `directory/data/` duplicates `teams/data/`'s ZIP/city-centroid
files instead of pointing at them directly.** `geo_ladder.GeoLadder`'s
constructor requires all five of its data files (two school TSVs, one
overrides TOML, two centroid TOMLs) to exist under one `data_dir` —
there is no way to hand it "just the centroids." Since `directory/`
must never import or reference `teams/`'s own data path (see
Constraints, above — that would recreate the exact "backwards
dependency" sprint 018 rejected, just via a file path instead of a
Python import), `directory/data/` carries its own committed copy of
`zip-centroids.toml`/`city-centroids.toml` (byte-identical as of this
ticket; see those files' own header comments for the "re-copy by hand
after a refresh" note) plus genuinely-empty `sd-schools-public.tsv`/
`sd-schools-private.tsv`/`school-overrides.toml` — Places have zero
real school-matching data to carry (see the constraint above on why
Places never use the school rungs at all). Ticket 018-008 (Clubs —
Hack Club chapters are school-hosted) is expected to be the first
consumer that needs real school data here, and can populate it then;
this ticket does not, per its own "do not block on Clubs existing"
scope. **Alternatives considered:** (a) import `teams.geo.
DEFAULT_DATA_DIR` directly — rejected, recreates the forbidden
dependency; (b) move the shared centroid files to a new common
location both `teams/` and `directory/` point at — rejected as
out-of-scope for this ticket (ticket 018-006 already shipped `teams/
geo.py`'s `DEFAULT_DATA_DIR` unchanged at `teams/data/`; relocating it
now would relitigate a closed ticket's decision for a benefit — saving
~660 lines of duplicated, low-churn centroid data — that does not
justify reopening it).

**Why `_apply_geo_fallback()` only constructs a `GeoLadder` when at
least one `Place` actually needs it.** For this ticket's real curated
dataset, that is exactly one entry (`atlas-labs`). Every other place
already carries a hand-curated, address-precision coordinate, so a
`directory` run whose static roster resolved everything by hand never
pays the ladder's five-data-file loading cost at all —
`tests/directory/test_pipeline.py`'s
`test_geo_ladder_is_never_constructed_when_nothing_needs_fallback`
proves this directly (a nonexistent `data_dir` would make
`GeoLadder(...)` raise if it were ever constructed).

**Why `export_directory()` sorts by `(category, name)` rather than
`teams/export.py`'s `(league, natural_number)`.** Places have no
natural numeric ordering the way a robotics team number does;
grouping by category (so a visitor sees "every planetarium together,"
etc.) then alphabetically by name is the natural reading order for a
"where to go any day" reference.

## 5. Open Questions

- Should `directory/data/`'s duplicated ZIP/city-centroid files be
  refreshed automatically alongside `teams/data/`'s own copies (e.g. by
  extending `dev/refresh_school_directories.py` to write both
  locations), rather than "re-copy by hand"? Deferred — the data
  changes rarely (Census ZCTA/CDE school-directory refreshes are
  roughly yearly) and this ticket did not touch `dev/
  refresh_school_directories.py`. Worth revisiting if the two copies
  are ever found to have drifted.
- Should Coronado and National City libraries be re-checked
  periodically for a maker-lab program launch, given they were
  confirmed absent only as of this ticket's research pass (2026-08-31)?
  No monitoring exists for this (curated data is described as
  near-zero-maintenance per sprint.md's Scope) — revisit only if a
  stakeholder reports one has since opened.
