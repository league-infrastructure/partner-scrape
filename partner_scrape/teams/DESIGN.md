# teams

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 (ticket 011-004) · **Status:** in-flux

---

## 1. Purpose

`partner_scrape/teams/` acquires, locates, and publishes San Diego
County's FIRST robotics teams (FTC via FTCScout, FRC via The Blue
Alliance) as a standalone `teams.json` data contract, structurally
independent of the existing `Opportunity` pipeline. It is a subsystem
of its own — not folded into `adapters/`/`normalize/`/`export/` —
because a `Team` is a fundamentally different kind of record: a
standing entity with no date, no recurrence, and no relevance-gating
need, none of which the existing pipeline's abstractions are built
around. The seam this subsystem owns is "acquire, locate, and publish
an undated directory entity," which nothing else in the codebase does.

## 2. Orientation

**Ticket 011-004 (this ticket) adds the offline geocoding ladder —
the increment that actually delivers the sprint's stated goal of
*knowing where the teams are*.** `teams.pipeline.run_teams()` now runs
both sources, links cross-league identity, and geocodes every merged
`Team` through `teams.geo.geocode_teams()` before export. Measured
against the real 211-team FTC+FRC corpus (`tests/fixtures/teams/`, the
same live-captured fixtures ticket 011-003 uses) at this ticket's build
(2026-08-28): **129 teams at school precision** (79 FTC + 50 FRC), **8
at ZIP**, **70 at city**, **4 unresolved** (`"none"` — two Ensenada
teams, plus two out-of-region teams whose city name is too ambiguous
to guess, "San Antonio"/"Louisville"), **14 flagged `needs_review`**.
Only site pages remain (`sprint.md`'s Migration Concerns:
001→002→003→004→005, each needing the one before it):

```
BUILT (ticket 011-001):
  registry.load_active_sources(teams/registry/)   reused verbatim
     ↓
  sources.ftcscout.FTCScoutSource                  TeamSource protocol
     ↓ (via sources.base.run())
  model.Team objects                                (no email field, ever)

BUILT (ticket 011-002):
  teams.pipeline.run_teams()          Team Registry -> TeamSource(s) dispatch,
     ↓                                per-source failure isolation
  teams.export.export_teams()         writes {site_dir}/src/data/teams.json
     ↓                                (meta envelope + teams array)
  cli.py `teams` subcommand           partner-scrape teams [--dry-run]
                                       [--source ftcscout|tba] [--site-dir DIR]
                                       [--no-mirror] [-v]
     ↓ (unless --no-mirror/--dry-run)
  export.mirror_site_data()           reused unmodified, teams.json added
                                       to MIRRORED_DATA_FILES

BUILT (ticket 011-003):
  sources.tba.TBASource                probes /api/v3/status for
     ↓                                 max_team_page, enumerates every
     ↓                                 /api/v3/teams/{page}, filters to
     ↓                                 CA + SD_COUNTY_CITIES -- 59 teams
  teams.merge.merge_teams(teams)       links Team.org_key/sibling_team_ids
     ↓                                 by normalized organization name,
     ↓                                 run after every source, before geocode

BUILT (this ticket, 011-004):
  teams.geo.geocode_teams(teams)       seven-rung offline ladder (below),
     ↓                                 run once over the merged Team[],
     ↓                                 after merge_teams(), before export
  teams/data/*.tsv, *.toml             CDE + NCES + ZIP/city centroids +
     ↓                                 school-overrides.toml, all committed
  dev/refresh_school_directories.py    standalone yearly refresh (network;
                                        never imported by teams/geo.py or
                                        teams.pipeline)
  (feeds into ticket 011-002's export_teams(), unchanged)

PLANNED (later tickets, not yet built):
  → site/src/pages/teams/*                   (011-005)
```

A freshly-extracted `Team` from either source still has
`location_precision == "none"` and no coordinates until
`teams.geo.geocode_teams()` runs — that stage now runs on every
`run_teams()` call, so `teams.json` carries real coordinates for most
teams as of this ticket. `cli.py` still imports only
`teams.pipeline.run_teams` — the one and only edge from any existing,
non-`teams/` module into this subsystem; `teams.geo` itself has zero
edges into `partner_scrape.fetch` or any other network-capable module
(see Constraints and `teams/geo.py`'s own docstring).

**FTCScout**, `api.ftcscout.org`, free, unauthenticated. Its REST
search endpoint returns 152 San Diego FTC teams in one response — no
pagination, no probing needed, one `TeamRef` per run. It supplies city
and (62% of the time) a school name, but confirmed live: no website and
no ZIP for any of the 152 records (0/3,412 nationally too).

**The Blue Alliance (this ticket)**, `www.thebluealliance.com/api/v3`,
keyed (`X-TBA-Auth-Key`, 401 without it). Unlike FTCScout, TBA has no
region-scoped search endpoint — `discover()` first probes `/api/v3/
status` for `max_team_page` (23 measured live), then enumerates every
`/api/v3/teams/{page}` (~9,163 teams worldwide, 496 in California),
filtering down to the 59 in `sources.tba.SD_COUNTY_CITIES` (an
allowlist — see Constraints below for why it must be one, unlike
FTCScout's denylist). TBA is the first real source of website (73%)
and ZIP (83%) coverage; its `lat`/`lng`/`address`/`location_name`/
`gmaps_place_id` fields are documented in TBA's own OpenAPI spec as
"Will be NULL, for future development" and confirmed NULL for all 59 SD
teams, so this source never reads them at all — **TBA is not a
geocoding source**; only ticket 011-004's `geo.py` sets
`Team.latitude`/`longitude`.

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
- **Out-of-region FTC teams are flagged, never dropped.** A team whose
  (cleaned) city is in `sources.ftcscout.OUT_OF_REGION_CITIES` (6 of
  152 FTC teams: Ensenada ×2, San Clemente, San Antonio, Louisville,
  Agoura Hills) is published with `Team.in_region = False`, not
  excluded. The set is a denylist, not an allowlist — an unrecognized
  new city defaults to `in_region=True`, which is the safer failure
  mode (a real San Diego community not yet seen must never be silently
  flagged out-of-region because it's missing from a hand-maintained
  list).
- **`sources.tba.SD_COUNTY_CITIES` must be an allowlist, unlike
  FTCScout's denylist above — and this is deliberate, not an
  inconsistency.** FTCScout's `region=USCASD` search endpoint already
  pre-filters to a rough San Diego-area geographic box, so its residual
  6-city denylist only needs to catch stragglers. TBA's `/api/v3/
  teams/{page}` has no region parameter at all — it enumerates every
  FRC team worldwide (~9,163) — so `sources/tba.py` must actively
  select the 59 that are in San Diego County, both by `state_prov ==
  "CA"` and by `city` matching this allowlist. An unrecognized San
  Diego city is a silent *undercount* here (the opposite failure mode
  from FTCScout's denylist), surfaced via `meta.by_league["FRC"]`
  reading lower than the issue's measured 59 — that count is the first
  place to check if this list ever needs a new entry.
- **`sources.tba.TBASource.discover()` raises on any probe failure; it
  does not degrade gracefully the way `adapters/tec.py`'s pagination
  probe does (falling back to "assume 1 page").** A missing/invalid
  `TBA_KEY`, a non-200/401 `/api/v3/status` response, or an unparseable
  body all raise `RuntimeError` from `discover()`. There is no sane
  page-count fallback for a credential failure — guessing would still
  401 on every subsequent page fetch, just less honestly. Raising here
  is exactly what lets `teams.pipeline.run_teams()`'s existing
  per-source try/except (ticket 011-002, unchanged by this ticket)
  isolate it: log, skip TBA, continue with whatever FTCScout already
  contributed. This is the mechanism that satisfies sprint.md's
  Migration Concerns — a missing/401 `TBA_KEY` degrades a `teams` run
  to FTC-only output, never aborts it — with **zero TBA-specific
  special-casing in `pipeline.py`** beyond registering the source in
  `_TEAM_SOURCES`. `tests/teams/test_pipeline.py`'s
  `TestTbaFailureIsolation` covers both cases end-to-end.
- **Cross-league organizational identity keys on normalized
  organization name, never on team number.** `teams.merge.merge_teams()`
  links `Team.org_key`/`sibling_team_ids` by
  `normalize.partners.normalize_org_name`-normalized `Team.organization`
  — reused directly, not reimplemented. `Team.team_id` already
  guarantees per-league uniqueness by construction
  (`f"{league.lower()}-{number}"`), so number collisions across leagues
  never produce a duplicate ID, but a naive number-based *link* would
  still be wrong: FTC 1622 and FRC 1622 are both real, both at Poway
  High School (a genuine dual-program link, correctly made by org
  name), while FTC 812 and FRC 812 are at *different* schools (measured
  — a number-based link would be actively wrong here, and org-name
  linking correctly makes none). Linking never fuses records — every
  `Team` a group produces stays a separate object; only `org_key` and
  `sibling_team_ids` are set. `Family/Community` and any other
  empty-`organization` team gets `org_key = ""` and is excluded from
  grouping entirely (never linked to anything, including other
  empty-organization teams) — without this, 58 unrelated FTC home teams
  would fuse into one bogus ~60-team "organization." See `merge.py`'s
  own module docstring for the full rationale and
  `tests/teams/test_merge.py` for the dual-program/never-groups/
  number-collision test cases.
- **`merge_teams()` runs once, after every source has completed and
  before `teams.geo.geocode_teams()` — never inside the per-source
  acquisition loop.** Cross-league
  identity needs the *combined* `Team[]` from every source that
  succeeded; running it per-source would see only one league at a time
  and could never link anything. `teams.pipeline.run_teams()` calls it
  exactly once, after the source loop, and does not wrap it in its own
  try/except — unlike source acquisition (network I/O, expected to
  fail sometimes), `merge_teams()` operates on already-validated
  in-memory `Team` objects and never raises for any input it can
  receive there.
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
- **Sources still never geocode.** Neither `sources/ftcscout.py` nor
  `sources/tba.py` resolves coordinates; both leave
  `Team.latitude`/`longitude`/`location_precision` at their dataclass
  defaults (`None`/`None`/`"none"`) and `teams.merge.merge_teams()`
  never touches them either. That is exclusively `teams.geo.
  geocode_teams()`'s job (this ticket), sequenced after both sources
  and after `merge_teams()` specifically because its offline ladder
  needs real `postal_code` values, which only TBA supplies at any real
  rate (ticket 011-003).
- **`teams.geo` is fully offline — zero network calls, structurally,
  not just by convention.** Measured before this ticket was built
  (`clasi/sprints/011-robot-teams/issues/robot-teams-scrape-locate-and-
  publish-san-diego-first-teams.md`'s Geocoding section): Nominatim/OSM
  resolved only 25 of 62 distinct school names (41% failure) and
  returned an HTTP 429 on a second machine's very first request; the US
  Census geocoder found 0 matches for a bare school name (it parses
  street addresses, which this project does not have). `teams/geo.py`
  therefore reads only the five committed files under `teams/data/`
  and never imports `partner_scrape.fetch` or any of Python's own
  networking modules (`urllib`, `http`, `socket`, ...) —
  `tests/teams/test_geo.py`'s `TestZeroNetworkCalls` enforces this by
  AST-scanning `geo.py`'s own source (matching
  `test_sources_base.py`'s forbidden-import-scan precedent) *and* by
  asserting `geocode_teams()`/`SchoolIndex.__init__()` accept no
  `Fetcher`-shaped parameter at all — not merely "an unused one," so a
  future edit cannot silently wire one in. The only thing in this
  subsystem that touches the network is `dev/refresh_school_
  directories.py`, a standalone script run by hand roughly yearly,
  never imported by `teams.geo` or `teams.pipeline`.
- **No LLM fallback for geocoding, ever — a wrong pin is worse than no
  pin.** A team that exhausts all seven of `teams.geo`'s rungs gets
  `location_precision: "none"` and no coordinates, full stop. This is
  tested directly (`tests/teams/test_geo.py`'s `TestRung7NoMatch`) and
  is why rung 7 exists as a real, exercised code path rather than an
  unreachable default.
- **`teams.geo`'s cache is in-memory, scoped to one `SchoolIndex`
  instance/one `run_teams()` call — deliberately not a disk-persisted
  cache modeled on `enrich/cache.py`.** `EnrichmentCache` exists to
  avoid *paying for* a repeated LLM call (real money, real latency);
  nothing in `teams.geo`'s matching costs either — it is a few hundred
  organizations compared against ~1,000 in-repo TSV rows, sub-second
  even uncached. A disk cache would add real complexity (schema
  versioning, content-hash invalidation, a `SCRAPE_CACHE_DIR`
  dependency this offline module would otherwise never need) for no
  measurable benefit. What *is* reused from that module's design is the
  shape "cache hits and misses alike, keyed by identity, not by
  record" — `SchoolIndex` caches rungs 1-4's outcome (hit **or**
  confirmed miss) keyed by `geo.normalize_school_name(Team.
  organization)` alone, per the issue's own measurement that 94
  school-named FTC/FRC teams collapse onto ~58 distinct campuses (a
  per-team cache would repeat ~40% of the matching work).
  `tests/teams/test_geo.py`'s `TestPerSchoolNotPerTeamCaching` proves
  this via `SchoolIndex.match_calls`, a counter incremented only on an
  actual (uncached) ladder run.
- **`needs_review` reflects the fuzzy match's actual Jaccard score, not
  which rung (3 vs. 4) accepted it.** A rung-3 (within-city, ≥0.60)
  match that happens to score ≥0.85 is not flagged; a rung-4
  (county-wide, ≥0.80) match at exactly 0.80 is. Below 0.85 the match
  still publishes — a flagged guess beats a silent one — exactly the
  mechanism that would catch "Classical Academy Online" (an online
  school with no campus) fuzzy-matching its sponsoring district's
  building at a 0.70 score without a human ever ratifying it.
  `Team.matched_name` is set on every resolved team regardless of
  precision (`"ZIP 92037 centroid"`, `"San Diego (city centroid)"`,
  or a real school name) so "why is this team here?" always has a
  string answer — never set (`""`) only when `location_precision ==
  "none"`.
- **Normalizing "Poway High School" to match CDE's own official "Poway
  High" required stripping a small, deliberately narrow stopword set
  (`"school"`/`"schools"`/`"sch"`/`"the"`), not a general fuzzy
  matcher.** Measured live building this ticket: without this, ~72 of
  117 school-precision matches (61%) scored 0.60-0.80 purely from CDE
  almost never writing the word "School" itself, flooding
  `needs_review` with matches that were actually exactly correct.
  Grade-level/type words (`"high"`, `"middle"`, `"elementary"`,
  `"senior"`) are deliberately **not** stripped — they distinguish two
  real, different schools at the same place name (e.g. "Poway High" vs.
  a hypothetical "Poway Middle") and dropping them would risk a false
  match, not just a noisy flag. After this fix, `needs_review` count
  dropped to 14 of 211 teams — a small, meaningful residue (genuine
  wording differences like "Senior"/"Early College", plus the
  "Classical Academy Online" case itself), not matcher noise.
  `geo.normalize_school_name` is a small, separately-named normalizer
  local to `teams/geo.py` — deliberately not
  `normalize.partners.normalize_org_name`, which is scoped to
  partner-directory organization names, not place names (see Design,
  below, for why the two must not be conflated).
- **`geo.py`'s loader independently re-checks `Virtual`/`StatusType`
  rather than trusting `dev/refresh_school_directories.py` was run
  correctly.** The committed `sd-schools-public.tsv` already excludes
  `Virtual in {"F", "V"}` rows and ships `StatusType == "Active"` rows
  only, but `SchoolIndex`'s own TSV loader re-applies both filters (the
  Virtual reject unconditionally; "prefer Active over Closed" as a
  per-normalized-name dedup) — defense in depth, and the only way
  `tests/teams/test_geo.py`'s `TestVirtualRowRejected` and
  `TestRung2ExactMatch::test_closed_row_never_wins_over_active` can
  exercise this behavior directly via a hand-built fixture, independent
  of whether today's real data file happens to need it.
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
  refresh annually; opportunities refresh weekly. A TBA auth failure
  (this ticket's `sources/tba.py`) must never sit inside the same
  process/exit code as the weekly opportunities export. `cli.py`'s
  `_run_teams()` never calls `run`/`pipeline.run()`, and
  `tests/test_cli_teams.py` asserts the isolation in both directions
  (`teams` never reaches `pipeline.run()`; the no-subcommand path never
  reaches `run_teams()`).
- **`export_teams()` drops `Team.sources` from the published field
  set**, the same way `export/writer.py`'s `SITE_SCHEMA_FIELDS` drops
  `Opportunity.sources` — cross-source acquisition bookkeeping (which
  source(s) contributed a record) has no counterpart in the site's
  schema. `teams/export.py`'s `TEAMS_SCHEMA_FIELDS` is derived from
  `dataclasses.fields(Team)` the same drift-proof way, so a new field
  (this ticket's `org_key`/`sibling_team_ids`, confirmed live: they now
  publish with no `export.py` change; ticket 011-004's `latitude`/
  `longitude`/`location_precision` next) is published automatically
  with no `export.py` change required.

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
`organization=""`, `org_type="family_community"` specifically so
`merge.py` (this ticket) can key cross-league identity on a non-empty
normalized organization name without accidentally fusing 58 unrelated
home teams into one bogus "Family/Community" organization.
`sources/tba.py` mirrors this for FRC: TBA has no equivalent sentinel,
but an unaffiliated team simply reports an empty `school_name`, which
maps the same way (`organization=""`, `org_type="unknown"`) — both
sources land in the same "never group" bucket `merge.py` checks
(`Team.organization == ""`), with no TBA-specific case in `merge.py`
itself.

**Why `teams.merge.merge_teams()` groups by `Team.organization ==
""` rather than a set of known sentinel values.** `merge.py` has no
knowledge of `"Family/Community"` or any other source-specific
sentinel — `_org_key()` only ever checks `if not team.organization`.
Each source is responsible for mapping its own "no real organization"
signal to an empty `Team.organization` at extraction time (see the
paragraph above); `merge.py` only needs to know that "empty" means
"never group," which keeps it source-agnostic and means a third future
source (e.g. increment 5's FLL static roster) needs no `merge.py`
change to get the same protection, only its own extraction-time
mapping to `organization=""` where appropriate.

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

**Why FTCScout/TBA share no extraction code beyond the `TeamSource`
protocol shape.** The two payloads are structurally unrelated
(FTCScout: REST search, thin fields; TBA: `/api/v3/teams/{page}`,
richer fields, `X-TBA-Auth-Key` header) — forcing a shared extraction
helper would couple two things that change for unrelated reasons.
`sources/base.py` supplies only the shared protocol shape
(`discover`/`fetch`/`extract` → `Team` objects) and a generic
`run()` chaining helper, matching `adapters.base.Adapter`/
`adapters.base.run()`'s shape closely enough to reuse the mental
model, deliberately not the type itself (see Constraints). Confirmed
true in practice, not just anticipated: `sources/tba.py` (this ticket)
shares zero helper functions with `sources/ftcscout.py` — only the
`TeamSource` protocol and `SOURCE_NAME`/`LEAGUE`/`PROGRAM` naming
convention.

**Why `teams.pipeline._TEAM_SOURCES` is a private local dict, not a
second `adapters.base.ADAPTERS`.** `sources.base.run()` deliberately
takes its `TeamSource` as an explicit argument rather than resolving
one from a shared table (see `sources/base.py`'s own docstring) — the
*caller* still needs some way to pick a `TeamSource` per Team Registry
entry's `adapter_type`, and `teams.pipeline` is that one caller.
`_TEAM_SOURCES` is not exported, not imported by anything else, and
provides no path from `partner_scrape.pipeline.run()` into this
subsystem — it is a plain lookup local to one function, not a
public, growable extension point like `ADAPTERS` is. This ticket adds
a `"tba"` entry here, and nothing else changed about the shape of
`_TEAM_SOURCES` itself.

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
(`ftc-sd.toml`, `frc-sd.toml`), and the operator-facing need is "run
only FTCScout" / "run only TBA" (e.g. to isolate a TBA outage) — a
property of *which acquisition method*, not which file. Filtering on
`SourceConfig.adapter_type` (`"ftcscout"`, `"tba"`) matches that need
directly.

**Why `teams.geo`'s seven rungs are ordered exact-cheapest-first, not
best-effort-in-parallel (this ticket).** `SchoolIndex._run_ladder()`
tries overrides, then an exact normalized-name match, before ever
computing a single Jaccard score — cheaper and strictly
higher-confidence checks should never be skipped in favor of a fuzzy
one that happens to run first. Rungs 3 (within-city, ≥0.60) and 4
(county-wide, ≥0.80) are two different *candidate pools* at two
different thresholds, not two different scoring functions — the same
`_best_token_match()` helper powers both, called once with a city
filter and once without. This mirrors the issue's own measured
methodology (Jaccard token-set matching, city-scoped before
county-wide) rather than the earlier difflib-ratio approach an even
earlier exploratory pass of the same issue tried and superseded.

**Why `geo.normalize_school_name()` is a separate function from
`normalize.partners.normalize_org_name()`, not a shared one (per
sprint.md's Design Rationale and this module's own docstring).** The
two solve different problems: `normalize_org_name` matches a scraped
organization string against the curated partner directory (drops a
leading "the ", nothing else); `normalize_school_name` matches a
team's self-reported school name against an *official government
directory's* naming conventions specifically — parenthetical asides
CDE writes into names (`"Feaster (Mae L.) Charter"`), and a small
institution-type stopword set (`"school"`, `"schools"`, `"sch"`,
`"the"`) that CDE systematically omits from its own records
(`"Poway High"`, never `"Poway High School"`). Importing
`normalize_org_name` and extending it in place would couple two
independently-changing concerns (partner-name matching, school-name
matching) into one function neither caller fully owns; keeping them
separate, even with a few lines of real duplication (both drop a
leading "the"), was the deliberate choice sprint.md's plan called for.

**Why the offline data provisioning script lives in `dev/`, not inside
`teams/` itself.** `dev/refresh_school_directories.py` is the only
thing in this whole subsystem that touches the network, and it is a
human-run, reviewed-before-commit tool (download, diff, commit) — not
part of any runtime code path. Placing it under `dev/` (matching this
project's existing convention: `dev/fetch_tec_api.py`,
`dev/export_site.py`, ...) rather than `teams/` makes that boundary
visible in the directory layout itself, not just in a docstring.

## 5. Interfaces

### Exposes
- **`model.Team`** — the record type: `team_id`, `league`, `program`,
  `number`, `name`, `organization`, `org_type`, `city`, `postal_code`,
  `latitude`, `longitude`, `location_precision`, `in_region`,
  `matched_name`, `needs_review` (this ticket), `website`,
  `website_status`, `organization_website`, `rookie_year`, `active`,
  `last_season`, `sponsors`, `org_key`, `sibling_team_ids`, `sources`.
  Every field defaults to an empty/neutral value; no `email` field
  exists (Constraints). Fields are populated incrementally across
  pipeline stages — `sources/ftcscout.py` and `sources/tba.py` set
  identity/organization/city/website/postal_code/sponsors/in-region
  fields; `teams.merge.merge_teams()` sets `org_key`/`sibling_team_ids`;
  `latitude`/`longitude`/`location_precision`/`organization_website`/
  `matched_name`/`needs_review` are set last, by this ticket's
  `teams.geo.geocode_teams()`.
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
- **`sources.tba.TBASource`** (this ticket) — the concrete `TeamSource`
  for The Blue Alliance's keyed v3 API. `discover()` probes `/api/v3/
  status` for `max_team_page`, then returns one `TeamRef` per `/api/v3/
  teams/{page}`; raises `RuntimeError` on any probe failure rather than
  degrading (Constraints). `extract()` filters each page to `state_prov
  == "CA"` and `city` in `SD_COUNTY_CITIES`. Config keys read from
  `SourceConfig.config`: `api_base` (default `config.get_tba_url()`).
  Auth via `config.get_tba_api_key()`, read fresh per call
  (`_auth_headers()`, matching `adapters/leaguesync.py`'s pattern).
- **`teams/registry/ftc-sd.toml`** / **`teams/registry/frc-sd.toml`**
  (the latter this ticket) — the FTCScout and TBA sources'
  `SourceConfig`s, loaded via `registry.loader.load_active_sources`
  pointed at `teams/registry/` (not the main
  `partner_scrape/registry/sources/` directory — a separate, disjoint
  registry namespace).
- **`merge.merge_teams(teams: list[Team]) -> list[Team]`** (this
  ticket) — sets `Team.org_key`/`sibling_team_ids` in place by grouping
  on `normalize.partners.normalize_org_name`-normalized
  `Team.organization`, skipping (never grouping) any team whose
  `organization` is empty. Mutates and returns the same list; called
  once by `teams.pipeline.run_teams()`, after every source has run and
  before `export_teams()`. See Constraints for the full identity rule
  and Design for why it keys on organization name, not team number.
- **`pipeline.run_teams(*, registry_dir=None, source=None, site_dir=None,
  fetcher=None, dry_run=False, geo_data_dir=None) -> dict`** — the
  programmatic entry point: loads the Team Registry (defaulting to the
  real seed, `teams/registry/`), dispatches each active source to its
  `TeamSource` via `_TEAM_SOURCES`, isolates any one source's failure
  (logged and skipped, matching `pipeline.run()`'s own SUC-008
  contract), links cross-league identity via `merge_teams()`, resolves
  every team's location via `teams.geo.geocode_teams()` (this ticket;
  `geo_data_dir` overrides the geocoding data directory, mainly for
  tests) over the combined result, and hands it to `export_teams()`.
  Returns that call's `{"meta": ..., "teams": [...]}` payload unchanged.
- **`teams.geo.geocode_teams(teams, *, data_dir=None) -> list[Team]`**
  (this ticket) — resolves every `Team` through the seven-rung offline
  ladder in place; returns the same list (parallel in shape to
  `merge_teams()`). `data_dir` defaults to `geo.DEFAULT_DATA_DIR` (the
  real committed `teams/data/`). Called once by `run_teams()`, after
  `merge_teams()` and before `export_teams()`.
- **`teams.geo.SchoolIndex(data_dir=None)`** (this ticket) — loads all
  five `teams/data/` files once and exposes `resolve(team)` (the full
  ladder for one `Team`, mutating it in place), `resolve_school(org,
  city)` (rungs 1-4, cached), `resolve_zip(postal_code)`/
  `resolve_city(city)` (rungs 5-6, uncached — already O(1) dict
  lookups), and `match_calls` (a counter of actual, uncached rungs-1-4
  ladder runs — what `tests/teams/test_geo.py`'s per-school-caching
  tests assert against). Raises `RuntimeError` if any data file under
  `data_dir` is missing or malformed — fails loudly at construction,
  per SUC-003's Error Flows ("a bad geocoding table is a build-time
  defect"). See Constraints for the caching design and Design for the
  rung ordering.
- **`teams.geo.normalize_school_name(name) -> str` /
  `normalize_city_name(city) -> str`** (this ticket) — the two
  normalizers `SchoolIndex` matches against; see Design for why these
  are separate from `normalize.partners.normalize_org_name`.
- **`export.export_teams(teams, site_dir=None, *, dry_run=False) -> dict`**
  — writes `{site_dir}/src/data/teams.json` as
  `{"meta": {...}, "teams": [...]}`. `meta` carries `generated`
  (timestamp), `total`, `by_league`, `out_of_region`, and
  `by_location_precision` — coverage/data-quality made visible in the
  artifact itself, not just a log line. `TEAMS_SCHEMA_FIELDS` (every
  `Team` field except `sources`) is the published field set, derived
  from `dataclasses.fields(Team)` so it can never drift — `org_key`/
  `sibling_team_ids` (this ticket) needed no `export.py` change to
  start being published, exactly as designed. Raises `RuntimeError` on
  an unwritable `site_dir`/`src/data`, matching `export_opportunities`'s
  loud-failure contract; `dry_run=True` computes and returns the
  payload without touching disk. **Never** writes or touches
  `opportunities.json`/`scrape-meta.json` (Constraints).
- **`partner-scrape teams [--dry-run] [--source ftcscout|tba]
  [--site-dir DIR] [--no-mirror] [-v]`** (`cli.py`) — the CLI entry
  point. Constructs a real `PoliteFetcher()` and calls `run_teams()`;
  unless `--dry-run`/`--no-mirror`, also calls `export.mirror_site_data`
  (reused, unmodified) against `config.get_mirror_site_dirs()`. Never
  calls `run`/`pipeline.run()` — see `cli.py`'s own module docstring
  and Constraints above.
- **`export/mirror.py`'s `MIRRORED_DATA_FILES`** — gained one entry,
  `"teams.json"`, in ticket 011-002; no change in this ticket. See
  `export/DESIGN.md`.
- **`teams/data/*`** (this ticket) — the five committed offline
  geocoding data files `teams.geo.SchoolIndex` reads:
  `sd-schools-public.tsv` (CDE public schools, San Diego County,
  `StatusType == "Active"`, `Virtual not in {"F","V"}`, 795 rows as of
  this ticket's build), `sd-schools-private.tsv` (NCES EDGE private
  schools, San Diego County, union of the 2021-22 and 2023-24 survey
  vintages, 213 rows), `zip-centroids.toml` (95 ZIP Code Tabulation
  Area centroids from the Census Bureau's own Gazetteer),
  `city-centroids.toml` (54 city/neighborhood centroids, derived from
  `sd-schools-public.tsv`'s own coordinates plus a documented ZIP
  fallback for the handful of San Diego neighborhoods CDE's `City`
  field does not distinguish from plain "San Diego" — see
  `dev/refresh_school_directories.py`'s own docstring), and
  `school-overrides.toml` (hand corrections, empty as of this ticket —
  the ladder's algorithmic rungs resolved the real 211-team corpus well
  enough that none has been needed yet). All five are plain data, never
  imported as Python.
- **`dev/refresh_school_directories.py`** (this ticket) — the
  standalone, human-run yearly refresh script that produces the four
  generated files above (not `school-overrides.toml`, which is
  hand-maintained only). The only network-capable code in this whole
  subsystem; never imported by `teams.geo` or `teams.pipeline`. See its
  own module docstring for the exact CDE/NCES/Census Gazetteer
  endpoints and filtering rules.

### Consumes
- **`registry.schema.SourceConfig` / `registry.loader.load_active_sources`
  (from `registry/`)** — reused verbatim for per-league source config;
  no new schema. See `registry/DESIGN.md`.
- **`normalize.partners.normalize_org_name` (from `normalize/`)** (this
  ticket) — `teams.merge`'s only edge into `normalize/`, read-only:
  organization-name normalization for cross-league linking, reused
  directly rather than reimplemented. This is a *new* caller of an
  *existing* function, not a new dependency on `normalize/run()` or any
  other part of that pipeline — `teams/` still has no edge into
  `enrich/`, `normalize.run()`, `pipeline.run()`, or either existing
  export writer (sprint.md's Impact on Existing Components). See
  `normalize/DESIGN.md`.
- **`fetch.Fetcher` (from `fetch/`)** — the protocol every `TeamSource`
  method takes as an explicit argument. Production wiring to a real
  `fetch.PoliteFetcher` instance happens in `cli.py`'s `_run_teams()`
  handler, passed through `teams.pipeline.run_teams()`'s `fetcher`
  parameter — nothing in `teams/sources/` or `teams/pipeline.py`
  constructs a concrete fetcher's default itself except that one CLI
  call site, matching `adapters/leaguesync.py`'s convention of taking
  `Fetcher` as a parameter. See `fetch/DESIGN.md`.
- **`config.get_site_dir()` / `config.get_mirror_site_dirs()` /
  `config.get_tba_api_key()` / `config.get_tba_url()` (from
  `config.py`)** — the last two, this ticket, mirror
  `get_leaguesync_api_key()`/`get_leaguesync_url()` line-for-line,
  including the SOPS-decrypted-secret quote-stripping; `config.py`
  remains the only module reading `os.environ`. The site-dir/mirror
  accessors are ticket 011-002's, reused unmodified. See the root
  `partner_scrape/DESIGN.md`.
- **`export.mirror_site_data` (from `export/`)** — reused, unmodified,
  to propagate `teams.json` into extra checkouts. See `export/DESIGN.md`.

## 6. Open Questions / Known Limitations

- The site pages do not exist yet — this doc now describes what
  tickets 011-001 through 011-004 built (model + FTCScout + TBA +
  export + CLI + merge + offline geocoding); see `sprint.md`'s Tickets
  table for the remaining ticket (011-005).
- **`school-overrides.toml` ships empty as of this ticket.** The
  algorithmic rungs (exact match + the stopword-normalized Jaccard
  fuzzy tiers) resolved the real 211-team corpus well enough that no
  hand correction was needed — 129 teams reached school precision with
  only 14 flagged `needs_review`, and none of those 14 were bad enough
  to warrant a hand override rather than just a flag (each is a real,
  explainable wording difference — "Senior" vs. not, "HS" vs. spelled
  out, or the genuinely-ambiguous "Classical Academy Online" case).
  Future refreshes or a larger corpus (FLL, a follow-on sprint) may
  surface real residue; add entries there once a human has verified a
  specific coordinate, per that file's own header comment.
- **Two ambiguous out-of-region city names are deliberately
  unresolved.** FTCScout's `region=USCASD` search returned one team
  each reporting `city == "San Antonio"` and `city == "Louisville"` —
  real US place names that exist in many states, with no way to tell
  which one FTCScout means from the data available. `city-
  centroids.toml` has no entry for either, so both fall through to
  `location_precision: "none"` rather than guessing a specific city
  (Texas? California? Kentucky?). `"Ensenada"` (Mexico) is similarly
  unresolved — outside US Census/CDE coverage entirely, not a matcher
  gap. All three are in `sources.ftcscout.OUT_OF_REGION_CITIES`, so
  they are correctly flagged `in_region = False` regardless of
  location precision. See `dev/refresh_school_directories.py`'s
  docstring for the same reasoning applied to `city-centroids.toml`'s
  construction.
- **`Team.organization_website` is populated from CDE's `WebSite`
  column on a school-precision *public*-school match only** — NCES's
  private-school geocode data carries no website field at all, so a
  private-school match never sets it (confirmed: 88 of the 117
  school-precision FTC teams and 11 of the 44 FRC ones got a real
  `organization_website` at this ticket's build; the private-school
  gap accounts for the rest). Not a gap in the matcher — there is
  simply nothing to carry over from that source.
- **The ZIP/city centroid tables cover what this ticket's real 211-team
  corpus and `sources.tba.SD_COUNTY_CITIES`'s full allowlist need, not
  a hand-picked "~38"/"~25" count the issue's early estimate
  mentioned.** `dev/refresh_school_directories.py` derives 95 ZIP
  centroids (every ZIP appearing in `sd-schools-public.tsv`, a
  reproducible superset rather than a curated subset) and 54 city
  centroids (every CDE `City` value plus the documented neighborhood/
  out-of-region additions) — broader coverage costs nothing at runtime
  (an unused entry is simply never looked up) and reduces the chance a
  future real team falls through to a coarser rung than it should.
- `teams.pipeline.run_teams()`'s per-source failure isolation (logged
  and skipped) is now load-bearing in production, not just tested via
  a synthetic double: `sources.tba.TBASource.discover()` raises on a
  missing/invalid `TBA_KEY` or a non-200/401 `/api/v3/status` response
  by design (Constraints), and `tests/teams/test_pipeline.py`'s
  `TestTbaFailureIsolation` exercises both cases end-to-end. This is
  the real mechanism `TBA_KEY` not yet being in GitHub Actions repo
  secrets (sprint.md's Migration Concerns) depends on until an operator
  pushes it.
- `sources.ftcscout.OUT_OF_REGION_CITIES` is a small hand-maintained
  denylist derived from one live measurement (2026-08-27).
  `sources.tba.SD_COUNTY_CITIES` is the equivalent allowlist for TBA —
  see Constraints for why TBA needs an allowlist where FTCScout needs
  only a denylist. Both remain in place, unsuperseded: `teams.geo`'s
  CDE/NCES-driven ladder resolves *where* a team is, but `in_region`
  (whether it counts as San Diego County at all) is still these two
  lists' job — `geo.py` never sets or reads `in_region` (Constraints).
- `sources.tba.SD_COUNTY_CITIES` was assembled from this project's own
  historical FRC roster (`data/robot-teams.json`) plus every
  incorporated San Diego County city, not from a live capture of TBA's
  current data (no network access during this ticket's build — see
  `tests/teams/test_sources_tba.py`'s module docstring). A San Diego
  city genuinely present in TBA's live data but missing from this list
  would silently undercount; `meta.by_league["FRC"]` reading below the
  issue's measured 59 on a real run is the signal to check this list
  first.
- `FTCScoutSource.fetch()` does not send any auth header (FTCScout
  needs none) — unlike `adapters/leaguesync.py`'s Bearer-token pattern
  and unlike this ticket's `TBASource.fetch()`, which does.
- `teams.merge.merge_teams()` links strictly pairwise-by-group; unlike
  `teams.geo`'s fuzzy school matching (`needs_review: true` below a
  0.85 Jaccard score, this ticket), it has no notion of merge
  *confidence* at all — `merge.py` only ever compares exact normalized
  organization names, never fuzzy-matches two differently-worded
  organization strings. Two organizations whose names normalize
  identically but are not actually the same real-world organization
  (not observed in the 152+59 fixture corpus, but not structurally
  impossible with a larger live roster) would link — there is no
  manual-override mechanism (a `school-overrides.toml`-style table) for
  `merge.py` today.
- Whether `teams.json` is ever joined to the curated partner directory,
  and whether LLM-assisted website discovery is added later, are both
  explicitly out of scope for the whole sprint, not just this ticket —
  see `sprint.md`'s Design Rationale and Scope.
