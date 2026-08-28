# teams

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** in-flux

---

## 1. Purpose

`partner_scrape/teams/` acquires, locates, and publishes San Diego
County's FIRST robotics teams (FTC via FTCScout, FRC via The Blue
Alliance in a later ticket) as a standalone `teams.json` data contract,
structurally independent of the existing `Opportunity` pipeline. It is
a subsystem of its own — not folded into `adapters/`/`normalize/`/
`export/` — because a `Team` is a fundamentally different kind of
record: a standing entity with no date, no recurrence, and no
relevance-gating need, none of which the existing pipeline's
abstractions are built around. The seam this subsystem owns is
"acquire, locate, and publish an undated directory entity," which
nothing else in the codebase does.

## 2. Orientation

**Ticket 011-002 (this ticket) wires the acquisition foundation ticket
011-001 built into a runnable, publishable end-to-end path.**
`teams.pipeline.run_teams()` now sequences the Team Registry ->
`TeamSource`(s) -> `teams.export.export_teams()`, and a new
`partner-scrape teams` CLI subcommand invokes it — `teams.json` with
152 FTC teams is a real, buildable artifact as of this ticket. There is
still no merge or geocoding — those remain later tickets, landing on
top of this spine in sequence (`sprint.md`'s Migration Concerns:
001→002→003→004→005, each needing the one before it):

```
BUILT (ticket 011-001):
  registry.load_active_sources(teams/registry/)   reused verbatim
     ↓
  sources.ftcscout.FTCScoutSource                  TeamSource protocol
     ↓ (via sources.base.run())
  model.Team objects                                (no email field, ever)

BUILT (this ticket, 011-002):
  teams.pipeline.run_teams()          Team Registry -> TeamSource(s) dispatch,
     ↓                                per-source failure isolation
  teams.export.export_teams()         writes {site_dir}/src/data/teams.json
     ↓                                (meta envelope + teams array)
  cli.py `teams` subcommand           partner-scrape teams [--dry-run]
                                       [--source ftcscout] [--site-dir DIR]
                                       [--no-mirror] [-v]
     ↓ (unless --no-mirror/--dry-run)
  export.mirror_site_data()           reused unmodified, teams.json added
                                       to MIRRORED_DATA_FILES

PLANNED (later tickets, not yet built):
  + sources.tba.TBASource                    (011-003 -- 59 FRC teams)
  → merge.py                                 (011-003 -- cross-league identity)
  → geo.py + data/                           (011-004 -- offline geocoding ladder)
  → site/src/pages/teams/*                   (011-005)
```

A freshly-extracted `Team` from `FTCScoutSource` still has
`location_precision == "none"` and no coordinates — that is correct,
not a gap: no geocoding rung has run yet (ticket 011-004). `teams.json`
publishes that honestly (`by_location_precision: {"none": 152}` in its
`meta`) rather than hiding it. As of this ticket, `cli.py` imports
`teams.pipeline.run_teams` — the one and only edge from any existing,
non-`teams/` module into this subsystem.

**FTCScout, this ticket's only source.** `api.ftcscout.org`, free,
unauthenticated. Its REST search endpoint returns 152 San Diego FTC
teams in one response — no pagination, no probing needed, one
`TeamRef` per run. It supplies city and (62% of the time) a school
name, but confirmed live: no website and no ZIP for any of the 152
records (0/3,412 nationally too). The Blue Alliance (ticket 011-003)
is the first real source of website/ZIP coverage.

## 3. Constraints and Invariants

- **Never register with `adapters.base.ADAPTERS`.** A team source
  registered there would become reachable from `pipeline.run()`, which
  would hand a `Team` object to `normalize.run()` — a type it does not
  expect — and crash. `TeamSource` (`sources/base.py`) is a separate
  `Protocol` with no import relationship to `adapters.base` at all —
  `tests/teams/test_sources_base.py` enforces this by scanning every
  module actually shipped in `teams/sources/` for a forbidden import,
  so a future addition (e.g. `sources/tba.py`) that violates it fails
  the same test, not just today's code.
- **No `email` field, structurally, on `model.Team`.** A follow-on
  sprint may eventually ingest `data/robot-teams.json` (40 email
  addresses, including six volunteer coaches' personal Gmail
  accounts); there is nowhere on this dataclass to put one.
  `tests/teams/test_model.py`'s `TestNoEmailField` asserts this by
  inspecting `dataclasses.fields(Team)` directly, not by convention.
- **FTCScout uses its REST endpoint, not GraphQL.** `fetch.Fetcher`
  (`fetch/fetcher.py`) is GET-only; adding a `post()` method to support
  GraphQL would ripple into every `FixtureFetcher` test double in the
  whole suite for this one source's benefit.
- **Out-of-region teams are flagged, never dropped.** A team whose
  (cleaned) city is in `sources.ftcscout.OUT_OF_REGION_CITIES` (6 of
  152 FTC teams: Ensenada ×2, San Clemente, San Antonio, Louisville,
  Agoura Hills) is published with `Team.in_region = False`, not
  excluded. The set is a denylist, not an allowlist — an unrecognized
  new city defaults to `in_region=True`, which is the safer failure
  mode (a real San Diego community not yet seen must never be silently
  flagged out-of-region because it's missing from a hand-maintained
  list).
- **Dirty city strings are normalized at extraction time, not
  deferred.** Measured live: 27 raw distinct `city` strings for what
  is really 24 places (`"La Jolla "` with trailing whitespace,
  `"carlsbad"`/`"Carlsbad"`, `"san diego"`/`"San Diego"`).
  `sources/ftcscout._clean_city()` strips and title-cases every record
  before it becomes a `Team.city` value, so every later stage (merge,
  geocoding, site filters) sees one canonical string per place. This
  is a simple, sufficient fix for the variants actually observed — it
  is not a general place-name normalizer, and ticket 011-004's `geo.py`
  does the real matching against CDE/NCES school directories.
- **Deliberate non-goal, still — no merge, no geocoding.**
  `sources/ftcscout.py` only extracts `Team` objects from one source;
  it does not attempt cross-league identity (that needs a second
  source to merge against — ticket 011-003) and does not resolve
  coordinates (ticket 011-004). Do not "helpfully" add either here —
  each has its own ticket, sequenced because each genuinely depends on
  the one before it (geocoding fixtures need real `postal_code`
  values, which only TBA supplies at any real rate).
- **`teams/export.py` never writes or touches `opportunities.json` or
  `scrape-meta.json`.** Those are `export/writer.py`'s exclusive
  outputs; `scrape-meta.json` in particular carries the *opportunities*
  export's freshness timestamp, and a `teams` run overwriting it would
  make the site falsely claim opportunities were just refreshed.
  `teams.json` carries its own `meta.generated` timestamp instead. Two
  dedicated regression tests in `tests/teams/test_export.py` assert
  both files are byte-identical before and after a `teams` run, over
  the full 152-team fixture, not just a single hand-built `Team`.
- **`teams` is a CLI subcommand, never a flag on `run`.** Rosters
  refresh annually; opportunities refresh weekly. A future TBA auth
  failure (ticket 011-003) must never sit inside the same process/exit
  code as the weekly opportunities export. `cli.py`'s `_run_teams()`
  never calls `run`/`pipeline.run()`, and `tests/test_cli_teams.py`
  asserts the isolation in both directions (`teams` never reaches
  `pipeline.run()`; the no-subcommand path never reaches `run_teams()`).
- **`export_teams()` drops `Team.sources` from the published field
  set**, the same way `export/writer.py`'s `SITE_SCHEMA_FIELDS` drops
  `Opportunity.sources` — cross-source acquisition bookkeeping (which
  source(s) contributed a record) has no counterpart in the site's
  schema. `teams/export.py`'s `TEAMS_SCHEMA_FIELDS` is derived from
  `dataclasses.fields(Team)` the same drift-proof way, so a future field
  (e.g. ticket 011-003/011-004's `org_key`, `latitude`) is published
  automatically with no `export.py` change required.

## 4. Design

**Why `Team` is a new, separate model, not a widened `Opportunity`/
`Kind`.** A team is a standing entity with no date, and
`export/writer.py`'s current-and-upcoming filter would drop every one
of them; widening `Kind` would ripple into `enrich/`,
`normalize/run.py`, and `export/writer.py` for near-zero reuse (no
date, no recurrence, no relevance gate, no taxonomy in common). See
`sprint.md`'s Design Rationale for the full comparison.

**Why `organization`/`org_type` come from `schoolName`, mapped, not
copied.** FTCScout's `schoolName` field is populated for every record,
but 58 of 152 (38%) carry the literal sentinel `"Family/Community"` —
a home team with no sponsoring school, not an organization named
"Family/Community". `_extract_one()` maps that sentinel to
`organization=""`, `org_type="family_community"` specifically so a
later stage (ticket 011-003's `merge.py`) can key cross-league identity
on a non-empty normalized organization name without accidentally
fusing 58 unrelated home teams into one bogus "Family/Community"
organization — `merge.py` doesn't exist yet, but this extraction
decision is what makes that rule enforceable when it lands.

**Why `location_precision` defaults to `"none"` here rather than
`"city"`.** FTCScout does give city-level data, so it might seem
`"city"` is more accurate. `location_precision` is reserved for what
`teams/geo.py`'s seven-rung offline ladder (ticket 011-004) actually
resolved — school match, ZIP centroid, city centroid, or nothing.
Stamping `"city"` here, before that ladder has run at all, would be a
false claim about *how* the location was resolved, not just *that* a
city string exists. `Team.city` already carries the raw (cleaned)
place name for anything downstream that wants it before geocoding
runs; `location_precision` is reserved for geocoding provenance
specifically.

**Why FTCScout/TBA (ticket 011-003) will share no extraction code
beyond the `TeamSource` protocol shape.** The two payloads are
structurally unrelated (FTCScout: REST search, thin fields; TBA:
`/api/v3/teams/{page}`, richer fields, Bearer auth) — forcing a shared
extraction helper would couple two things that change for unrelated
reasons. `sources/base.py` supplies only the shared protocol shape
(`discover`/`fetch`/`extract` → `Team` objects) and a generic
`run()` chaining helper, matching `adapters.base.Adapter`/
`adapters.base.run()`'s shape closely enough to reuse the mental
model, deliberately not the type itself (see Constraints).

**Why `teams.pipeline._TEAM_SOURCES` is a private local dict, not a
second `adapters.base.ADAPTERS`.** `sources.base.run()` deliberately
takes its `TeamSource` as an explicit argument rather than resolving
one from a shared table (see `sources/base.py`'s own docstring) — the
*caller* still needs some way to pick a `TeamSource` per Team Registry
entry's `adapter_type`, and `teams.pipeline` is that one caller.
`_TEAM_SOURCES` is not exported, not imported by anything else, and
provides no path from `partner_scrape.pipeline.run()` into this
subsystem — it is a plain lookup local to one function, not a
public, growable extension point like `ADAPTERS` is. Ticket 011-003
adds a `"tba"` entry here, nothing more.

**Why `teams.export.export_teams()` performs no current/upcoming
filter or slug-dedup pass, unlike `export/writer.py`.** Teams are
undated (no filter possible or needed) and `team_id` is already
globally unique by construction (`f"{league.lower()}-{number}"`, set
at extraction time) — both of `export/writer.py`'s extra passes exist
to solve problems `Team` structurally doesn't have. What *is* reused
is the same "serialize exactly the published field set, write, done"
shape, via `TEAMS_SCHEMA_FIELDS`'s drift-proof `dataclasses.fields()`
derivation.

**Why `--source` on the `teams` subcommand filters by `adapter_type`,
not by Team Registry file stem.** `pipeline.run()`'s own `--source`
flag matches a Source Registry file's stem (e.g. `coastalrootsfarm`),
because that pipeline's registry holds one file per organization.
`teams`' registry instead holds one file per *league/program* source
(`ftc-sd.toml`, and ticket 011-003's `frc-sd.toml`), and the operator-
facing need is "run only FTCScout" / "run only TBA" (e.g. to isolate a
TBA outage) — a property of *which acquisition method*, not which
file. Filtering on `SourceConfig.adapter_type` (`"ftcscout"`, `"tba"`)
matches that need directly.

## 5. Interfaces

### Exposes
- **`model.Team`** — the record type: `team_id`, `league`, `program`,
  `number`, `name`, `organization`, `org_type`, `city`, `postal_code`,
  `latitude`, `longitude`, `location_precision`, `in_region`,
  `website`, `website_status`, `organization_website`, `rookie_year`,
  `active`, `last_season`, `sponsors`, `org_key`, `sibling_team_ids`,
  `sources`. Every field defaults to an empty/neutral value; no
  `email` field exists (Constraints). Fields are populated
  incrementally across pipeline stages — this ticket's
  `sources/ftcscout.py` sets identity/organization/city/sponsors/
  in-region fields only; `org_key`/`sibling_team_ids` (ticket
  011-003), `latitude`/`longitude`/`location_precision`/
  `organization_website` (ticket 011-004) are set later.
- **`sources.base.TeamSource`** — the injectable per-source protocol
  (`discover(source, fetcher) -> Iterable[TeamRef]`,
  `fetch(ref, fetcher) -> RawTeamResponse`,
  `extract(raw, source) -> Iterable[Team]`), parallel in shape to
  `adapters.base.Adapter` but with no import relationship to it
  (Constraints).
- **`sources.base.run(source, team_source, fetcher) -> list[Team]`** —
  chains discover → fetch → extract for one `TeamSource`. Called by
  `teams.pipeline.run_teams()`, once per active Team Registry entry
  whose `adapter_type` has a registered `TeamSource`; there is no
  `teams`-side dispatch registry equivalent to `adapters.base.ADAPTERS`
  (see Design, "`_TEAM_SOURCES` is a private local dict").
- **`sources.ftcscout.FTCScoutSource`** — the concrete `TeamSource` for
  FTCScout's REST search endpoint. Config keys read from
  `SourceConfig.config`: `api_base` (default
  `https://api.ftcscout.org`), `region` (default `USCASD`).
- **`teams/registry/ftc-sd.toml`** — the FTCScout source's
  `SourceConfig`, loaded via `registry.loader.load_active_sources`
  pointed at `teams/registry/` (not the main
  `partner_scrape/registry/sources/` directory — a separate, disjoint
  registry namespace).
- **`pipeline.run_teams(*, registry_dir=None, source=None, site_dir=None,
  fetcher=None, dry_run=False) -> dict`** (ticket 011-002) — the
  programmatic entry point: loads the Team Registry (defaulting to the
  real seed, `teams/registry/`), dispatches each active source to its
  `TeamSource` via `_TEAM_SOURCES`, isolates any one source's failure
  (logged and skipped, matching `pipeline.run()`'s own SUC-008
  contract), and hands the accumulated `Team[]` to `export_teams()`.
  Returns that call's `{"meta": ..., "teams": [...]}` payload unchanged.
- **`export.export_teams(teams, site_dir=None, *, dry_run=False) -> dict`**
  (ticket 011-002) — writes `{site_dir}/src/data/teams.json` as
  `{"meta": {...}, "teams": [...]}`. `meta` carries `generated`
  (timestamp), `total`, `by_league`, `out_of_region`, and
  `by_location_precision` — coverage/data-quality made visible in the
  artifact itself, not just a log line. `TEAMS_SCHEMA_FIELDS` (every
  `Team` field except `sources`) is the published field set, derived
  from `dataclasses.fields(Team)` so it can never drift. Raises
  `RuntimeError` on an unwritable `site_dir`/`src/data`, matching
  `export_opportunities`'s loud-failure contract; `dry_run=True`
  computes and returns the payload without touching disk. **Never**
  writes or touches `opportunities.json`/`scrape-meta.json` (Constraints).
- **`partner-scrape teams [--dry-run] [--source ftcscout] [--site-dir
  DIR] [--no-mirror] [-v]`** (ticket 011-002, `cli.py`) — the CLI entry
  point. Constructs a real `PoliteFetcher()` and calls `run_teams()`;
  unless `--dry-run`/`--no-mirror`, also calls `export.mirror_site_data`
  (reused, unmodified) against `config.get_mirror_site_dirs()`. Never
  calls `run`/`pipeline.run()` — see `cli.py`'s own module docstring
  and Constraints above.
- **`export/mirror.py`'s `MIRRORED_DATA_FILES`** (ticket 011-002) —
  gained one entry, `"teams.json"`; no change to `mirror_site_data`'s
  own copy logic. See `export/DESIGN.md`.

### Consumes
- **`registry.schema.SourceConfig` / `registry.loader.load_active_sources`
  (from `registry/`)** — reused verbatim for per-league source config;
  no new schema. See `registry/DESIGN.md`.
- **`fetch.Fetcher` (from `fetch/`)** — the protocol every `TeamSource`
  method takes as an explicit argument. Production wiring to a real
  `fetch.PoliteFetcher` instance happens in `cli.py`'s `_run_teams()`
  handler, passed through `teams.pipeline.run_teams()`'s `fetcher`
  parameter — nothing in `teams/sources/` or `teams/pipeline.py`
  constructs a concrete fetcher's default itself except that one CLI
  call site, matching `adapters/leaguesync.py`'s convention of taking
  `Fetcher` as a parameter. See `fetch/DESIGN.md`.
- **`config.get_site_dir()` / `config.get_mirror_site_dirs()` (from
  `config.py`)** (ticket 011-002) — the same site-checkout resolution
  `export/writer.py` and `cli.py`'s `run` command already use;
  `teams/export.py` and `cli.py`'s `teams` handler reuse them
  unmodified rather than duplicating `SITE_DIR`/`MIRROR_SITE_DIRS`
  resolution. See the root `partner_scrape/DESIGN.md`.
- **`export.mirror_site_data` (from `export/`)** (ticket 011-002) —
  reused, unmodified, to propagate `teams.json` into extra checkouts.
  See `export/DESIGN.md`.

## 6. Open Questions / Known Limitations

- `merge.py`, `geo.py`, and `sources/tba.py` (the FRC source) do not
  exist yet — this doc describes what tickets 011-001 and 011-002
  built; see `sprint.md`'s Tickets table for the remaining sequencing
  (011-003 through 011-005).
- `teams.pipeline.run_teams()`'s per-source failure isolation (logged
  and skipped) is exercised this ticket only via a synthetic
  test double (`tests/teams/test_pipeline.py`'s
  `TestSourceFailureIsolation`) — FTCScout itself has no known failure
  mode this ticket triggers live. Ticket 011-003 is the first source
  this isolation is load-bearing for in production (a missing/401
  `TBA_KEY`, per `sprint.md`'s Migration Concerns).
- `sources.ftcscout.OUT_OF_REGION_CITIES` is a small hand-maintained
  denylist derived from one live measurement (2026-08-27). It is
  sufficient for this ticket's fixture-based tests but is not the
  "real" county-boundary determination — ticket 011-004's CDE/NCES-
  driven geocoding ladder is the actual authority on location, and may
  eventually supersede this denylist entirely.
- `FTCScoutSource.fetch()` does not send any auth header (FTCScout
  needs none) — unlike `adapters/leaguesync.py`'s Bearer-token pattern.
  If FTCScout ever requires a credential, `config.py` (the sole
  `os.environ` reader) would need a new accessor, matching
  `get_leaguesync_api_key()`'s shape.
- Whether `teams.json` is ever joined to the curated partner directory,
  and whether LLM-assisted website discovery is added later, are both
  explicitly out of scope for the whole sprint, not just this ticket —
  see `sprint.md`'s Design Rationale and Scope.
