---
status: done
sprint: '011'
tickets:
- 011-001
- 011-002
- 011-003
- 011-004
- 011-005
---

# Robot Teams: scrape, locate, and publish San Diego FIRST teams

## Description

The site covers **partners** (organizations) and **opportunities** (dated events). It has nothing
about the ~250 FIRST robotics teams in San Diego County — who they are, where they are, or how to
reach them.

Build a refreshable pipeline that pulls live team rosters (FLL / FTC / FRC), locates each team as
precisely as public data allows, and publishes browsable team pages on the site.

### Source availability (probed live 2026-08-28)

| Source | Teams | Coverage |
|---|---|---|
| **FTC** — FTCScout, free, no auth. REST `GET api.ftcscout.org/rest/v1/teams/search?region=USCASD` | **152** | 100% city, 62% school name, **0% website**, 0% ZIP |
| **FRC** — The Blue Alliance, `X-TBA-Auth-Key`. Enumerate `/api/v3/teams/{page}`, filter CA + SD cities | **59** | 91% school name, **83% ZIP**, **72% website** |
| **FLL** — no public API exists | 48 | hand-maintained export only; program ends after 2026-27 |

The two live sources are asymmetric, and this drives the design: **TBA is rich, FTCScout is thin.**
FRC records carry a postal code and a website; FTC records carry a city and maybe a school name.
`TBA_KEY` is provisioned in `.env` and `config/prod/secrets.env` (SOPS) and is verified working.

### Geocoding: measured options

- **Nominatim/OSM** — 62 distinct FTC school names, county-bounded, 1.15s spacing: **25 resolved, 36
  did not (41%)**. Normalizing truncated names recovered zero more. A second machine received **HTTP
  429 on its first request**. Inaccurate here and operationally unreliable.
- **CDE public-school directory** (`cde.ca.gov/schooldirectory/report?rid=dl1&tp=txt`, 8.8 MB TSV,
  18,397 rows) carries `School / District / City / Zip / WebSite / Latitude / Longitude`. Filtered to
  active San Diego County schools with coordinates: **~800 rows**. Three-tier matcher
  (exact-normalized → token-subset → difflib ≥ 0.87) resolves **FTC 64/94 (68%), FRC 38/54 (70%)**,
  offline, with no runtime network call. **This is the one to use.**
- CDE's **private**-school file (`privateschooldata2526.xlsx`) carries CDS code, county, name, and
  enrollment/staffing but **no address and no coordinates** — useful as a validated name list (219 SD
  private schools), not as a geocoding source.
- **NCES EDGE private-school locations** *do* close that gap: ArcGIS REST,
  `.../EDGE_GEOCODE_PRIVATESCH_2324/MapServer/0/query?where=STFIP='06'` — 2,335 geocoded CA private
  schools, **179 in San Diego County, all 179 with coordinates**. Federal public-domain, paginated
  JSON, no key. PSS is a *survey*, so non-responding schools drop out of individual vintages
  (Pacific Ridge School is absent from 2023-24 but present in 2021-22) — **union the 2021-22 and
  2023-24 vintages**.
- TBA's `lat` / `lng` / `address` / `location_name` / `gmaps_place_id` are documented in its own
  OpenAPI spec as *"Will be NULL, for future development"* — confirmed NULL for all 59 SD teams.

With CDE + NCES unioned, normalized token-set matching (Jaccard ≥ 0.60 within city, ≥ 0.80 county-wide)
resolves **52 of 64 distinct targets → 77 of 94 school-named teams**, rising to ~80 with two known
matcher fixes: strip CDE's `Surname (Given Name)` parentheticals (`Feaster (Mae L.) Charter`), and
union the PSS vintages. The ~14 that remain are org-named teams no school directory contains
(`D Robotics Education`, `Girls Clubs of America`, `The League of Amazing Programmers`) plus two
Mexican schools — not matcher failures.

Expected placement across ~259 teams:

| Precision | Teams | How |
|---|---|---|
| School (campus rooftop, ±50 m) | ~118 | CDE + NCES match (~80 FTC, ~38 FRC) |
| ZIP centroid (1–3 sq mi urban) | ~15 | FRC `postal_code` where no school matched |
| City centroid | ~120 | `Family/Community` teams, org-named teams, all 48 FLL |
| Out of region | 6 | Ensenada ×2, San Clemente, San Antonio, Louisville, Agoura Hills |

"Geocode every school" is not "locate every team": **56 FTC teams are `Family/Community`** and stay at
city precision regardless of how good the school data gets.

**The map must not lie about this.** Of the city-precision cohort, **40 FTC teams collapse onto the
single "San Diego" centroid** — a 372 sq mi city, so a Rancho Peñasquitos team would render ~18 miles
from its real location. Do not jitter (it fabricates precision and changes every regeneration) and do
not use a plain cluster marker (it implies the centroid means something). Render one labelled badge
per city — `San Diego — 40 teams`, visually distinct from precise markers, opening a list rather than
a popup.

**Precedent for why `location_precision` is mandatory:** `site/src/data/partners.json` has this bug
today. **7 records carry exactly `36.778261, -119.417932`** — Google's geocoder centroid for the bare
string `"California"` — including Olivewood Gardens, San Diego Automotive Museum, Media Arts Center
San Diego, and iFLY San Diego, all genuinely local. A further **15 fall outside the map's bounding box
and are silently dropped** by the `return` at `site/src/pages/partners/index.astro:90`. That is an ~8%
silent-failure rate caused by storing coordinates with no record of how precise they are.

## Cause

Two things make this urgent rather than merely nice to have.

**FIRST LEGO League is ending.** LEGO declined to renew its 28-year FIRST partnership on 2026-03-19,
making **2026-27 the last FLL season ever**. San Diego's FLL coaches, judges, and venues become free
agents after it. `robot-team-analysis/robot-team/coaches-network-launch.md` identifies convening them
— league-neutral, *before* they individually pick a successor — as the highest-leverage available
move, and a public, accurate team directory is the artifact that makes that convening credible.

**The existing data is a dead end.** `data/robot-teams.json` holds 254 records hand-assembled from
three manually-maintained files in the sibling `robot-team-analysis` repo. It has **no coordinates at
all**, 55% of records show nothing more precise than "San Diego", there is no refresh path, and
nothing in this codebase references it — it is an unwired drop-in.

## Proposed fix

A new module, `partner_scrape/teams/`, with its own model, pipeline, and exporter — reusing the
existing fetch/cache/export machinery but **not** the `Opportunity` model.

**Why a separate model:** `export/writer.py:50` filters to current-and-upcoming records and drops
anything undated. A team is a standing entity with no date, so routing teams through `Opportunity`
would filter every one of them out at export. Widening `model.Kind` with `"team"` would also ripple
into `enrich/enricher.py`, `normalize/run.py`, and `export/writer.py` to gain nothing.

### Layout

```
partner_scrape/teams/
  model.py                        Team dataclass + identity/merge keys
  sources/{base,ftcscout,tba,static_roster}.py
  geo.py                          offline resolver: CDE + NCES + ZIP + city
  merge.py                        cross-source and cross-league identity
  export.py                       writes {site_dir}/src/data/teams.json
  pipeline.py                     run_teams()
  registry/{ftc-sd,frc-sd,fll-sd}.toml
  data/{sd-schools-public.tsv,sd-schools-private.tsv,school-overrides.toml,
        zip-centroids.toml,city-centroids.toml}
dev/refresh_school_directories.py yearly manual CDE + NCES refresh
```

Team sources use a parallel `TeamSource` protocol, **not** `adapters.base.ADAPTERS` — registering
there would make a team source loadable by `pipeline.run()`, which would hand `Team` objects to
`normalize.run()` and crash. Keep the namespaces disjoint. Reuse `registry.schema.SourceConfig` and
`registry.loader.load_active_sources` verbatim; both are already league-agnostic.

Use FTCScout's **REST** endpoint, not GraphQL: the `Fetcher` protocol is GET-only, and adding `post()`
would break every `FixtureFetcher` double in the suite.

### Reused, not rebuilt

- `fetch/cache.py::PoliteFetcher` — robots, throttle, conditional GET, disk cache.
- `config.py` — add `get_tba_api_key()` / `get_tba_url()` mirroring `get_leaguesync_api_key()`
  exactly, including the dotconfig quote-stripping. `config.py` stays the only module reading
  `os.environ`.
- `export/mirror.py` — add `"teams.json"` to `MIRRORED_DATA_FILES`, and call `mirror_site_data()` from
  the new subcommand (it is currently only called on the `run` path). Without this the beta site
  serves nothing — the exact staleness bug that module exists to fix.
- `normalize/partners.py::normalize_org_name` — for org matching; do not write a second normalizer.
- `observability/` YieldReporter; the fixture/no-network test convention.

### Team model

Key fields: `team_id` (`"{league}-{number}"`), `league`, `program`, `number`, `name`, `organization`,
`org_type`, `city`, `postal_code`, `latitude`, `longitude`, `location_precision`
(`school|zip|city|none`), `in_region`, `website`, `website_status`, `organization_website`,
`rookie_year`, `active`, `last_season`, `sponsors`, `org_key`, `sibling_team_ids`, `sources`.

**No email field, deliberately.** The seed carries 40 addresses, 6 of them volunteer coaches' personal
Gmail accounts, and its own `meta.warning` says not to publish it. Home addresses are not a concern —
we hold none — but a parent's personal email on a public page is a different thing. Omitting the field
makes leaking one structurally impossible; an export test asserts no key or value in `teams.json`
matches an email pattern.

### Location resolution — fully offline

Ladder, highest precision first, each rung stamping `location_precision`:

1. `school-overrides.toml` (hand-corrections for the residue) → school
2. CDE **and NCES** exact normalized name, city-filtered when ambiguous → school
3. Token-set match, Jaccard ≥ 0.60 within the same city → school
4. Token-set match, Jaccard ≥ 0.80 county-wide → school
5. ZIP centroid from `postal_code` (38 distinct ZIPs, static table) → zip
6. City centroid (~25-city table) → city
7. No match → leave blank

**Rung 7 is deliberate: never guess.** A wrong pin is worse than no pin — which is also why an LLM
must not be asked for coordinates; it will emit plausible wrong values nothing downstream can catch.

Committed data files: `sd-schools-public.tsv` (CDE, ~924 active SD rows with coordinates — reject
`Virtual` rows, prefer `StatusType == "Active"`); `sd-schools-private.tsv` (NCES EDGE, 179 SD rows,
**union of the 2021-22 and 2023-24 vintages**); `school-overrides.toml`; `zip-centroids.toml`;
`city-centroids.toml`.

Any fuzzy match scoring below 0.85 sets `needs_review: true` and surfaces in the yield report instead
of publishing silently — that catches cases like `Classical Academy Online`, an online school with no
campus that fuzzy-matches its sponsoring district's building at 0.70. Keep `matched_name` on every
record so "why is this team here?" has a string answer rather than a guess. Cache **per resolved
school, not per team** (94 school-named teams collapse to ~58 distinct campuses), and cache negatives
too, or the ~14 unresolvable org-named teams rescan the index every run.

City strings need normalization first (`"La Jolla "`, `"carlsbad"`, `"san diego"` are distinct in the
live data; normalization collapses FTC's 27 raw strings to 24). Out-of-county teams (Ensenada, San
Clemente, Agoura Hills — 6 of 152) get `in_region = false` and are **flagged, not dropped**; silent
drops are invisible to an operator, and a count in `meta` makes a sudden jump detectable.

### Websites — what will and will not work

**The structured sources are dead — measured, not assumed.** FTCScout's `website` field is empty
*nationally*: across nine regions (USCASD, USCALA, USTX, USMI, USNY, USCHS, USNC, USWA, USMN),
**0 of 3,412 teams** have a non-null website. FIRST publishes none either — `ftc-events`
team pages render an "On The Web:" heading with nothing under it even for long-established teams, the
official API has no `website` field at all, and the page source says *"PLEASE DO NOT SCRAPE WEBPAGES
FOR EVENT DATA"*. And the "go through the online rosters" idea does not survive contact: `sdftc.org`
publishes roster pages, but **the only external link on any of them is a Font Awesome CSS include** —
there are no team websites there to harvest.

**Correction worth recording: an unattended pipeline *can* search the web.** Anthropic's Messages API
provides a server-side `web_search` tool that runs on Anthropic's infrastructure, so a cron job gets
real, cited results with no interactive session. Cost is **$10 per 1,000 searches**, and
`usage.server_tool_use.web_search_requests` makes spend measurable. Two caveats: dynamic filtering
requires Claude 4.6+, while `enrich/llm_client.py::MODEL_ID` is pinned to `claude-haiku-4-5` (give
discovery its own model constant rather than repinning the enricher); and server-tool errors return
**HTTP 200 with an error object** where a list is expected, so branch before indexing.

**But viability is not the same as value.** Two live searches bracket the outcome: FTC 4216 "Rise of
Hephaestus" surfaced `roh4216.weebly.com` — exactly the URL a human curated into the seed — while FTC
3712 "Purple F.E.A.R." has no site at all, and every result was either an aggregator or **a different
team's website**. A naive "first non-aggregator result" heuristic attaches High Voltage's site to
Purple F.E.A.R. Realistic yield is **55–70% of the sites that exist**, roughly 20–35 net new over the
hand-curated set, for ~$8 a cold run. Roughly 100 of the 254 teams have no website because none
exists — for the 56 `Family/Community` teams especially.

Ship deterministic tiers first: TBA `website` for FRC (43 teams, free, already in the payload); the 68
hand-collected websites in the seed, matched by team id, with a liveness check demoting dead links; the
matched CDE row's `WebSite` as a **separate** `organization_website` field (never present a school
homepage as the team's own). Also ingest FTCScout's `sponsors`, populated for **49 of 152** teams and
already in the response — free profile content currently thrown away.

If search-based discovery is built, it goes behind an explicit flag, and **the LLM proposes while
deterministic Python disposes**. Accept only on two independent signals (team number in host or path,
nickname in host/`<title>`/`<h1>`, number adjacent to "FTC"/"FIRST" in the body, school or city named),
and reject unconditionally when: the host is a known aggregator; **the host matches a school website
from CDE's `WebSite` column** and the number/nickname test fails; or **the host is already assigned to
another team this run** (host-uniqueness catches the Purple F.E.A.R. case in one line). Fetch every
candidate through `PoliteFetcher` before accepting — never publish a URL that was not retrieved.

This failure mode is not hypothetical: **the hand-curated seed already contains it.** At least four of
its 68 websites are the *school's* site, not the team's — `bishops.com`, `e3civichigh.com`, `sahs.org`,
`aolp.org` — a ~6–9% false-positive rate from a careful human. The CDE school-domain denylist would
have caught three of them for free.

Report coverage honestly in `meta` and add an "Add your team's website" link — crowd-sourcing beats
guessing, and it is the play this repo already runs for partners. Distinguish *"we failed to find it"*
from *"it does not exist"* with a `website_search` sub-object (`outcome ∈ found | no_candidate |
all_rejected | error`); two `no_candidate` runs 30+ days apart on an unchanged record promote to
`likely_none`. Social-only presence goes in a `social[]` field, never in `website`.

### Teams and partners are disjoint

Of 105 distinct team organizations, **exactly one** is already a partner (The LEAGUE of Amazing
Programmers). Skip the partner-join; `teams.json` stands alone. The inverse is the interesting result:
**104 San Diego schools run robotics teams and are not in the partner directory** — a ready-made
recruitment list, out of scope here.

### Site pages

- `site/src/data/teams.json` — committed, delivered by the mirror.
- `TeamCard.astro` — model on `OpportunityCard`, **not** `PartnerCard`: the map reads
  `card.querySelector('h3 a')`, and `PartnerCard` wraps the whole card in the anchor, so its popups
  fall back to `href="#"` (a latent bug on the Partners map today).
- `TeamFilters.astro` — clone `OpportunityFilters`' build-time facet-count pattern.
- `pages/teams/index.astro` — copy `partners/index.astro`, keeping the `#results-grid`,
  `#map-container`, `.results-count`, `.view-toggle` IDs that `scripts/filters.js` finds by
  convention. Every card needs `data-type` or the filter engine cannot see it.
- `pages/teams/[slug].astro` — `getStaticPaths()` over `teams.json`; reuse `.detail-page` + mini-map.
- Add the Teams item to **both** `Header.astro` and `Footer.astro` (separate hard-coded lists).
- Every emitted URL goes through `const base = import.meta.env.BASE_URL.replace(/\/+$/, '')`.
- **Map treatment:** ~85 city-precision teams would stack on one San Diego centroid and read as a
  single pin. Plot school/ZIP precision as individual pins; render city-precision as a labelled count
  per city.

### CLI

A new subcommand, not a flag on `run` — rosters refresh annually, opportunities weekly, and a TBA 401
must never poison the opportunities export:

```
uv run partner-scrape teams [--dry-run] [--source ftcscout|tba|seed]
                            [--site-dir DIR] [--no-mirror] [-v]
```

### Increments

1. **Model + FTCScout + export + subcommand.** 152 FTC teams, city-level. No credential needed. Proves
   the spine end to end.
2. **TBA source + merge.** +59 FRC teams, 43 websites, 49 ZIPs. Cross-league linking must key on
   **normalized organization name, not team number**: only one number collides across programs (1622),
   but **seven organizations run teams in both FTC and FRC** (Canyon Crest Academy, Francis Parker,
   Poway, Coronado, Del Norte, La Jolla Senior, North County Trade Tech). `Family/Community` and empty
   organizations must never group, or all home teams fuse into one bogus 100-team org.
3. **Geocoding.** The offline ladder, its data files, and `dev/refresh_school_directories.py`. Delivers
   the actual goal — knowing where the teams are.
4. **Site pages.** Index with filters and map, detail pages, nav.
5. **FLL static roster.** 48 teams, marked static with provenance and an end-of-life date. Last,
   because it is lowest value and the only piece with a hard expiry.

Seed data is an **overlay, never an override**: it supplies only fields no live source carries
(`github`, `notes`, `neighborhood`, curated `website`) and only where the live value is empty. A live
value always wins — a stale override is the worst failure mode because it is invisible. Strip contact
fields at import; the live pipeline must never open `data/robot-teams.json` directly.

## Verification

- `uv run pytest` — full suite green (905 passing at time of writing). New tests use canned
  FTCScout/TBA fixtures under `tests/fixtures/teams/`, `FixtureFetcher`, and **no network**.
- Fixtures must cover: an exact-CDE match, a private-school miss, a `Family/Community` team, dirty
  cities (`"La Jolla "`, `"carlsbad"`), and an out-of-county team.
- `uv run partner-scrape teams --dry-run -v` — inspect the payload without writing.
- Assert the numbers above (152 FTC, 59 FRC, 6 out-of-region, ~148 school-precision). Material drift
  means a source changed and should fail loudly rather than silently shrink the directory.
- Two hard invariants, each with a test: `opportunities.json` is never touched, and **`scrape-meta.json`
  is never written by the teams export** (it carries the opportunities timestamp; overwriting it would
  make the site claim opportunities were refreshed when they weren't). The teams timestamp lives in
  `meta.generated`.
- Export test asserts no key or value in `teams.json` matches an email pattern.
- `just build` — site builds clean; `/teams` page count equals exported team count.
- Confirm `teams.json` reaches `site/src/data/` via the mirror, not just `../stem-ecosystem`.

## Related

- `data/robot-teams.json` — the 254-record seed to trim into an overlay. Note its `meta.warning`.
- Sibling repo `../robot-team-analysis` — roster sources (`ftc/sd-ftc-teams.csv`,
  `frc/sd-frc-teams.csv`, `fll/sd-fll-teams-contact-list.md`), `web/build-teams.py`, the
  `fll/fll-disruption-2026.md` brief, and `robot-team/coaches-network-launch.md` (the strategy this
  serves).
- `partner_scrape/adapters/leaguesync.py` — reference implementation for a credentialed structured-API
  source (`_auth_headers`, `context` discriminator, per-record isolation).
- `partner_scrape/export/mirror.py` — `MIRRORED_DATA_FILES` must gain `teams.json`.
- `docs/deploy/scheduled-run.md` — **`TBA_KEY` is in local SOPS but not in GitHub Actions secrets**;
  the scheduled run will fail on FRC until an operator pushes it.
