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

**This ticket (011-001) builds the acquisition foundation only.** What
exists today is `model.Team`, the `TeamSource` protocol
(`sources/base.py`), its first implementation
(`sources/ftcscout.py`), and the FTCScout registry entry
(`registry/ftc-sd.toml`). There is no merge, geocoding, export, or
CLI-invoked pipeline yet — those are later tickets, landing on top of
this foundation in sequence (`sprint.md`'s Migration Concerns:
001→002→003→004→005, each needing the one before it):

```
BUILT (this ticket, 011-001):
  registry.load_active_sources(teams/registry/)   reused verbatim
     ↓
  sources.ftcscout.FTCScoutSource                  TeamSource protocol
     ↓ (via sources.base.run())
  model.Team objects                                (no email field, ever)

PLANNED (later tickets, not yet built):
  + sources.tba.TBASource                    (011-003 -- 59 FRC teams)
  → merge.py                                 (011-003 -- cross-league identity)
  → geo.py + data/                           (011-004 -- offline geocoding ladder)
  → export.py                                (011-002 -- writes teams.json)
  → pipeline.py  run_teams()                 (011-002 -- sequences the above)
  → cli.py `teams` subcommand                (011-002)
  → site/src/pages/teams/*                   (011-005)
```

A freshly-extracted `Team` from this ticket's `FTCScoutSource`
therefore has `location_precision == "none"` and no coordinates — that
is correct, not a gap: no geocoding rung has run yet. Nothing in
`partner_scrape/teams/` is imported by any existing module
(`pipeline.py`, `cli.py`, `adapters/`) as of this ticket; that wiring
begins in ticket 011-002.

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
- **Deliberate non-goal, this ticket — no merge, no geocoding, no
  export.** `sources/ftcscout.py` only extracts `Team` objects from one
  source; it does not attempt cross-league identity (that needs a
  second source to merge against — ticket 011-003), does not resolve
  coordinates (ticket 011-004), and does not write `teams.json` (ticket
  011-002). Do not "helpfully" add any of these here — each has its
  own ticket, sequenced because each genuinely depends on the one
  before it (geocoding fixtures need real `postal_code` values, which
  only TBA supplies at any real rate).

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
  chains discover → fetch → extract for one `TeamSource`. Ticket
  011-002's `teams.pipeline` is the intended caller once more than one
  source exists to sequence; there is no `teams`-side dispatch
  registry equivalent to `adapters.base.ADAPTERS`.
- **`sources.ftcscout.FTCScoutSource`** — the concrete `TeamSource` for
  FTCScout's REST search endpoint. Config keys read from
  `SourceConfig.config`: `api_base` (default
  `https://api.ftcscout.org`), `region` (default `USCASD`).
- **`teams/registry/ftc-sd.toml`** — the FTCScout source's
  `SourceConfig`, loaded via `registry.loader.load_active_sources`
  pointed at `teams/registry/` (not the main
  `partner_scrape/registry/sources/` directory — a separate, disjoint
  registry namespace).

### Consumes
- **`registry.schema.SourceConfig` / `registry.loader.load_active_sources`
  (from `registry/`)** — reused verbatim for per-league source config;
  no new schema. See `registry/DESIGN.md`.
- **`fetch.Fetcher` (from `fetch/`)** — the protocol every `TeamSource`
  method takes as an explicit argument. Production wiring to a real
  `fetch.PoliteFetcher` instance happens at the call site (ticket
  011-002's `teams.pipeline`, not yet built) — nothing in
  `teams/sources/` constructs a concrete fetcher itself, matching
  `adapters/leaguesync.py`'s convention of taking `Fetcher` as a
  parameter. See `fetch/DESIGN.md`.

## 6. Open Questions / Known Limitations

- Everything below the source layer — `merge.py`, `geo.py`,
  `export.py`, `pipeline.py`, the `teams` CLI subcommand, and the
  `sources/tba.py` FRC source — does not exist yet. This doc describes
  only what ticket 011-001 built; see `sprint.md`'s Tickets table for
  the full sequencing (011-002 through 011-005).
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
