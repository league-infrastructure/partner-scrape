<!--
DRAFT — sprint 011 planning-time content, not yet applied.

This file is NOT a seeded overlay of an existing canonical doc — no
canonical `partner_scrape/teams/DESIGN.md` exists yet, because the
`partner_scrape/teams/` directory doesn't exist yet. It therefore
cannot go through `seed_sprint_design_overlay`/`generate_diffs` (a
diff needs a pristine baseline to diff against) and is deliberately
kept in this `new-subsystem/` subdirectory rather than the flat
`design/` overlay directory, so `clasi design validate` (which only
inspects `design/`'s direct `.md` children) does not try to resolve it
against the canonical doc set or demand a `.diff.md` sibling it cannot
have.

Ticket 001's acceptance criteria require writing this content to its
final co-located path, `partner_scrape/teams/DESIGN.md`, once the
module exists — refreshed against the actual code at that point
(bootstrap-design's "describe reality, not aspiration" rule), not
copied verbatim from this pre-code draft. Written to the packaged
`clasi.design.store.subsystem_template()` structure so that refresh is
a content edit, not a restructuring.
-->

# teams

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 (planning draft — refresh once built) · **Status:** in-flux

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

A second, independent pipeline, invoked by its own CLI subcommand
(`partner-scrape teams`), not by `pipeline.run()`:

```
registry.load_active_sources()        reused verbatim, teams/registry/*.toml
   ↓
sources/{ftcscout,tba}.py             TeamSource protocol (not adapters.base.ADAPTERS)
   ↓
merge.py                              cross-league organizational identity
   ↓
geo.py + data/                        offline resolution ladder (7 rungs)
   ↓
export.py                             writes {site_dir}/src/data/teams.json
   ↓
pipeline.py  run_teams()              sequences the above for one CLI invocation
```

`cli.py`'s `teams` subcommand calls `run_teams()` and, unless
`--no-mirror`, `export.mirror_site_data` (reused from `export/`) —
mirroring how the main `run` subcommand sequences
`pipeline.run()`/`mirror_site_data` today, but as a fully separate
invocation with its own exit status.

**Two structured sources, deliberately asymmetric in richness.**
FTCScout (`api.ftcscout.org`, free, unauthenticated) returns 152 San
Diego FTC teams with city and (62% of the time) a school name, but no
website and no ZIP. The Blue Alliance (`thebluealliance.com/api/v3`,
keyed via `config.get_tba_api_key()`) returns 59 FRC teams with much
richer fields — 91% school name, 83% ZIP, 72% website. `sources/base.py`
defines the shared `TeamSource` protocol; `sources/ftcscout.py` and
`sources/tba.py` each implement it independently — there is no shared
extraction logic between them beyond the protocol shape, since the two
APIs' payloads share almost no field names.

**Location precision is a first-class, honestly-reported property, not
an implementation detail.** Every `Team` carries a `location_precision`
(`school | zip | city | none`) stamped by whichever rung of `geo.py`'s
ladder resolved it. This is the subsystem's central design commitment:
`site/src/data/partners.json` has a live, unnoticed bug today (7
partner records sit on Google's bare-string-"California" centroid;
15 more silently fall outside the map's bounding box and are dropped)
caused by storing coordinates with no record of how precise they are.
`teams/` is built specifically not to repeat that.

## 3. Constraints and Invariants

- **Never register with `adapters.base.ADAPTERS`.** A team source
  registered there would become reachable from `pipeline.run()`, which
  would hand a `Team` object to `normalize.run()` — a type it does not
  expect — and crash. The `TeamSource` protocol is deliberately a
  separate, unregistered shape. Do not "simplify" by merging the two
  protocols; that removes the type-safety boundary this rule exists
  for.
- **`geo.py` never calls an LLM, and never will.** A wrong coordinate
  on a public map is worse than no coordinate, and nothing downstream
  can verify an LLM-guessed one. A team that exhausts all seven rungs
  of the ladder gets `location_precision: none`, not a fallback guess.
  This is not a cost-cutting measure to relax later — it is the
  subsystem's core promise (see `sprint.md`'s Design Rationale, "never
  guess").
- **`geo.py` performs no network I/O, ever.** Every rung reads only its
  own committed data files (`data/sd-schools-public.tsv`,
  `data/sd-schools-private.tsv`, `data/zip-centroids.toml`,
  `data/city-centroids.toml`, `data/school-overrides.toml`) and
  `dev/refresh_school_directories.py` is a separate, manually-run,
  yearly script — never invoked from the pipeline itself.
- **`export.py` never writes to `opportunities.json` or
  `scrape-meta.json`.** These are `export/writer.py`'s exclusive
  outputs; `scrape-meta.json` in particular carries the opportunities
  export's timestamp, and a `teams` run overwriting it would make the
  site falsely claim opportunities were just refreshed. `teams/export.py`
  writes only `teams.json`, with its own `meta.generated` timestamp.
- **No `email` field, structurally.** The FLL seed this subsystem may
  later ingest (a follow-on sprint, not this one) carries 40 email
  addresses including personal coach Gmail accounts; the `Team` model
  has no field to put one in, and an export test asserts no key or
  value in `teams.json` matches an email pattern. This is a stronger
  guarantee than "we chose not to publish it" — there is structurally
  nowhere for it to go.
- **Cross-league merge never groups `Family/Community`/empty
  organizations.** Roughly 56 FTC teams carry no real organization
  string; grouping them by a shared blank/placeholder value would fuse
  unrelated home teams into one bogus ~100-team "organization" in
  `merge.py`'s output. Every real merge must key on a non-empty
  normalized organization name.
- **Out-of-region teams are flagged, never dropped.** A team whose
  city falls outside San Diego County (Ensenada, San Clemente, Agoura
  Hills, etc. — 6 of the initial 152 FTC teams) is published with
  `in_region = false` and counted in `meta`, not silently excluded. A
  silent drop is invisible to whoever is watching for it; a flagged
  count is not.
- **Deliberate non-goal — no join to `partners.json` this sprint.**
  Only 1 of 105 distinct team organizations is already a curated
  partner. `teams.json` stands alone; do not add a partner lookup here
  without a separate design decision (see `sprint.md`'s Design
  Rationale).
- **Deliberate non-goal — no LLM website discovery this sprint.**
  Deterministic tiers only (TBA's own `website` field, the hand-curated
  seed with liveness checks, CDE's matched `WebSite` as a distinct
  `organization_website` field). An LLM-driven search is a possible,
  explicitly-flagged future increment, not part of this subsystem as
  built.

## 4. Design

**Why cross-league identity keys on normalized organization name, not
team number.** Team number 1622 exists independently in both FTC and
FRC — keying on number would actively merge two unrelated teams. Seven
real organizations (Canyon Crest Academy, Francis Parker, Poway,
Coronado, Del Norte, La Jolla Senior, North County Trade Tech) run
teams in both programs and should link. `merge.py` reuses
`normalize.partners.normalize_org_name` (lowercasing, punctuation
stripping, leading-"the" removal) rather than writing a second,
independently-drifting normalizer — the two subsystems' notion of "the
same organization, written two ways" must not diverge.

**Why the geocoding ladder is ordered the way it is.** Highest
precision first, each rung stamping `location_precision`:
`school-overrides.toml` (hand corrections) → CDE+NCES exact normalized
match → token-set match within city (Jaccard ≥ 0.60) → token-set match
county-wide (Jaccard ≥ 0.80) → ZIP centroid → city centroid → no match.
CDE (California's public-school directory, ~924 active SD rows with
coordinates) and NCES EDGE (179 SD private schools, unioning the
2021-22 and 2023-24 survey vintages since individual vintages drop
non-responding schools) were chosen over live geocoding after live
measurement: Nominatim resolved only 59% of distinct FTC school names
within the county and returned an HTTP 429 on a second machine's very
first request. A fuzzy match scoring below 0.85 sets `needs_review:
true` rather than publishing silently — catches cases like an online
school fuzzy-matching its sponsoring district's physical building.
Caching is per resolved school (94 school-named teams collapse to ~58
distinct campuses), not per team, and negative results are cached too,
or the ~14 unresolvable org-named teams rescan the full index every
run.

**Why the FTCScout/TBA source split has no shared extraction code.**
The two payloads are structurally unrelated (FTCScout: REST search,
thin fields; TBA: `/api/v3/teams/{page}`, rich fields, Bearer auth) —
forcing a shared extraction helper would couple two things that change
for unrelated reasons (a FTCScout API change has zero chance of
affecting TBA parsing). `sources/base.py` supplies only the shared
`TeamSource` protocol shape (`discover`/`fetch`/`extract` → `Team`
objects), matching `adapters.base.Adapter`'s shape closely enough to
reuse the mental model, deliberately not the type itself (see
Constraints).

**Why FTCScout uses its REST endpoint, not GraphQL.** The `Fetcher`
protocol (`fetch/fetcher.py`) is GET-only; adding a `post()` method
would ripple into every `FixtureFetcher` test double in the suite for
one source's benefit.

**Why the seed (`data/robot-teams.json`) is not read by anything in
this sprint's build of the subsystem.** Its FLL-roster import is a
deferred follow-on sprint's work (see `sprint.md`'s Goals). When it
lands, the design intent is an *overlay*, never an *override*: it
supplies only fields no live source carries, and only where the live
value is currently empty — a live value always wins, since a stale
override is a worse failure mode than a missing field because it is
invisible.

## 5. Interfaces

### Exposes
- **`partner-scrape teams [--dry-run] [--source ftcscout|tba]
  [--site-dir DIR] [--no-mirror] [-v]`** — the CLI entry point.
  `--source` restricts to one acquisition source (useful for isolating
  a TBA outage); omitted, both run. `--dry-run` computes and reports
  without writing.
- **`pipeline.run_teams(...) -> dict`** — the programmatic entry point,
  sequencing sources → merge → geocode → export; returns a summary
  (team counts by league, out-of-region count, unresolved-location
  count) matching `publish.project()`'s existing "return a summary"
  convention in `export/`.
- **`{site_dir}/src/data/teams.json`** — the published contract: a
  `meta` envelope (`generated`, per-league counts, out-of-region count,
  unresolved count) plus a `teams` array. Mirrored into extra checkouts
  by `export.mirror_site_data` (reused, unmodified) via
  `MIRRORED_DATA_FILES`.
- **`model.Team`** — the record type: `team_id`, `league`, `program`,
  `number`, `name`, `organization`, `org_type`, `city`, `postal_code`,
  `latitude`, `longitude`, `location_precision`, `in_region`, `website`,
  `website_status`, `organization_website`, `rookie_year`, `active`,
  `last_season`, `sponsors`, `org_key`, `sibling_team_ids`, `sources`.
  No `email` field (Constraints).

### Consumes
- **`registry.schema.SourceConfig` / `registry.loader.load_active_sources`
  (from `registry/`)** — reused verbatim for per-league source config;
  no new schema. See `registry/DESIGN.md`.
- **`fetch.PoliteFetcher` (from `fetch/`)** — the only network access
  this subsystem performs, matching the rest of the codebase's "one
  network seam" convention. See `fetch/DESIGN.md`.
- **`config.get_tba_api_key()`/`get_tba_url()` (from `config.py`)** —
  the only credential this subsystem needs; `config.py` remains the
  sole `os.environ` reader. See the root `partner_scrape/DESIGN.md`.
- **`normalize.partners.normalize_org_name` (from `normalize/`)** — the
  one function reused for cross-league identity matching. This is the
  subsystem's only edge into `normalize/`; it does not call
  `normalize.run()` and is not called by it. See `normalize/DESIGN.md`.
- **`export.mirror_site_data` (from `export/`)** — reused, unmodified,
  to propagate `teams.json` into extra checkouts. See `export/DESIGN.md`.

## 6. Open Questions / Known Limitations

- Whether `teams.json` is ever joined to the curated partner directory
  (104 of 105 team organizations are not currently partners — a
  candidate recruitment list) is an open product question, not resolved
  by this sprint.
- LLM-assisted website discovery (behind an explicit flag, two
  independent-signal acceptance, host-uniqueness rejection) is a
  possible future increment; not built this sprint. Realistic yield
  estimated at 55-70% of sites that actually exist, ~$8 per cold run
  via Anthropic's server-side `web_search` tool.
- The FLL static roster (48 teams, hand-maintained, PII-bearing,
  hard 2026-27 expiry) is deferred to a follow-on sprint — see
  `sprint.md`'s Goals for the full scope-decision rationale.
- `TBA_KEY` is provisioned and verified locally but not yet present in
  the scheduled workflow's GitHub Actions secrets — the FRC portion of
  a scheduled `teams` run will fail (isolated, not fatal to the whole
  run — see Constraints) until an operator pushes it.
