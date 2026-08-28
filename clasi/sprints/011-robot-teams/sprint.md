---
id: '011'
title: Robot teams
status: ticketing
branch: sprint/011-robot-teams
use-cases: []
issues:
- robot-teams-scrape-locate-and-publish-san-diego-first-teams.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 011: Robot teams

## Goals

Build a refreshable pipeline that scrapes, locates, and publishes San
Diego County's ~259 FIRST robotics teams (FTC, FRC, FLL) — a new
category the site currently has nothing for — as a self-contained new
module and site section (issue `robot-teams-scrape-locate-and-publish-
san-diego-first-teams.md`).

A new `partner_scrape/teams/` module (its own model, sources, offline
geocoding, merge, and exporter — deliberately not routed through the
existing `Opportunity` model, since a team is a standing entity with no
date and would be filtered out by the export's current-and-upcoming
logic) pulls live rosters from FTCScout (152 FTC teams, free/no auth)
and The Blue Alliance (59 FRC teams, keyed, already provisioned), locates
each team via a fully offline resolution ladder (CDE + NCES school
directories, then ZIP centroid, then city centroid — never an LLM guess,
per the issue's explicit "never guess" rule), and publishes browsable
`/teams` pages modeled on the existing Opportunities pages.

The issue lays out five increments. **This sprint plans increments 1-4
only** (detail-planning decision, below); increment 5 is deferred to a
follow-on sprint:

1. **Model + FTCScout + export + subcommand** — 152 FTC teams,
   city-level, no credential needed; proves the spine end to end.
2. **TBA source + merge** — adds 59 FRC teams, 43 websites, 49 ZIPs;
   cross-league identity keyed on normalized organization name (not team
   number, since teams number 1622 collides across programs).
3. **Geocoding** — the offline CDE+NCES+ZIP+city resolution ladder, its
   committed data files, and the yearly manual refresh script.
4. **Site pages** — `/teams` index with filters and map, detail pages,
   nav entries in both `Header.astro` and `Footer.astro`.
5. **FLL static roster** (deferred to a follow-on sprint, not planned
   here) — 48 teams from a hand-maintained export, marked static with
   provenance and an end-of-life date (FIRST LEGO League's last season
   is 2026-27). Lowest-value piece and the only one with a hard expiry
   — see the scope-decision note above.

This sprint is large and self-contained: it introduces a new
`partner_scrape/teams/` subsystem, a new `Team` data model deliberately
disjoint from `Opportunity`, a new offline geocoding subsystem, and a
new `/teams` site section — independent of sprints 009/010's export and
discovery work, which is why it sits last where it cannot block them.

**Detail-planning decision: increments 1-4 in this sprint, increment 5
deferred.** The issue itself calls out that "increments 1-4 are
independently shippable" while increment 5 (FLL) is "lowest-value" and
"last, because it is lowest value and the only piece with a hard
expiry." Shipping 1-4 delivers a complete, working, visible `/teams`
page covering FTC (152 teams) and FRC (59 teams) — 211 of the ~259
total, all from live, refreshable sources, fully geocoded through the
offline ladder. Increment 5 is a structurally different kind of work: a
one-time import of a hand-maintained, PII-bearing static file
(`data/robot-teams.json`, 254 records including 40 email addresses)
with its own overlay/provenance/end-of-life mechanics, not a live
pipeline extension. Bundling it here would mean either rushing that
PII-stripping and provenance work to close out the sprint, or padding
the sprint past a natural stopping point that already satisfies "ship a
working page, not half a pipeline." A follow-on sprint (candidate: 012)
would carry increment 5 alone: import `data/robot-teams.json`, strip
contact fields, overlay it (never override) onto the live FTC/FRC data
this sprint publishes, mark FLL records `static` with provenance and
the 2026-27 end-of-life date, and extend `/teams` to include the FLL
cohort. That sprint has no dependency on anything this sprint doesn't
already ship — `teams.json`'s shape and the site pages both already
accommodate a `static` source with no code change needed to add FLL
later.

Note for detail planning: `docs/design/design.md` (plus per-subsystem
`DESIGN.md`) is being bootstrapped concurrently and `design_docs` is now
`enabled`. `partner_scrape/teams/` is an entirely new subsystem — expect
it to receive its own `DESIGN.md` at detail-planning/architecture time,
not merely a `design/` overlay on an existing doc.

## Scope

### In Scope

- New `partner_scrape/teams/` module: `model.py` (`Team` dataclass),
  `sources/{base,ftcscout,tba}.py` (`sources/static_roster.py` is
  increment 5 — out of scope this sprint), `geo.py` (offline resolver),
  `merge.py` (cross-source/cross-league identity), `export.py` (writes
  `teams.json`), `pipeline.py`, per-league `registry/*.toml`, and
  committed geocoding data files (CDE public + NCES private school
  directories, ZIP/city centroid tables, `school-overrides.toml`).
- `config.py` additions for `TBA_KEY` / TBA URL, mirroring the existing
  `leaguesync` credential pattern.
- `export/mirror.py`'s `MIRRORED_DATA_FILES` gaining `teams.json`, and a
  new `teams` CLI subcommand (not a flag on `run`, since rosters refresh
  annually and a TBA failure must never poison the opportunities
  export).
- New site components/pages modeled on the existing Opportunities
  section: `TeamCard.astro`, `TeamFilters.astro`,
  `pages/teams/index.astro`, `pages/teams/[slug].astro`, and nav entries
  in `Header.astro` / `Footer.astro`.
- The offline geocoding ladder and its yearly manual refresh script
  (`dev/refresh_school_directories.py`).
- Deploy follow-up: pushing `TBA_KEY` to GitHub Actions secrets so the
  scheduled run doesn't fail on FRC (flagged in the issue as currently
  missing; see Migration Concerns).

### Out of Scope

- **Increment 5 — the FLL static roster overlay** (48 teams from
  `data/robot-teams.json`, contact-field stripping, static/provenance/
  end-of-life marking). Deferred to a follow-on sprint (candidate:
  012) — see the scope-decision note under Goals. Not a rejection of
  the work, a sequencing decision: it is structurally a one-time static
  import, not a live-pipeline extension, and bundling it here would
  either rush its PII-handling or push the sprint past the point where
  a complete, working `/teams` page already ships.
- Joining teams to the existing partner directory — the issue found only
  one of 105 distinct team organizations is already a partner, and
  explicitly skips the partner-join; `teams.json` stands alone. The
  inverse finding (104 San Diego schools running robotics teams that
  aren't partners) is a ready-made recruitment list, noted as out of
  scope here.
- An LLM-driven website-discovery search for team websites — the issue
  frames this as a possible follow-on behind an explicit flag, not part
  of the five core increments; deterministic tiers (TBA's `website`
  field, the hand-curated seed with liveness checks, CDE's matched
  `WebSite` as a separate `organization_website` field) ship first.
- Any team `email` field — deliberately omitted per the issue (a parent's
  personal email on a public page is a real risk; omitting the field
  makes leaking one structurally impossible).
- Sprints 009/010's export-publishing and discovery work — independent
  data domains; this sprint does not touch `opportunities.json`,
  `partners.json`, or `scrape-meta.json` (two hard invariants the issue
  calls out explicitly: teams export never touches either file).

## Test Strategy

Matches the existing engine's convention exactly: fixture-based, hermetic,
no network. New tests live under `tests/` mirroring `partner_scrape/teams/`'s
layout (one test module per source module), using canned FTCScout/TBA JSON
fixtures under `tests/fixtures/teams/` and the existing `FixtureFetcher`
double — no new test infrastructure is introduced.

- **Unit — sources**: FTCScout and TBA extraction against canned fixtures,
  including a malformed/partial record (per-record isolation, matching
  every adapter's convention).
- **Unit — merge**: cross-league identity on normalized organization name;
  fixtures must include one of the seven known FTC+FRC dual-program
  organizations (e.g. Canyon Crest Academy) merging correctly, and confirm
  `Family/Community`/empty organizations never group into one org.
- **Unit — geocoding**: fixtures covering an exact CDE match, a private-school
  (NCES) miss, a `Family/Community` team (city precision), dirty city
  strings (`"La Jolla "`, `"carlsbad"`), an out-of-county team
  (`in_region = false`, flagged not dropped), and a low-confidence fuzzy
  match (`needs_review: true`) — the six cases the issue's own Verification
  section calls out.
- **Unit — export**: a test asserting no key or value in `teams.json`
  matches an email-address pattern (the no-email invariant is structural,
  not just a code review note); a test asserting `teams` export never
  writes or touches `opportunities.json` or `scrape-meta.json` (the two
  hard invariants).
- **Integration — CLI**: `partner-scrape teams --dry-run -v` against
  fixtures, asserting the payload's team counts (152 FTC, 59 FRC, 6
  out-of-region) match the issue's measured numbers — material drift means
  a source changed and should fail loudly, not silently shrink the
  directory.
- **Integration — mirror**: `teams.json` reaches a target checkout's
  `site/src/data/` via `mirror_site_data`, matching the existing
  `MIRRORED_DATA_FILES` test convention.
- **Site build**: `just build` succeeds with a fixture `teams.json` present;
  `/teams` page count equals the exported team count; `TeamCard`'s title
  markup is checked for the `h3 a` structure the map's `querySelector('h3
  a')` depends on (the exact bug this sprint avoids by modeling on
  `OpportunityCard`, not `PartnerCard` — see Architecture's Design
  Rationale).
- **Regression**: `uv run pytest` — full existing suite stays green. No
  existing test should need to change; `partner_scrape/teams/`'s only edge
  into `normalize/` is a read-only reuse of
  `normalize.partners.normalize_org_name` (Architecture's Design
  Rationale) — it has no
  edge into `enrich/`, `normalize.run()`, `pipeline.run()`,
  `export/writer.py`, or `export/ads.py`.

## Architecture

**Substantial** — introduces a brand-new `partner_scrape/teams/`
subsystem (5+ new modules: `model.py`, `sources/{base,ftcscout,tba}.py`,
`geo.py`, `merge.py`, `export.py`, `pipeline.py`), a new data model
(`Team`, deliberately disjoint from `Opportunity`), two new external
integrations (FTCScout, The Blue Alliance), a new cross-module
dependency into `config.py`/`export/mirror.py`, and a new site section.
Well past every "compact" threshold (one module, no new dependency, no
data-model change) — this gets the full 7-step methodology, diagrams
included.

This project has opted into the persistent per-subsystem design-doc set
(`design_docs` enabled), so per the `architecture-authoring` skill's
Mode 2a, the full architecture write-up for a substantial sprint lives
in this sprint's `design/` overlay, not in this section. This section is
the pointer and summary; the overlay is the source of truth tickets are
derived from.

**Overlay documents edited** (`clasi/sprints/011-robot-teams/design/`):

- `design.md` — system doc (`docs/design/design.md`): adds
  `partner_scrape/teams/` to the subsystem map as a second, independent
  pipeline (not part of the `registry→adapters→enrich→normalize→export`
  flow diagram), and notes the teams/partners join as an open product
  question.
- `DESIGN.md` — root overview (`partner_scrape/DESIGN.md`): documents
  `config.py`'s new `get_tba_api_key()`/`get_tba_url()` accessors,
  `cli.py`'s new `teams` subcommand, and adds `teams/` to the subsystem
  map table.
- `export-DESIGN.md` (`partner_scrape/export/DESIGN.md`): documents
  `mirror.py`'s `MIRRORED_DATA_FILES` gaining `"teams.json"`, written by
  the new, structurally separate `teams/export.py` (not this
  subsystem's own `writer.py`/`ads.py`).

**New subsystem doc — not seeded, drafted separately.**
`partner_scrape/teams/DESIGN.md` has no existing canonical version to
seed a diff against (the directory doesn't exist yet), so it cannot go
through `seed_sprint_design_overlay`/`generate_diffs` like the three
docs above — a diff needs a pristine baseline, and this doc doesn't
have one yet. A full draft, written to the bootstrap-design subsystem
template, lives at
`clasi/sprints/011-robot-teams/design/new-subsystem/teams-DESIGN.md`
(kept in a subdirectory so it doesn't trip the overlay validator's
diff/manifest checks, which only apply to the three real overlay files
above). Ticket 001's acceptance criteria require writing this content
to its final co-located path, `partner_scrape/teams/DESIGN.md`, once
the module exists — verified/refreshed against the actual code at that
point, per bootstrap-design's "describe reality, not aspiration" rule,
not copied verbatim from the pre-code draft.

**What changed, in one paragraph:** A new, independent
`partner_scrape/teams/` pipeline (own model, sources, merge, offline
geocoder, exporter) acquires FTC (FTCScout) and FRC (The Blue Alliance)
team rosters, resolves cross-league organizational identity, locates
each team through a seven-rung offline-only ladder, and publishes
`teams.json` — reusing `config.py`, `registry.schema/loader`,
`fetch.PoliteFetcher`, and one function of `normalize.partners`, but
never touching `pipeline.run()`, `normalize.run()`, `enrich/`, or either
existing export writer. `export/mirror.py` gains one allowlist entry so
`teams.json` reaches mirrored checkouts the same way `opportunities.json`
does. A new `/teams` site section (index, filters, map, detail pages,
nav) presents it, modeled on `OpportunityCard`/`OpportunityFilters`
rather than the visually-closer `PartnerCard` (full rationale in the
overlay's root-doc update).

**Design Rationale (highlights — full detail, with alternatives
considered, is in the overlay documents and the new-subsystem draft):**

- **`Team` is a new, separate model, not a widened `Opportunity`/`Kind`**
  — a team is a standing entity with no date, and `export/writer.py`'s
  current/upcoming filter would drop every one of them; widening `Kind`
  would ripple into `enrich/`, `normalize/run.py`, and `export/writer.py`
  for near-zero reuse (no date, no recurrence, no relevance gate, no
  taxonomy in common).
- **`TeamSource` is structurally disjoint from `adapters.base.ADAPTERS`**
  — registering a team source there would make it reachable from
  `pipeline.run()`, which would hand a `Team` to `normalize.run()` and
  crash on a type it doesn't expect. Keeping the namespaces disjoint is
  a structural guarantee, not just a convention.
- **A new `teams` CLI subcommand, not a `run` flag** — a TBA auth
  failure must never sit inside the same process/exit code as the
  weekly opportunities export (`TBA_KEY` is not yet in scheduled-run
  secrets — Migration Concerns), and refresh cadences differ (annual vs.
  weekly).
- **Geocoding is offline-only; no LLM fallback, ever** — the issue's own
  measurement found live geocoding unreliable (Nominatim 41% failure, a
  429 on first request from a second machine), and an LLM-guessed
  coordinate is unverifiable and worse than no pin. ~14 unresolvable
  FTC teams (plus any unresolvable FRC teams) ship with
  `location_precision: none` rather than a fabricated point.
- **Cross-league identity keys on normalized organization name, not team
  number** — team number 1622 exists in both FTC and FRC as different
  teams, while seven real organizations run teams in both programs and
  must link; reusing `normalize.partners.normalize_org_name` avoids a
  second, independently-drifting normalizer.
- **`teams.json` is not joined to `partners.json` this sprint** — only 1
  of 105 distinct team organizations is already a partner; the
  interesting finding (104 SD schools running teams that aren't
  partners) is a recruitment list, a product decision, not an
  architectural one.
- **`TeamCard.astro` models on `OpportunityCard`, not the more visually
  similar `PartnerCard`** — confirmed live that `PartnerCard` wraps its
  whole card body in one outer `<a>`, so its `<h3>` has no nested `<a>`
  and the map's `card.querySelector('h3 a')` returns `null` (an
  existing, latent bug on the Partners map today); `OpportunityCard`
  nests the anchor inside `<h3>` and the same map code works.
- **Increments 1-4 this sprint, increment 5 (FLL) deferred** — see the
  scope-decision note under Goals. `teams.json`'s schema already
  accommodates a future `static` source value with no schema change
  needed when FLL is added later.

**Impact on Existing Components:** additive throughout — `config.py`
gains two accessor functions, `cli.py` gains one subcommand branch,
`export/mirror.py` gains one allowlist entry, `normalize.partners`
gains one new caller (no new code), and `Header.astro`/`Footer.astro`
each gain one nav item. Everything else in `partner_scrape/`
(`pipeline.py`, `normalize/`, `enrich/`, `export/writer.py`,
`export/ads.py`, `export/images.py`, `export/publish.py`,
`export/partner_log.py`, `discovery/`, `extract/`, `observability/`,
`store/`) is untouched — a direct consequence of "`Team` is not an
`Opportunity`" above.

### Migration Concerns

- **`TBA_KEY` is not yet in GitHub Actions repo secrets.** It is
  provisioned and verified working in `.env` and
  `config/prod/secrets.env` (SOPS), but the scheduled workflow's
  environment does not have it yet. Until an operator pushes it as a
  repo secret, the FRC (TBA) portion of the `teams` subcommand will
  fail with an auth error on any scheduled run. Per the "new `teams` CLI
  subcommand, not a `run` flag" rationale above and the project's
  existing "a partial result ships, the gap is reported" failure
  principle (`docs/design/design.md` §5), `teams.pipeline.run_teams()`
  must isolate a TBA fetch failure the same way `pipeline.run()`
  isolates a per-source failure — logging and skipping TBA rather than
  raising — so a missing `TBA_KEY` degrades to FTC-only `teams.json`
  (152 teams) instead of failing the whole subcommand and leaving no
  `teams.json` at all. This ticket-level requirement is called out
  explicitly in ticket 003's acceptance criteria. Manual local runs are
  unaffected (`TBA_KEY` already works in `.env`) — this only blocks the
  *scheduled* run's FRC coverage until the operator action happens.
- **Sequencing within the sprint**: tickets 001→002 must land before 003
  (TBA needs the pipeline/export spine to merge into), which must land
  before 004 (geocoding fixtures need real `postal_code` values, which
  only TBA supplies at any real rate), which must land before 005 (site
  pages read `location_precision` to decide pin-vs-badge rendering). See
  Tickets.
- **First local run before the site can build.** `pages/teams/*.astro`'s
  `getStaticPaths()` reads `site/src/data/teams.json` at build time, the
  same way existing pages read `opportunities.json`. Until an operator
  (or ticket 005's own testing step) runs `partner-scrape teams` at
  least once against this repo's own `site/` checkout, `just build`
  has no `teams.json` to read. This is the same bootstrap requirement
  every existing data-driven page already has — not a new failure mode,
  but worth stating since it's this sprint's first time it applies to a
  brand-new page.
- **No backward-compatibility concern**: `teams.json` is a wholly new
  file; no existing file's schema changes, and the two hard invariants
  (`opportunities.json` and `scrape-meta.json` are never touched by the
  teams export) are each covered by a dedicated test (Test Strategy).
- **No data migration**: nothing existing is being converted or
  backfilled; `data/robot-teams.json` (the FLL/legacy seed) is read by
  nothing this sprint — its import is entirely deferred to the
  follow-on sprint (see "Increments 1-4 this sprint..." in Design
  Rationale above).

## Use Cases

`docs/design/usecases.md`'s twelve existing UCs are all shaped around
`Opportunity` (dated events/programs/internships) or the existing
Engine/Operator/Visitor/Fleet actors. None has a `Team` (an undated
standing entity) as its subject, so — matching sprint 010's precedent
for new capability without a matching existing UC — each SUC below
parents to the closest existing UC by *shape* (structured-API ingest →
UC-001, record-to-site-schema mapping → UC-005, browsing a directory →
UC-012) rather than minting a new top-level UC. Whether `Team` warrants
its own top-level UC family is a consolidation-time decision, not this
sprint's.

### SUC-001: Ingest FTC team rosters and publish a teams directory
Parent: UC-001

- **Actor**: Engine
- **Preconditions**: `partner_scrape/teams/registry/ftc-sd.toml` (or
  equivalent) is registered; no credential required (FTCScout is free,
  unauthenticated).
- **Main Flow**:
  1. `partner-scrape teams` (or `--source ftcscout`) calls
     `teams.pipeline.run_teams()`.
  2. `teams.sources.ftcscout` fetches San Diego region FTC teams via
     FTCScout's REST search endpoint and maps each into a `Team`.
  3. `teams.export` serializes the result to
     `{site_dir}/src/data/teams.json` with a `meta.generated` timestamp
     (never `scrape-meta.json`).
  4. Unless `--no-mirror`, `export.mirror_site_data` copies `teams.json`
     into every configured mirror checkout.
- **Postconditions**: `teams.json` exists (or is refreshed) with every
  currently-active San Diego FTC team, city-precision at minimum.
- **Error Flows**: FTCScout unreachable or returns an unexpected shape
  → the run logs and exits without writing a corrupt `teams.json`
  (existing file, if any, is left untouched — no partial overwrite).
  Malformed individual record → logged and skipped, matching every
  existing adapter's per-record isolation convention.
- **Acceptance Criteria**:
  - [ ] `partner-scrape teams --dry-run -v` against fixtures reports
        152 FTC teams (the issue's measured count) with no network call.
  - [ ] `teams.json` is written to `{site_dir}/src/data/` and mirrored
        to every configured checkout.
  - [ ] `opportunities.json` and `scrape-meta.json` are byte-identical
        before and after a `teams` run (hard invariant, tested).
  - [ ] No key or value in the written `teams.json` matches an
        email-address pattern.

### SUC-002: Ingest FRC rosters and merge cross-league team identity
Parent: UC-001

- **Actor**: Engine
- **Preconditions**: SUC-001 ships (the pipeline/export spine exists);
  `TBA_KEY` is set (locally verified working; not yet in scheduled-run
  secrets — Migration Concerns).
- **Main Flow**:
  1. `teams.sources.tba` fetches San Diego-area FRC teams from The Blue
     Alliance's `/api/v3/teams/{page}` (filtered to CA + SD cities),
     authenticated via `config.get_tba_api_key()`.
  2. `teams.merge` links each FRC `Team` to any FTC `Team` sharing the
     same `normalize.partners.normalize_org_name`-normalized
     organization, setting `org_key`/`sibling_team_ids` — except
     `Family/Community`/empty organizations, which never group.
  3. The merged, still-unlocated `Team[]` continues into export as in
     SUC-001.
- **Postconditions**: `teams.json` additionally carries 59 FRC teams;
  the seven known dual-program organizations' FTC and FRC teams
  cross-reference each other via `sibling_team_ids`; team-number
  collisions (e.g. 1622) do not cause a false merge.
- **Error Flows**: `TBA_KEY` missing or TBA returns 401/unreachable →
  logged and skipped (never raises the whole run) per Migration
  Concerns — `teams.json` still publishes with FTC-only data. A
  malformed individual TBA record → logged and skipped.
- **Acceptance Criteria**:
  - [ ] With TBA fixtures present, `teams.json` carries 59 FRC teams
        (the issue's measured count).
  - [ ] A dual-program organization fixture (e.g. Canyon Crest Academy)
        merges its FTC and FRC teams via `sibling_team_ids`.
  - [ ] `Family/Community` and empty-organization teams are never
        merged into a shared `org_key`.
  - [ ] A simulated `TBA_KEY`-missing/401 run still publishes a
        152-team, FTC-only `teams.json` rather than failing outright.

### SUC-003: Locate each team through the offline geocoding ladder
Parent: UC-005

- **Actor**: Engine
- **Preconditions**: SUC-001/SUC-002 produce merged `Team[]`; the
  committed geocoding data files (`sd-schools-public.tsv`,
  `sd-schools-private.tsv`, `zip-centroids.toml`,
  `city-centroids.toml`, `school-overrides.toml`) exist under
  `teams/data/`.
- **Main Flow**:
  1. For each `Team`, `teams.geo` runs the seven-rung ladder in order:
     overrides → CDE+NCES exact match → token-set match within city →
     token-set match county-wide → ZIP centroid → city centroid → no
     match.
  2. Each resolved `Team` is stamped with `location_precision`
     (`school|zip|city|none`), `matched_name` (traceability), and, below
     a 0.85 fuzzy-match score, `needs_review: true`.
  3. An out-of-county team (e.g. Ensenada, San Clemente) is stamped
     `in_region = false` and still published — never silently dropped —
     with a count surfaced in `meta`.
- **Postconditions**: Every located `Team` carries coordinates and a
  precision label; unresolvable teams carry `location_precision: none`
  rather than a fabricated coordinate.
- **Error Flows**: No LLM fallback exists for this ladder — by design
  (Architecture's Design Rationale), a team that exhausts all seven
  rungs simply has no coordinates.
  A malformed data file → fails the run loudly at startup (a bad
  geocoding table is a build-time defect, not a per-record one).
- **Acceptance Criteria**:
  - [ ] Fixture set (Test Strategy) covers an exact CDE match, an NCES
        private-school miss, a `Family/Community` city-precision team,
        dirty city strings, an out-of-county team, and a sub-0.85 fuzzy
        match.
  - [ ] No coordinate is ever produced by a rung other than the seven
        listed — no LLM call anywhere in `teams.geo`.
  - [ ] `dev/refresh_school_directories.py` exists and documents the
        yearly manual refresh procedure for the CDE/NCES source files.

### SUC-004: Visitor browses the Teams directory
Parent: UC-012

- **Actor**: Visitor
- **Preconditions**: `teams.json` is published and mirrored into the
  site checkout being served (SUC-001-003 have run at least once).
- **Main Flow**:
  1. Visitor opens `/teams` from the header or footer nav.
  2. `TeamFilters` narrows by league/program and other build-time
     facets, following `OpportunityFilters`' existing pattern.
  3. School/ZIP-precision teams render as individual map pins;
     city-precision teams render as one labelled badge per city (e.g.
     "San Diego — 40 teams") rather than stacking indistinguishable
     pins or a plain cluster marker that implies false precision.
  4. Visitor opens a team's detail page
     (`pages/teams/[slug].astro`) for its full record.
- **Postconditions**: A visitor can find and identify San Diego FTC/FRC
  teams by league, name, or location precision, without the map
  misrepresenting a team's actual location certainty.
- **Error Flows**: A team with `location_precision: none` still appears
  in the list view (filterable, findable) but is omitted from the map
  rather than plotted at a fabricated point.
- **Acceptance Criteria**:
  - [ ] `/teams` index and `/teams/<slug>` detail pages build and
        render against a fixture `teams.json`.
  - [ ] `TeamCard`'s title anchor sits inside `<h3>` (not wrapping the
        whole card), so `card.querySelector('h3 a')` resolves — the
        `PartnerCard` map-popup defect (Architecture's Design Rationale)
        is not reintroduced.
  - [ ] City-precision teams render as a labelled per-city badge, never
        jittered and never a plain unlabeled cluster marker.
  - [ ] "Teams" appears in both `Header.astro` and `Footer.astro` nav.
  - [ ] `just build`'s `/teams` page count equals the fixture's exported
        team count.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Team model and FTCScout source | — |
| 002 | Teams pipeline export and CLI subcommand | 001 |
| 003 | TBA source and cross league merge | 002 |
| 004 | Offline geocoding ladder and data files | 003 |
| 005 | Teams site pages and navigation | 004 |

Tickets execute serially in the order listed. None of these tickets
close out the linked issue (`completes_issue: false` on all five) —
increment 5 (FLL) is deferred to a follow-on sprint, whose tickets will
eventually complete it.
