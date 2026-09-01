# teams

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-29 (sprint 013 — website verification and sponsor extraction added) · **Status:** all five sprint 011/012 increments complete (FTC + FRC + geocoding + site pages + FLL static roster), plus sprint 013's website verification and sponsor-extraction stages

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

**Ticket 018-006 extracted the general-purpose parts of the ladder
below into a new shared module, `partner_scrape/geo_ladder.py`,** so
the sprint 018 `directory/` module (Places, Clubs — school-based Hack
Club chapters need the same CDE/NCES school-matching rungs) can depend
on the ladder without depending on `teams/` or duplicating its logic.
`teams.geo.SchoolIndex` is now a thin subclass of
`geo_ladder.GeoLadder`, adding only `Team`-field stamping
(`SchoolIndex.resolve(team)`); `teams.geo.geocode_teams()`'s signature
and behavior, and every rung's ordering/thresholds described below,
are unchanged — see `teams/geo.py`'s own updated docstring and
`geo_ladder.py`'s own docstring for the extraction's exact split, and
`tests/teams/test_geo_regression.py` for the byte-identical-output
proof. The rung-by-rung description in this document remains an
accurate description of *behavior*; it is not duplicated in
`geo_ladder.py`'s docstring, which instead documents the same ladder
from its own, `Team`-independent point of view.

**Ticket 011-004 added the offline geocoding ladder — the increment
that actually delivers the sprint's stated goal of *knowing where the
teams are*.** `teams.pipeline.run_teams()` runs both sources, links
cross-league identity, and geocodes every merged `Team` through
`teams.geo.geocode_teams()` before export. Measured at ticket 011-004's
own build (2026-08-28) against the *original* 211-team FTC+FRC test
corpus (152 FTC + a hand-authored 59-team TBA fixture, since
superseded — see below): **129 teams at school precision** (79 FTC +
50 FRC), **8 at ZIP**, **70 at city**, **4 unresolved** (`"none"` — two
Ensenada teams, plus two out-of-region teams whose city name is too
ambiguous to guess, "San Antonio"/"Louisville"), **14 flagged
`needs_review`**. This distribution described the *test fixture's*
corpus at that build, not a live measurement — see the next paragraph
for why that distinction turned out to matter.

**Ticket 011-005 adds the `/teams` site section — the last increment
of `sprint.md`'s Migration Concerns chain (001→002→003→004→005)** —
and is the ticket that makes the whole sprint visible to a site
visitor. It builds no new Python code in this subsystem at all; it is
purely a consumer of `teams.json`, exactly as `sprint.md`'s Impact on
Existing Components anticipated. See "Site Presentation Layer" below
for what it built.

**Ticket 011-003 was reopened (2026-08-28) for a sprint-validation
defect: a live `partner-scrape teams` run returned only 19 FRC teams,
not the ~59 the original ticket measured.** Root cause: TBA's
`/api/v3/teams/{page}` reports the *full* state name (`"California"`)
for the majority of San Diego County records (59 of the real 78) and
only the bare USPS abbreviation (`"CA"`) for the rest (19) —
`sources.tba._extract_one()`'s original filter compared `state_prov`
to the literal string `"CA"` with no normalization, so it matched only
the minority 19 and silently dropped the majority 59. The ticket
011-003 test fixture used `"CA"` for every hand-authored record, so
this was never caught in tests. **Fix:** `sources.tba._normalize_state()`
normalizes any recognized full US state name to its USPS abbreviation
before the comparison runs (see Interfaces). **On the 19 `"CA"`-abbreviated
records themselves:** confirmed live (`/team/frcNNNN/years_participated`)
that every one is a genuine historical San Diego County FRC team —
real schools, real addresses, several with real working websites — but
all 19 last competed in or before 2014 (two never competed at all),
while the "California"-labeled 59 skew far more recent (40 of 59 last
competed 2023 or later). This age/format correlation is why the bug
went undercounted for so long, but it is not a legitimacy signal: TBA's
team roster is an append-only historical registry with no "active"
flag (`model.Team.active` is not populated by any source; see
Constraints below), so an old profile that has never been rewritten to
the full state name is still a real San Diego County team, exactly the
same way a "California"-labeled but similarly stale record already in
the 59 is. Excluding the 19 would require inventing a new
activity-based filter this subsystem has never had (neither source
filters by recency), which was judged out of scope for a filter-format
bugfix. **Corrected total, confirmed via a real `partner-scrape teams
--dry-run` run (2026-08-28): 78 FRC teams, 230 overall (152 FTC + 78
FRC)** — see Interfaces for the corrected `SD_COUNTY_CITIES` figure and
Open Questions for the full before/after. The *committed test fixture*
(`tests/fixtures/teams/tba_teams_page0.json`/`page1.json`) was rebuilt
from real, live-captured records but deliberately kept small (7 of the
78 real matches, plus real noise records) rather than growing to the
full 78 — see `tests/teams/test_sources_tba.py`'s module docstring —
so the fixture-driven test corpus is now 159 teams (152 FTC + 7 FRC),
not 211; every count elsewhere in this document that cites "211" or
"59" describes that now-superseded original fixture unless marked
otherwise.

**Sprint 012 adds the fifth and final increment: a static FLL roster.**
Sprint 011 deliberately deferred First LEGO League (48 teams) because
there is no public FLL API and no third-party aggregator — probed and
confirmed at issue-write time. The only source is a hand-maintained,
dated export living in a sibling repo
(`../robot-team-analysis/fll/sd-fll-teams-contact-list.md`), which also
carries contact data (40 email addresses, six of them volunteer
coaches' personal Gmail accounts) this project has never published and
structurally cannot — `model.Team` has no `email` field, by design (see
Constraints). `teams.sources.static_roster.StaticRosterSource` reads a
committed, already-contact-stripped roster file under `teams/data/` and
never calls the injected `Fetcher` — a "source" in name and protocol
shape only; there is no acquisition step to isolate a failure from, only
a file read. Registered via a new `teams/registry/fll-sd.toml` entry
(`adapter_type = "static_roster"`) alongside the two live sources, it
needed zero changes to `merge_teams()`, `geocode_teams()`, or
`export_teams()` — the pipeline stages after acquisition were already
source-agnostic by the design choices sprint 011 made (see Design,
below, for the specific paragraph that anticipated this). Because FLL's
2026-27 season is announced as the program's last ever (LEGO declined to
renew its FIRST partnership, 2026-03-19), the registry entry also
carries `sunset_season = "2026-27"`; `run_teams()` logs a WARNING once
`date.today()` passes that season rather than silently continuing to
publish undated-feeling "current" data for a program that no longer
exists. Expected total once this ships: **278 teams (152 FTC + 78 FRC +
48 FLL)** — see Open Questions for the real-run confirmation this
sprint requires before close, matching the ticket 011-003 lesson
(commit a fixture built from real captured data, then verify against a
live run, not just the fixture suite).

**Sprint 013 adds website verification and sponsor extraction — the
first stages in this subsystem that fetch a page this project does not
control and interpret its unstructured content.** Of the 278 teams, 53
(all FRC, from TBA) carry a known `website`; `run_teams()` gained two
new stages after `geocode_teams()`. First, `teams.scrape.
verify_team_websites()` fetches each of those 53 URLs through the same
`fetcher`/`PoliteFetcher` seam every other network-touching stage in
this project already uses (robots.txt, per-domain throttle, and
conditional-GET cache all apply with zero new plumbing), setting
`Team.website_status` to `confirmed` (2xx), `unverified` (non-2xx,
transport error, or robots disallow), or `none` (no known URL) —
`website_status` existed on the dataclass since sprint 011 but no code
had ever written it until now. Second, for every `confirmed` fetch,
`teams.sponsor_extract.extract_sponsors()` runs a deterministic
candidate-gathering pass (`teams.sponsor_candidates.
gather_sponsor_candidates()` — headings matching
`/sponsor|partner|thank/i`, `<img>` `alt`/`title` text, footer link
text/hostnames) and, only when that pass finds something, a
cache-checked LLM call (`teams.sponsor_llm.SponsorLLMClient.
classify_sponsors()`) that *selects* — never generates — which
candidates are genuine sponsor names. Every returned name is validated
against the original candidate list before it is trusted; a name that
is not verbatim in that list is dropped and logged, not published. This
is a structural anti-hallucination guarantee, not a prompting
convention — see Design, below, for why that distinction was the
sprint's central design decision. Surviving names are deduplicated
against any existing structured sponsors (today, only FTCScout's) via
`normalize.partners.normalize_org_name` (reused, not reimplemented) and
recorded with provenance in a new `Team.sponsor_provenance: dict[str,
str]` field (`"structured"`/`"scraped"`). None of this touches
`enrich/`, `adapters/`, `normalize.run()`, or `pipeline.run()` — the
five new modules (`scrape.py`, `sponsor_candidates.py`, `sponsor_llm.py`,
`sponsor_cache.py`, `sponsor_extract.py`) mirror `enrich/llm_client.py`'s
and `enrich/cache.py`'s pattern in shape only, never by import. See
Constraints, Design, and Interfaces below for the full detail; see
`clasi/sprints/013-team-website-surfacing-and-sponsor-extraction/
sprint.md` for the sprint-level plan this section elaborates.

**Sprint 016 ticket 005 adds the first non-FIRST league this subsystem
has ever ingested: VEX Robotics Competition (V5RC/VIQRC), CA Region 4
(San Diego/Imperial), via the same RobotEvents API v2 sprint 016 ticket
004 already plumbed config access for on the Opportunity-pipeline
side.** VEX team designations are alphanumeric (`90210A`, a numeric
prefix plus a required letter suffix distinguishing sibling teams
fielded by the same organization — `90210A`/`90210B`/`90210C` are three
distinct real teams), which `Team.number: int` could not hold without
either colliding `team_id`s (truncating to the numeric prefix) or
adopting an `int | str` union every consumer would then need to check.
This ticket widens `Team.number` to `str` uniformly instead — see
`clasi/sprints/016-feed-robustness-venue-dedup-and-the-vex-league/
sprint.md`'s Design Rationale for the full alternatives-considered
writeup, not re-derived here — and repairs the two call sites that did
bare numeric-arithmetic sorting on it (`export.py`'s sort key, this
repo's own `site/src/pages/teams/index.astro` comparator) with a
natural-sort key (leading digit run as int, full string as tiebreaker)
so existing FTC/FRC/FLL purely-numeric values keep sorting numerically,
unchanged. `teams.sources.robotevents.VexTeamSource` follows
`sources/tba.py`'s structural precedent, not `sources/ftcscout.py`'s:
RobotEvents' `/teams` endpoint has no city/region query parameter at
all (confirmed against its published OpenAPI schema), the same
"global roster, no region filter" situation TBA's own `/api/v3/
teams/{page}` is in — so this source paginates the full result set and
filters to San Diego County client-side via its own (independently
duplicated, not imported) `SD_COUNTY_CITIES` allowlist, `discover()`
raising on any probe failure rather than degrading gracefully, matching
`sources/tba.py`'s exact isolation contract. Registered via
`teams/registry/vex-sd.toml` (`adapter_type = "robotevents"`)
unconditionally, matching `frc-sd.toml`'s TBA precedent — no live
`ROBOTEVENTS_KEY` was available during this ticket's execution either
(see ticket 004's own Notes), so `teams.pipeline.run_teams()`'s
existing per-source isolation is what makes this source's absence
degrade the pipeline to non-VEX-only output rather than aborting the
run, exactly as it already does for a missing `TBA_KEY`.

**Sprint 021 audits sprint 013's discovered-website import, then adds
description extraction -- the first stage in this subsystem that turns
a fetched page's *unstructured text* into a new published field.**
Ticket 001's audit confirmed, directly against the repository rather
than the issue's own framing, that the import already happened cleanly:
`teams/data/discovered-websites.toml`'s 52 entries (31 with a `website`
key, 21 social-only) exactly match sprint 013 research's own
`meta.websites: 31`/`meta.social_only: 21` counts, and
`teams.pipeline.run_teams()`'s stage order (`apply_website_overrides()`
immediately before `verify_team_websites()`, unconditionally, every
run) architecturally guarantees `Team.website_status` is set for every
overlay-sourced website -- no code change, one closed test-coverage gap
(an overlay-*only*-sourced website through the full `run_teams()`
chain). Ticket 004 then adds four new modules, mirroring sprint 013's
sponsor-extraction module set in shape but never by import:
`description_candidates.gather_description_content()` (pure, offline --
`<meta name="description">` content, `<title>` text, and every
`<h1>`-`<h3>`/`<p>` element's own text, concatenated and capped at 2000
characters, from the same fetched homepage `verify_team_websites()`/
`extract_sponsors()` already produced -- no second fetch), a
`description_llm.DescriptionLLMClient` protocol whose only contract is
*summarizing* that bounded text (never generating from open context,
mirroring `sponsor_llm.py`'s classify-don't-generate contract, adapted
to summarize-don't-generate), `description_cache.DescriptionCache`
(content-hash cache, mirrors `sponsor_cache.py`), and
`description_extract.extract_descriptions()` (orchestration: gather ->
cache -> summarize -> no-email/length guard -> publish, fail-open per
team, sequenced after `canonicalize_sponsors()` and before
`export_teams()`). The no-email guard is layered three independent
ways -- a regex strip at gathering time (layer 1), a system-prompt
instruction (layer 2), and a code-level rejection of the LLM's raw
response before it can ever be published (layer 3, mirroring
`sponsor_extract._is_denylisted()`'s own "never trust the model's
compliance with its own instructions alone" role) -- plus a length cap
mirroring `sponsor_extract._MAX_SPONSOR_NAME_LENGTH`'s own
defense-in-depth precedent. Four new flat fields land on `Team`
(`description`, `description_status`, `description_provenance`,
`description_fetched_at`); `teams/export.py` needed no code change at
all -- `TEAMS_SCHEMA_FIELDS` already auto-derives from
`dataclasses.fields(Team)`. Per a stem-ecosystem peer's planning-time
refinement, `description_status` (`"generated"`/`"unavailable"`/
`"none"`) is deliberately independent of the existing `website_status`
-- the latter still answers "was the site reachable," the former "did
we find anything worth showing," since a reachable site can still have
nothing extractable. `run_teams()` gains
`description_llm_client`/`description_cache`/`no_descriptions`
parameters, lazily constructing a real
`AnthropicDescriptionLLMClient()`/`DescriptionCache()` only when the
stage actually has at least one confirmed page to look at -- the same
`llm_client`/`sponsor_cache`/`no_sponsors` pattern sprint 013 ticket 005
established, applied a second time; `cli.py` gains a
`--no-descriptions` flag mirroring `--no-sponsors` exactly. None of
this touches `enrich/`, `adapters/`, `normalize.run()`, or
`pipeline.run()`, and description extraction has the same standing
"mirror, never import" relationship to sponsor extraction that sponsor
extraction itself has to `enrich/`. See
`clasi/sprints/021-team-website-verification-and-description-extraction/
sprint.md` for the sprint-level plan this section elaborates.

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
                                       [-v]

BUILT (ticket 011-003):
  sources.tba.TBASource                probes /api/v3/status for
     ↓                                 max_team_page, enumerates every
     ↓                                 /api/v3/teams/{page}, filters to
     ↓                                 CA + SD_COUNTY_CITIES -- 78 teams
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

BUILT (this ticket, 011-005):
  site/src/components/TeamCard.astro         modeled on OpportunityCard.astro
     ↓                                       (title anchor nested inside <h3>),
     ↓                                       NOT PartnerCard.astro -- see
     ↓                                       Design Rationale below
  site/src/components/TeamFilters.astro      clones OpportunityFilters.astro's
     ↓                                       build-time facet-count tally()
  site/src/pages/teams/index.astro           #results-grid / #map-container /
     ↓                                       .results-count / .view-toggle,
     ↓                                       List + Map (no Calendar -- Team
     ↓                                       has no date field)
  site/src/pages/teams/[slug].astro          getStaticPaths() over teams.json;
     ↓                                       slug = Team.team_id (already
     ↓                                       collision-free by construction)
  Header.astro / Footer.astro                "Teams" added to both hard-coded
                                              nav lists

BUILT (sprint 012):
  sources.static_roster.StaticRosterSource   reads committed, contact-stripped
     ↓                                       roster file under teams/data/ --
     ↓                                       never calls the injected Fetcher
  teams/registry/fll-sd.toml                 adapter_type = "static_roster",
     ↓                                       config.sunset_season = "2026-27"
  teams.pipeline._TEAM_SOURCES               gains one entry; run_teams() gains
     ↓                                       a sunset-date staleness WARNING
  (feeds into merge_teams()/geocode_teams()/export_teams(), all unchanged)

BUILT (sprint 013):
  teams.scrape.verify_team_websites()        per-team fetch via the existing
     ↓                                       fetcher/PoliteFetcher seam,
     ↓                                       robots-checked; sets
     ↓                                       Team.website_status; hands the
     ↓                                       fetched body forward in-memory
     ↓                                       (never onto Team)
  teams.sponsor_candidates.                  pure, offline: headings +
    gather_sponsor_candidates()              alt/title text + footer link
     ↓                                       text/hostnames -> candidate
     ↓                                       strings, or [] (no LLM call)
  teams.sponsor_llm.SponsorLLMClient         classifies (selects, never
     ↓                                       generates) candidates via a
     ↓                                       dataclass-derived JSON schema,
     ↓                                       mirrors but never imports
     ↓                                       enrich/llm_client.py
  teams.sponsor_cache.SponsorCache           content-hash cache, mirrors but
     ↓                                       never imports enrich/cache.py
  teams.sponsor_extract.extract_sponsors()   orchestrates the above; verifies
     ↓                                       every returned name is verbatim
     ↓                                       in the candidate list; dedups
     ↓                                       against structured sponsors via
     ↓                                       normalize.partners.
     ↓                                       normalize_org_name; sets
     ↓                                       Team.sponsors/sponsor_provenance
  teams.sources.ftcscout                     sets sponsor_provenance=
     ↓                                       "structured" for its existing
     ↓                                       sponsors
  cli.py `teams --no-sponsors`               skips the LLM stage only;
                                              website verification always runs
  (feeds into teams.export.export_teams(), unchanged -- TEAMS_SCHEMA_FIELDS
   auto-derives sponsor_provenance with no export.py change, same as every
   prior sprint's new Team field)
```

BUILT (sprint 016 ticket 005):
  teams.sources.robotevents.VexTeamSource   RobotEvents API v2 /teams,
     ↓                                      paginated + SD_COUNTY_CITIES
     ↓                                      client-side filter (no
     ↓                                      server-side region param --
     ↓                                      TBA's precedent, not
     ↓                                      FTCScout's)
  teams/registry/vex-sd.toml                adapter_type = "robotevents",
     ↓                                      registered unconditionally
  teams.pipeline._TEAM_SOURCES               gains one entry; discover()
     ↓                                      raises on any probe failure
     ↓                                      (matches sources/tba.py)
  model.Team.number: int -> str              widened; export.py +
                                              site/teams/index.astro gain
                                              a natural-sort key
  (feeds into merge_teams()/geocode_teams()/export_teams(), all
   unchanged -- a fourth source needed zero change to any of the three,
   exactly as sprint 012's static_roster addition already confirmed)

BUILT (sprint 021, ticket 001 -- audit only, no production code):
  teams/data/discovered-websites.toml   52 entries (31 website + 21
     ↓                                  social-only) confirmed to match
     ↓                                  sprint 013 research's own
     ↓                                  meta.websites/meta.social_only
     ↓                                  counts exactly
  (closed one test-coverage gap: an overlay-only-sourced website
   reaches website_status confirmed/unverified through the real
   run_teams() chain end to end -- no other change)

BUILT (sprint 021, ticket 004):
  teams.description_candidates.              pure, offline: meta
    gather_description_content()             description + title +
     ↓                                       h1-h3/p text, concatenated,
     ↓                                       capped at 2000 chars, or ""
     ↓                                       (no LLM call) -- no-email
     ↓                                       guard layer 1 of 3
  teams.description_llm.DescriptionLLMClient  summarizes (never
     ↓                                       generates) the gathered
     ↓                                       text via a dataclass-
     ↓                                       derived JSON schema;
     ↓                                       no-email guard layer 2 of 3
     ↓                                       (system prompt); mirrors
     ↓                                       but never imports
     ↓                                       sponsor_llm.py
  teams.description_cache.DescriptionCache   content-hash cache, mirrors
     ↓                                       but never imports
     ↓                                       sponsor_cache.py
  teams.description_extract.                 orchestrates the above;
    extract_descriptions()                   no-email guard layer 3 of 3
     ↓                                       (code-level rejection of
     ↓                                       the LLM's raw response) +
     ↓                                       length cap; fail-open per
     ↓                                       team; sets Team.description/
     ↓                                       description_status/
     ↓                                       description_provenance/
     ↓                                       description_fetched_at
  cli.py `teams --no-descriptions`           skips this stage only;
                                              website verification and
                                              sponsor extraction still run
  (feeds into teams.export.export_teams(), unchanged -- TEAMS_SCHEMA_FIELDS
   auto-derives the four new fields with no export.py change, same as
   every prior sprint's new Team field)

REMOVED (sprint 019, ticket 001): the `[--no-mirror]`-gated
`export.mirror_site_data()` call ticket 011-002 (above) added after
`teams.export.export_teams()` is gone -- `export/mirror.py` and the
`--mirror-site-dir`/`--no-mirror` CLI flags were removed outright
across the repo, since `partner-scrape` no longer tracks a second site
checkout to mirror into (`site/` becomes a build-time-only CI checkout
of `stem-ecosystem`, sprint 019 ticket 002). `cli.py`'s `teams`
subcommand now returns as soon as `teams.export.export_teams()`
completes.

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
`/api/v3/teams/{page}` (~9,163 teams worldwide, 659 in California --
496 reporting the full state name `"California"`, 163 the bare
abbreviation `"CA"`), filtering down to the 78 in `sources.tba.
SD_COUNTY_CITIES` (an allowlist — see Constraints below for why it
must be one, unlike FTCScout's denylist) after normalizing
`state_prov` to a USPS abbreviation (`_normalize_state()`, ticket
011-003 reopened — see Open Questions for why this normalization step
exists). TBA is the first real source of website (68% of the 78) and
ZIP (87%) coverage; its `lat`/`lng`/`address`/`location_name`/
`gmaps_place_id` fields are
documented in TBA's own OpenAPI spec as "Will be NULL, for future
development" and confirmed NULL for all 78 SD teams, so this source
never reads them at all — **TBA is not a geocoding source**; only
ticket 011-004's `geo.py` sets `Team.latitude`/`longitude`.

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
  select the 78 that are in San Diego County, both by `state_prov`
  (normalized to `"CA"` via `_normalize_state()` — ticket 011-003,
  reopened; see Open Questions) and by `city` matching this allowlist.
  An unrecognized San Diego city is a silent *undercount* here (the
  opposite failure mode from FTCScout's denylist), surfaced via
  `meta.by_league["FRC"]` reading lower than the measured 78 — that
  count is the first place to check if this list ever needs a new
  entry.
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
  dropped to 14 of the original 211-team fixture corpus (13 of the
  real, live 230-team corpus as of ticket 011-003's reopening — see
  Orientation) — a small, meaningful residue (genuine wording
  differences like "Senior"/"Early College", plus the "Classical
  Academy Online" case itself), not matcher noise.
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
- **(Sprint 012) `sources/static_roster.py` never calls the injected
  `Fetcher`, structurally, not just by convention.** Every `TeamSource`
  method still takes `fetcher` as a parameter (the protocol shape is
  unchanged — `sources/base.py`'s `TeamSource` is a fixed three-method
  contract), but `StaticRosterSource.fetch()` reads the committed roster
  file straight off disk (`Path.read_text()`) and ignores the `fetcher`
  argument entirely; `discover()` returns a single `TeamRef` whose `url`
  is a local file path, never an HTTP URL. `tests/teams/
  test_sources_static_roster.py` asserts this with a `Fetcher` test
  double that raises on any call, run through the full `sources.base.run()`
  chain — a stronger guarantee than an unused-parameter convention, the
  same spirit as `test_sources_base.py`'s forbidden-import AST scan
  (Constraints, above) even though the mechanism here is a runtime
  assertion rather than a static one (an AST scan cannot prove a method
  *never calls* an object it legitimately imports the type of).
- **(Sprint 012) Contact fields are stripped at import time, never
  carried into this module.** The upstream roster
  (`../robot-team-analysis/fll/sd-fll-teams-contact-list.md`) carries
  email addresses; the *committed* roster file under `teams/data/` that
  `static_roster.py` actually reads has already had every contact column
  removed before it was committed — `StaticRosterSource.extract()` never
  sees a contact field, let alone filters one out. This is a stronger
  guarantee than "filter emails at extraction time" would have been: a
  bug in a filter can leak; a column that was never committed cannot.
  Combined with `model.Team` having no `email` field at all (existing
  invariant, above), there are now two independent layers between any
  upstream contact data and a published `Team`.
- **(Sprint 012) A `sunset_season` past its date degrades to a loud
  warning, never a failure.** `teams.pipeline.run_teams()` parses
  `SourceConfig.config["sunset_season"]` (a `"YYYY-YY"` string, e.g.
  `"2026-27"`) once per run for any active source that declares it, and
  logs `logging.WARNING` if `date.today()` is past the parsed season-end
  date — the FLL program's own last season is 2026-27, and this project
  has no way to know today what, if anything, replaces it (see Open
  Questions). The roster keeps publishing regardless; a sunset date is a
  staleness signal for an operator to notice and act on, not a reason to
  stop shipping data that may still be the best available answer.
- **(Sprint 013) Fetched HTML is never stored on a `Team` field,
  structurally, not just by convention.** `teams.scrape.
  verify_team_websites()` returns a plain `dict[str, str]` (team_id ->
  fetched body) that `teams.pipeline.run_teams()` holds as a local
  variable and passes directly to `teams.sponsor_extract.
  extract_sponsors()` — it is never assigned to any `Team` attribute.
  This matters because `teams/export.py`'s `TEAMS_SCHEMA_FIELDS` is
  derived from `dataclasses.fields(Team)`, so any field added to the
  dataclass publishes automatically to the public `teams.json`; a raw
  HTML body reaching that mechanism would leak arbitrary third-party
  page content — including, potentially, a coach's personal contact
  info — into a public data contract with no review step. The same
  category of guarantee `model.Team`'s "no email field, ever" docstring
  already establishes for contact data (Constraints, above) is extended
  here to a new mechanism (raw scraped content) that did not exist
  before this sprint.
- **(Sprint 013) A sponsor name is never published unless it appears
  verbatim among a page's deterministically-gathered candidates.**
  `teams.sponsor_extract.extract_sponsors()` validates every name
  `SponsorLLMClient.classify_sponsors()` returns against the exact
  candidate list `teams.sponsor_candidates.gather_sponsor_candidates()`
  produced for that page; a returned name absent from that list is
  dropped and logged, never trusted into `Team.sponsors`. This is the
  sprint's central anti-hallucination guarantee (see Design, below) and
  is enforced in code, not only requested in the LLM prompt —
  `tests/teams/test_sponsor_extract.py` exercises it directly with a
  fixture LLM client that deliberately returns an out-of-list name.
- **(Sprint 013) An LLM call failure during sponsor extraction is
  isolated per team, matching `enrich/`'s "fail open, always" project-wide
  convention (`docs/design/design.md` Sec. 5's "Errors are isolated at
  the level that owns the unit").** A missing `ANTHROPIC_API_KEY`, a
  network error, or a malformed response during
  `SponsorLLMClient.classify_sponsors()` is caught inside
  `extract_sponsors()`'s per-team loop, logged, and leaves that team's
  `sponsors`/`sponsor_provenance` exactly as the structured sources
  already set them — it never raises out of `run_teams()` and never
  affects any other team. Unlike `merge_teams()`/`geocode_teams()`
  (deterministic stages this subsystem already treats as build-time-defect-only,
  never per-record-isolated), sponsor extraction calls an external,
  fallible service per team and is isolated the same way `sources/tba.py`'s
  network calls already are.
- **(Sprint 013) `teams.scrape.verify_team_websites()` checks
  `fetch.is_allowed()` before ever calling `fetcher.get()`, the same
  explicit-check-then-fetch pattern `discovery/hub_scan.py::scan_hub()`
  already uses for its own many-independent-pages loop** — not
  `fetch.cache.PoliteFetcher.get()`'s own internal robots check (which
  raises `RobotsDisallowed`). Checking first and skipping (logged) avoids
  a per-page `try/except RobotsDisallowed` around every one of the 53
  fetches; when the injected `fetcher` *is* a real `PoliteFetcher`, its
  own internal check is redundant but harmless (already confirmed
  allowed) rather than a second, differently-shaped guard.
- **(Sprint 013) `Team.sponsor_provenance` is purely additive to the
  existing `Team.sponsors: list[str]`, never a replacement.** Every
  existing consumer of `sponsors` (`TeamCard`'s Props interface, the
  detail page's `team.sponsors.map(...)`, `tests/teams/test_model.py`,
  `tests/teams/test_sources_ftcscout.py`) continues to see a flat
  `list[str]` with no change; `sponsor_provenance[name]` is a parallel
  lookup a consumer opts into only if it cares which claim is which. See
  Design, below, for the alternative (a restructured `sponsors:
  list[SponsorRecord]`) this rejected.

- **(Sprint 016 ticket 005) `Team.number` is `str`, uniformly — never
  checked with an `isinstance(..., int)` guard anywhere downstream.**
  VEX designations are alphanumeric (`90210A`); `teams/export.py`'s sort
  key and this repo's `site/src/pages/teams/index.astro` comparator both
  use a natural-sort key (leading digit run as `int`, full string as
  tiebreaker — `export.py`'s `_natural_number_key`) rather than bare
  numeric comparison, so a purely-numeric FTC/FRC/FLL value still sorts
  numerically (`"99"` before `"100"`) with no type-specific branch.
  `tests/teams/test_export.py`'s natural-sort regression fixture and
  `tests/teams/test_sources_robotevents.py`'s alphanumeric-sibling-pair
  fixture (`90210A`/`90210B`, distinct `team_id`s) both enforce this
  directly. This ticket did **not** also change `sources/ftcscout.py`'s,
  `sources/tba.py`'s, or `sources/static_roster.py`'s own `number=`
  construction (each still passes the source API's native `int`) — see
  this ticket's own Notes for why that narrower scope was chosen and
  what it means for `teams.json`'s per-team wire type in practice.
- **(Sprint 016 ticket 005) `sources.robotevents.VexTeamSource` follows
  `sources/tba.py`'s "no server-side region filter, raise on any probe
  failure" precedent, not `sources/ftcscout.py`'s denylist-with-a-
  region-scoped-search precedent.** RobotEvents API v2's `/teams`
  endpoint has no city/region query parameter at all (confirmed against
  its published OpenAPI schema) — the identical situation TBA's
  `/api/v3/teams/{page}` is in, not FTCScout's `region=USCASD` search.
  `VexTeamSource.discover()` therefore paginates the full result set and
  `extract()` filters to San Diego County client-side via its own
  `SD_COUNTY_CITIES` allowlist (duplicated from `sources/tba.py`'s, not
  imported — matching the "no shared extraction code beyond the
  `TeamSource` protocol shape" precedent below), and `discover()` raises
  `RuntimeError` on any probe failure (missing/invalid
  `ROBOTEVENTS_KEY`, non-200, unparseable body, invalid
  `meta.last_page`) rather than degrading gracefully the way
  `adapters/robotevents.py`'s own `/events` probe does — see this
  ticket's own acceptance criteria ("matching `sources/tba.py`'s exact
  isolation contract") and `sources/robotevents.py`'s own module
  docstring for the full rationale.

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

**Confirmed true in practice (sprint 012).** `sources/static_roster.py`
needed zero `merge.py` changes to ship. 28 of the FLL roster's 48
records are family/home teams with no sponsoring school — the roster's
own upstream data marks these distinctly from its 20 school-affiliated
records, and `static_roster.py` maps that distinction to
`organization=""`/`org_type="family_community"` the same way
`sources/ftcscout.py` maps its `"Family/Community"` sentinel, landing
in the identical "never group" bucket with no FLL-specific case
anywhere in `merge.py`.

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
convention. Confirmed true a third time (sprint 016 ticket 005):
`sources/robotevents.py` duplicates its own `_clean_city`/
`SD_COUNTY_CITIES`/`_auth_headers` rather than importing any of
`sources/tba.py`'s, even though the underlying San Diego County place
list is identical real-world data — the two sources still change for
unrelated reasons (a different upstream API, a different auth scheme),
so the small duplication is the accepted cost, exactly as this
paragraph's rationale already predicted for a not-yet-written third
source.

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

**Why city-precision teams render as one labelled badge per city, not
individual pins, jittered dots, or a plain cluster marker (this
ticket).** ~70 of the original 211-team fixture corpus sat at
`location_precision: "city"` (73 of the real, live 230-team corpus as
of ticket 011-003's reopening — see Orientation), and
most collapse onto the same handful of city centroids — plotting each
as its own `circleMarker` would stack dozens of markers on one point
and read, visually, as a single team. Three alternatives were rejected
explicitly: jittering (adding a random offset) fabricates precision
`teams.geo` never claimed and would shift on every regeneration, since
nothing anchors the jitter to a stable seed; a plain unlabeled cluster
marker (e.g. a generic clustering plugin) implies the cluster's
centroid itself means something, which it does not — it is a city
centroid, not a computed cluster center; a single stacked pin
misrepresents 62 real teams as one. `teams/index.astro`'s map script
instead groups every visible, in-region, city-precision card by
`data-city` and renders one `L.divIcon` per city carrying a visible
text label (`"San Diego — 40 teams"`) whose popup opens a `<ul>` list
of that city's teams, rather than a single team's popup — the same
distinction SUC-004's acceptance criteria draw. school/zip-precision
teams (a real resolved coordinate) keep the existing `circleMarker`
pin, unchanged from every other map on this site.

**Why teams with `in_region: false` are excluded from the map
entirely, not merely filterable (this ticket).** The ticket's own
instructions left this an explicit decision to make and record.
`Team.in_region` is not redundant with the map's own San Diego bounding
box: measured live, one out-of-region team (`ftc-9902`, city-precision
"San Clemente") has a city centroid that falls *inside* `SD_BOUNDS`
(`lat` 33.449, within the box's `latMax` 33.5), so the bounding-box
check alone would have silently plotted it as if it were a San Diego
County team. `teams/index.astro`'s map script checks
`card.dataset.region !== 'true'` before every other check, so an
out-of-region team is never plotted regardless of its coordinates —
this is a "San Diego teams" map, and a team flagged out-of-region by
`sources.ftcscout.OUT_OF_REGION_CITIES` should not silently contradict
that map's premise. Out-of-region teams are never removed from the
list/filter view, though (SUC-004's Error Flows precedent: flagged,
never dropped) — a "San Diego County Only" checkbox in `TeamFilters`
lets a visitor narrow the list to in-region teams if they want to, but
the default list shows everything, same as `teams.json` itself.

**(Sprint 013) Why sponsor extraction lives entirely inside `teams/` as
new modules that mirror, but never import, `enrich/llm_client.py`/
`enrich/cache.py`.** The issue that motivated this sprint explicitly
points at `enrich/`'s JSON-schema-constrained LLM pattern and
content-hash cache as the pattern to follow. Importing them directly was
considered and rejected: `enrich.llm_client.LLMClient.enrich_event` is
typed to `partner_scrape.model.Event`, and `enrich.cache.EnrichmentCache`
is keyed by `Event.identity_key()` — neither generalizes to a `Team`/HTML
candidate list without changing a public signature that would couple two
modules already changing for unrelated reasons, mirroring
`enrich/llm_client.py`'s own stated reason for not importing
`normalize/taxonomy.py` despite vocabulary overlap ("duplication here is
the accepted cost of keeping this module's one outward dependency the
external Anthropic API, not another in-package module"). This subsystem's
Purpose section and Constraints above already establish, and
`tests/teams/test_sources_base.py` partially enforces, that `teams/` has
zero edges into `enrich/`, `adapters/`, `normalize.run()`, or
`pipeline.run()` — importing `enrich.llm_client` would be the first crack
in that boundary, for a savings of roughly 60 lines of duplicated
schema-building/cache logic. `teams/sponsor_llm.py` therefore duplicates a
small (~15-line) JSON-schema-from-dataclass helper and
`teams/sponsor_cache.py` duplicates `enrich/cache.py`'s content-hash-plus-
schema-version shape; both are self-contained and unlikely to drift since
neither dataclass they serialize (`SponsorExtractionResult`) changes as
often as `EnrichmentResult` might.

**(Sprint 013, ticket 006) The one new outward edge this sprint adds
does not touch the forbidden four.** `teams/website_overrides.py`
imports `partner_scrape.model.slugify` (reused for its host+path
dedup key, per this sprint's "no second normalizer/slugifier"
principle) — the first import from anywhere in `teams/` into the
top-level `partner_scrape.model` module. `partner_scrape.model` is not
one of the four boundaries this subsystem's zero-edges invariant
actually guards (`enrich/`, `adapters/`, `normalize.run()`,
`pipeline.run()`); it is a leaf, dependency-free string utility with no
path back into any of those four, the same shape of reuse `teams/merge.py`
already established for `normalize.partners.normalize_org_name`. The
invariant `tests/teams/test_sources_base.py` enforces is unaffected.

**(Sprint 013) Why the LLM's role is constrained classification over
deterministically-gathered candidates, never open-ended generation.** The
issue names false positives as the dominant risk — asking an LLM "what
are this page's sponsors?" over a full footer will confidently return the
CMS vendor, the hosting provider, the school district, or the site's own
domain. Two alternatives were rejected: sending the whole page (or footer
HTML) and asking the model to name sponsors freely, which is exactly the
failure mode the issue warns about with no structural way to catch a
hallucinated name; and a prompt-only guard with no candidate constraint,
which relies entirely on the model following instructions with no
code-level backstop. Instead, `teams.sponsor_llm.SponsorLLMClient.
classify_sponsors()` is asked to *select from* a list
`teams.sponsor_candidates.gather_sponsor_candidates()` already produced,
and `teams.sponsor_extract.extract_sponsors()` rejects — in code — any
returned name absent from that list (Constraints, above). Fabricating an
unseen company is therefore structurally impossible, not merely
discouraged: the deterministic candidate-gathering pass is the actual
security boundary, and the LLM only narrows within it. The accepted
cost is a false negative — a genuine sponsor named only in flowing body
prose, never as a heading, `alt`/`title` text, or footer link, is missed —
traded deliberately for the much stronger false-positive guarantee the
issue itself prioritizes ("a wrong sponsor attributed to a real company
is worse than an empty list").

**(Sprint 013) Why fetched HTML is threaded through `run_teams()` as a
local `dict[team_id, str]`, never a `Team` field.** See Constraints,
above, for the mechanism; the alternative considered was storing the raw
body on `Team` temporarily and stripping it in `export.py` before
publish — rejected because `export.py`'s whole design point (Sec. 5's
Design entry on `export_teams()`'s field-set derivation) is never needing
a field-specific exclusion list beyond the one existing `sources`
exception; adding a second one for this purpose reintroduces exactly the
drift risk that mechanism exists to avoid. Keeping fetched bodies as a
plain local variable inside `run_teams()`'s own call stack means there is
no field to forget to strip. The accepted consequence is that
`verify_team_websites()` and `extract_sponsors()` must be sequenced
directly inside `run_teams()` rather than being independently
CLI-invokable stages — the same coupling `merge_teams()` and
`geocode_teams()` already accept for the same single-call-sequencing
reason.

**(Sprint 013) Why `Team.sponsor_provenance` is a new `dict[str, str]`
alongside `sponsors: list[str]`, not a restructured `sponsors:
list[SponsorRecord]`.** `TeamCard`'s Props interface, the detail page's
`team.sponsors.map((s: string) => ...)` rendering, and every existing
sponsor test/fixture (`tests/teams/test_model.py`,
`tests/teams/test_sources_ftcscout.py`) already assume `sponsors` is a
flat `list[str]`. Replacing it with a list of name+provenance records
was considered and rejected — it would touch every one of those call
sites for a benefit (structural typing) a parallel dict achieves
losslessly. `sponsor_provenance[name]` answers "is this a structured or
scraped claim?" for any name already in `sponsors`, at zero cost to
existing code paths — the same purely-additive shape sprint 012's Design
Rationale chose for `Team.sources` answering a parallel "is this record
static or live?" question, rather than a new boolean/enum field. The
accepted consequence: a consumer wanting a sponsor's name and provenance
together must join the two fields by key rather than reading one list of
records.

**(Sprint 013) Why sponsor name normalization reuses
`normalize.partners.normalize_org_name`, never
`teams.geo.normalize_school_name` or a new normalizer.** The issue
directs this explicitly, and `teams/merge.py` already established the
precedent of reusing `normalize_org_name`, read-only, for a different
purpose (cross-league organization linking) rather than writing something
new (see this section's own earlier entry, "Why `geo.normalize_school_name`
is a separate function from `normalize.partners.normalize_org_name`").
That earlier entry's reasoning does not reverse here: `geo.
normalize_school_name` exists specifically for CDE/NCES's government-
directory naming quirks for *place* names, which do not apply to
*company* names at all — sponsor names are squarely `normalize_org_name`'s
intended domain (organization-name variant matching), so, unlike
`geo.py`'s deliberate divergence, there is no boundary-crossing concern
reusing it here for a second purpose (sponsor consolidation) alongside its
original one (partner-directory join).

**(Sprint 013, ticket 006 — added post-planning) Why discovered-website
ingestion is a separate module (`website_overrides.py`) that never sets
`website_status`, rather than folded into `scrape.py` or given its own
verification logic.** Ticket 001 (`scrape.py`'s `verify_team_websites()`)
was already fully planned and approved before a web-search discovery
pass (`clasi/sprints/013-team-website-surfacing-and-sponsor-extraction/
research/discovered-websites.json`) found 31 more team websites and 21
social-only teams, and measurement against the live export found 4
`firstinspires.org` junk values and 7 malformed triple-slash URLs among
the original 53. Two things were considered and rejected: folding the
new ingestion/cleanup logic directly into `verify_team_websites()` —
rejected, since editing ticket 001's already-approved content would
conflate two independently-changing concerns (curated-data ingestion,
live-fetch verification) in one function; and having
`website_overrides.py` itself decide `website_status` for
high-confidence or already-re-verified discovered entries (the research
file's own `reverified_status: 200` on every entry, including the 3
`weak`-confidence ones, made this a real temptation) — rejected, because
it would make this module a second, partial, same-day-snapshot
implementation of ticket 001's job. Instead, `website_overrides.py` owns
exactly one thing (populate/clean `Team.website`/`Team.social` from
committed, curated data — the one-sentence, no-"and" cohesion test) and
`verify_team_websites()` remains the sole, uniform authority for
`confirmed`/`unverified`, run immediately afterward so it verifies the
corrected, enlarged set. This is the same "one committed-data-file
loader per concern" shape `geo.py` already established for location
overrides/centroids, applied here to website/social data — not a new
architectural pattern, an application of an existing one. The accepted
consequence is one more sequenced stage inside `run_teams()` (three now,
after `geocode_teams()`), the same single-call-sequencing cost
`merge_teams()`/`geocode_teams()` already require.

## 5. Interfaces

### Exposes
- **`model.Team`** — the record type: `team_id`, `league`
  (`"FTC"`/`"FRC"`/`"FLL"`/`"VEX"`, the last since sprint 016 ticket
  005), `program`, `number` (`str`, widened from `int` by sprint 016
  ticket 005 — see Constraints and Design), `name`, `organization`,
  `org_type`, `city`, `postal_code`,
  `latitude`, `longitude`, `location_precision`, `in_region`,
  `matched_name`, `needs_review` (this ticket), `website`,
  `website_status`, `organization_website`, `rookie_year`, `active`,
  `last_season`, `sponsors`, `sponsor_provenance` (sprint 013,
  `dict[str, str]`, `display sponsor name -> "structured" | "scraped"`),
  `social` (sprint 013 ticket 006, `list[str]`, team-declared social
  URLs — raw, no platform label), `org_key`, `sibling_team_ids`,
  `sources`.
  Every field defaults to an empty/neutral value; no `email` field
  exists (Constraints). Fields are populated incrementally across
  pipeline stages — `sources/ftcscout.py` and `sources/tba.py` set
  identity/organization/city/website/postal_code/sponsors/in-region
  fields; `teams.merge.merge_teams()` sets `org_key`/`sibling_team_ids`;
  `latitude`/`longitude`/`location_precision`/`organization_website`/
  `matched_name`/`needs_review` are set by `teams.geo.geocode_teams()`;
  `website`/`social` are then cleaned/filled by sprint 013 ticket 006's
  `teams.website_overrides.apply_website_overrides()`; `website_status`
  is set next, by sprint 013's `teams.scrape.verify_team_websites()`
  (which now runs after, and sees the corrected/enlarged `website` set
  from, ticket 006's stage); `sponsor_provenance` and any scraped
  additions to `sponsors` are set last of all, by sprint 013's
  `teams.sponsor_extract.extract_sponsors()`.
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
  degrading (Constraints). `extract()` filters each page to
  `_normalize_state(state_prov) == "CA"` (ticket 011-003, reopened —
  normalizes both TBA's `"CA"` and `"California"` forms, and any other
  recognized full US state name, to a USPS abbreviation before
  comparing; see Open Questions) and `city` in `SD_COUNTY_CITIES`.
  Config keys read from `SourceConfig.config`: `api_base` (default
  `config.get_tba_url()`). Auth via `config.get_tba_api_key()`, read
  fresh per call (`_auth_headers()`, matching `adapters/leaguesync.py`'s
  pattern).
- **`sources.static_roster.StaticRosterSource`** (sprint 012) — the
  concrete `TeamSource` for the committed FLL roster file. `discover()`
  returns a single `TeamRef` pointing at the roster path under
  `teams/data/` (read from `SourceConfig.config["roster_path"]`, no
  network URL); `fetch()` reads that file directly off disk, ignoring
  the `fetcher` argument (Constraints); `extract()` maps each roster row
  to a `Team` with `sources=["static_roster"]`, `league="FLL"`, and
  `organization=""`/`org_type="family_community"` for the 28 rows with
  no sponsoring school, mirroring `sources/ftcscout.py`'s sentinel
  mapping (Design). Never sets `latitude`/`longitude`/
  `location_precision` — like every other source, that is exclusively
  `teams.geo.geocode_teams()`'s job, run after this source the same way
  it runs after FTCScout/TBA.
- **`sources.robotevents.VexTeamSource`** (sprint 016 ticket 005) — the
  concrete `TeamSource` for RobotEvents API v2's keyed `/teams`
  endpoint. `discover()` probes `page=1`/`per_page=1` for `meta.
  last_page`, then returns one `TeamRef` per real page; raises
  `RuntimeError` on any probe failure rather than degrading, matching
  `sources.tba.TBASource`'s exact contract (Constraints — not
  `adapters/robotevents.py`'s graceful-degrade one). `extract()` filters
  each page to `city` in its own `SD_COUNTY_CITIES` (duplicated from
  `sources/tba.py`'s, not imported) since `/teams` has no city/region
  query parameter at all. `Team.league = "VEX"` for every record;
  `Team.program` is set verbatim per record from RobotEvents' own
  `program.name` field (distinguishing V5RC vs. VIQRC with no hardcoded
  code-to-label mapping this source would otherwise have to guess at
  without a live token). Config keys read from `SourceConfig.config`:
  `api_base` (default `config.get_robotevents_url()`), `country`
  (optional, unset by default), `per_page` (default 50). Auth via
  `config.get_robotevents_api_key()`, read fresh per call
  (`_auth_headers()`).
- **`teams/registry/ftc-sd.toml`** / **`teams/registry/frc-sd.toml`** /
  **`teams/registry/fll-sd.toml`** / **`teams/registry/vex-sd.toml`**
  (the last, sprint 016 ticket 005) — the FTCScout, TBA, static-roster,
  and RobotEvents sources' `SourceConfig`s, loaded via
  `registry.loader.load_active_sources` pointed at `teams/registry/`
  (not the main `partner_scrape/registry/sources/` directory — a
  separate, disjoint registry namespace). `fll-sd.toml`'s `config` dict
  additionally carries `sunset_season = "2026-27"` (Constraints) — no
  `SourceConfig` schema change, since `config` is already free-form per
  `adapter_type` (`registry/schema.py`).
- **`merge.merge_teams(teams: list[Team]) -> list[Team]`** (this
  ticket) — sets `Team.org_key`/`sibling_team_ids` in place by grouping
  on `normalize.partners.normalize_org_name`-normalized
  `Team.organization`, skipping (never grouping) any team whose
  `organization` is empty. Mutates and returns the same list; called
  once by `teams.pipeline.run_teams()`, after every source has run and
  before `export_teams()`. See Constraints for the full identity rule
  and Design for why it keys on organization name, not team number.
- **`pipeline.run_teams(*, registry_dir=None, source=None, site_dir=None,
  fetcher=None, dry_run=False, geo_data_dir=None, website_data_dir=None,
  llm_client=None, sponsor_cache=None, no_sponsors=False) -> dict`** —
  the programmatic entry point: loads the Team Registry (defaulting to
  the real seed, `teams/registry/`), dispatches each active source to
  its `TeamSource` via `_TEAM_SOURCES`, isolates any one source's
  failure (logged and skipped, matching `pipeline.run()`'s own SUC-008
  contract), links cross-league identity via `merge_teams()`, resolves
  every team's location via `teams.geo.geocode_teams()` (`geo_data_dir`
  overrides the geocoding data directory, mainly for tests), then
  (sprint 013 ticket 006) calls `teams.website_overrides.
  apply_website_overrides(teams, data_dir=website_data_dir)`, then
  (sprint 013) calls `teams.scrape.verify_team_websites(teams, fetcher)`
  and, unless `no_sponsors` (the `--no-sponsors` CLI flag),
  `teams.sponsor_extract.extract_sponsors(teams, fetch_results,
  llm_client, sponsor_cache)` — `llm_client` defaults to a real
  `AnthropicSponsorLLMClient()` and `sponsor_cache` to a real
  `SponsorCache()` when omitted, matching `fetcher`'s existing
  default-to-production convention; tests inject fixture doubles for
  all three (`website_data_dir` included). Hands the fully-populated
  `Team[]` to `export_teams()`. Returns that call's `{"meta": ...,
  "teams": [...]}` payload unchanged.
- **`teams.website_overrides.apply_website_overrides(teams, data_dir=None)
  -> list[Team]`** (sprint 013 ticket 006) — cleans every team's existing
  `website` (clears a `firstinspires.org`/`www.firstinspires.org` junk
  value; repairs a malformed `http:///`/`https:///` URL generically),
  then, for a team whose `website` is still empty, applies a discovered
  `website` from the committed overlay `teams/data/discovered-websites.toml`
  (`data_dir` overrides the directory, mainly for tests) if that team's
  `team_id` has one; sets `Team.social` from the overlay for any team_id
  present there, website or social-only alike. Never sets
  `Team.website_status` (Design — that stays `verify_team_websites()`'s
  sole responsibility, uniformly, regardless of the overlay entry's
  original discovery confidence). The loader mirrors, never imports,
  `teams.geo`'s `_load_overrides`/`_require_file` shape (`tomllib`,
  raises loudly at load time on a missing/malformed file); it also
  guards against a data-authoring collision — two different `team_id`s
  claiming the identical `(host, path)`, compared via
  `partner_scrape.model.slugify` on the parsed URL, never on host alone
  (Constraints: `carlsbaded.org`/`sites.google.com` each legitimately
  recur across distinct-path entries). Mutates and returns the same
  list, matching `merge_teams()`/`geocode_teams()`'s shape. Called once
  by `run_teams()`, after `geocode_teams()` and before
  `verify_team_websites()`.
- **`teams.scrape.verify_team_websites(teams, fetcher) -> dict[str, str]`**
  (sprint 013) — for each `Team` with a non-empty `website`: checks
  `fetch.is_allowed()` first (Constraints), then fetches via `fetcher`.
  Sets `Team.website_status` to `confirmed`/`unverified` in place; a
  `Team` with no `website` gets `"none"`. Returns a `dict[team_id, str]`
  of fetched bodies for every `confirmed` team only — never assigned to
  any `Team` field (Constraints). Called once by `run_teams()`, after
  `apply_website_overrides()` (ticket 006, so it sees the corrected,
  enlarged `website` set) and before `extract_sponsors()`.
- **`teams.sponsor_candidates.gather_sponsor_candidates(html, page_url) ->
  list[str]`** (sprint 013) — pure, offline: parses `html` once (`lxml`),
  collects text from headings matching `/sponsor|partner|thank/i` and
  their following block plus every `<img alt>`/`<img title>` and outbound
  link text/hostname inside any `<footer>` element, deduplicates, and caps
  the result (e.g. 40). Returns `[]` (with a logged warning) for
  unparseable HTML, and `[]` (no warning — the normal case) for a page
  with no sponsor-shaped section. Never raises, never calls a network or
  LLM API. See Design for why the LLM stage only ever selects from this
  function's output.
- **`teams.sponsor_llm.SponsorLLMClient`** (sprint 013) — the injectable
  protocol (`classify_sponsors(candidates: list[str], context: dict) ->
  SponsorExtractionResult`), parallel in shape to
  `enrich.llm_client.LLMClient` but with no import relationship to it
  (Design). `SponsorExtractionResult` (a small dataclass,
  `confirmed_sponsors: list[str]`) drives a JSON-schema-from-dataclass
  generation helper duplicated from, not imported from,
  `enrich.llm_client._build_enrichment_json_schema`'s pattern.
  `AnthropicSponsorLLMClient` is the real implementation
  (`MODEL_ID = "claude-haiku-4-5-20251001"`, matching
  `enrich.llm_client.MODEL_ID`'s value, redefined locally rather than
  imported); `FixtureSponsorLLMClient` is the test double, mirroring
  `enrich.llm_client.FixtureLLMClient`.
- **`teams.sponsor_cache.SponsorCache`** (sprint 013) — a content-hash
  cache keyed by `(team_id, content_hash(candidates))`, one JSON file per
  key under `{SCRAPE_CACHE_DIR}/sponsor_extraction_cache/`, mirroring
  (not importing) `enrich.cache.EnrichmentCache`'s
  `schema_version`-guarded shape. Caching is keyed by the *candidate
  list's* content hash, not the raw page body's, so a page's unrelated
  boilerplate changing (a footer copyright year, an unrelated nav link)
  never forces a re-classification the candidate set itself didn't
  change.
- **`teams.sponsor_extract.extract_sponsors(teams, fetch_results,
  llm_client, cache) -> None`** (sprint 013) — orchestrates, once per
  team with an entry in `fetch_results`: gather candidates -> cache
  lookup -> classify on a miss -> verbatim-candidate validation
  (Constraints) -> a small denylist guard (CMS/hosting vendor names, the
  team's own organization name, the page's own hostname) as
  defense-in-depth -> dedup/merge into `Team.sponsors` against existing
  structured sponsors via `normalize.partners.normalize_org_name` ->
  `Team.sponsor_provenance` updated. Mutates `teams` in place (parallel
  in shape to `merge_teams()`/`geocode_teams()`). Per-team try/except
  around the classify step (Constraints) — an LLM failure for one team
  never touches another.
- **`teams.geo.geocode_teams(teams, *, data_dir=None) -> list[Team]`**
  (this ticket; internals extracted to `geo_ladder.py` in ticket
  018-006, signature/behavior unchanged) — resolves every `Team`
  through the seven-rung offline ladder in place; returns the same
  list (parallel in shape to `merge_teams()`). `data_dir` defaults to
  `geo.DEFAULT_DATA_DIR` (the real committed `teams/data/`). Called
  once by `run_teams()`, after `merge_teams()` and before
  `export_teams()`.
- **`teams.geo.SchoolIndex(data_dir=None)`** (this ticket; as of
  018-006, a thin subclass of `geo_ladder.GeoLadder` — see Orientation)
  — loads all five `teams/data/` files once (inherited
  `GeoLadder.__init__`) and exposes `resolve(team)` (`SchoolIndex`'s
  own method: the full ladder for one `Team`, mutating it in place, via
  the inherited `GeoLadder.locate()`), `resolve_school(org, city)`
  (rungs 1-4, cached), `resolve_zip(postal_code)`/`resolve_city(city)`
  (rungs 5-6, uncached — already O(1) dict lookups), and `match_calls`
  (a counter of actual, uncached rungs-1-4 ladder runs — what
  `tests/teams/test_geo.py`'s per-school-caching tests assert against)
  — the latter four all inherited from `GeoLadder` unchanged. Raises
  `RuntimeError` if any data file under `data_dir` is missing or
  malformed — fails loudly at construction, per SUC-003's Error Flows
  ("a bad geocoding table is a build-time defect"). See Constraints for
  the caching design and Design for the rung ordering.
- **`teams.geo.normalize_school_name(name) -> str` /
  `normalize_city_name(city) -> str`** (this ticket; re-exported from
  `geo_ladder.py` as of 018-006, still importable from `teams.geo`
  unchanged) — the two normalizers `SchoolIndex` matches against; see
  Design for why these are separate from
  `normalize.partners.normalize_org_name`.
- **`partner_scrape.geo_ladder.GeoLadder(data_dir)` /
  `.locate(organization, city, postal_code="") -> LocationMatch`**
  (new, ticket 018-006) — the shared, `Team`-independent engine
  `teams.geo.SchoolIndex` now subclasses. `data_dir` is required (no
  default — unlike `SchoolIndex`, `GeoLadder` has no opinion about
  which subsystem's data directory to fall back to). `locate()` is the
  one generic entry point running the full ladder and returning a
  `LocationMatch` (`latitude`, `longitude`, `location_precision`,
  `matched_name`, `needs_review`, `website`) without mutating anything
  — see `geo_ladder.py`'s own docstring for the full design and
  `tests/test_geo_ladder.py` for its `Team`-independent test coverage.
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
- **`partner-scrape teams [--dry-run] [--source ftcscout|tba|
  static_roster|robotevents] [--site-dir DIR] [-v]`**
  (`cli.py`) — the CLI entry
  point. Constructs a real `PoliteFetcher()` and calls `run_teams()`.
  Never calls `run`/`pipeline.run()` — see `cli.py`'s own module
  docstring and Constraints above. **(Sprint 019, ticket 001)** the
  `--no-mirror` flag and the post-export `export.mirror_site_data`
  call this bullet used to describe were removed outright — see
  `export/DESIGN.md`'s sprint 019 note.
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
  the ladder's algorithmic rungs resolved the real corpus well enough
  that none has been needed yet, whether measured against the original
  211-team fixture or the real, live 230-team corpus ticket 011-003's
  reopening confirmed). All five are plain data, never imported as
  Python.
- **`dev/refresh_school_directories.py`** (this ticket) — the
  standalone, human-run yearly refresh script that produces the four
  generated files above (not `school-overrides.toml`, which is
  hand-maintained only). The only network-capable code in this whole
  subsystem; never imported by `teams.geo` or `teams.pipeline`. See its
  own module docstring for the exact CDE/NCES/Census Gazetteer
  endpoints and filtering rules.
- **Site Presentation Layer** (ticket 011-005) — the browsable `/teams`
  section, entirely in `site/src/`, entirely a read-only consumer of
  `teams.json` (no code here writes back into this subsystem):
  - `site/src/components/TeamCard.astro` — one team's summary card.
    Title anchor nested inside `<h3>` (`<h3><a href={...}>{title}</a></h3>`),
    matching `OpportunityCard.astro`, not `PartnerCard.astro` (see
    Design Rationale for why this matters to the map). Every card
    carries `data-type` (`Team.league`), `data-orgtype`
    (`Team.org_type`), `data-region` (`Team.in_region`), `data-precision`
    (`Team.location_precision`), `data-city`, `data-lat`/`data-lng`, and
    `data-title`/`data-desc` for `scripts/filters.js`'s search.
  - `site/src/components/TeamFilters.astro` — League and Organization
    Type facets (build-time counted via the same `tally()` shape
    `OpportunityFilters.astro` uses) plus a search box and a "San Diego
    County Only" toggle bound to `data-region`.
  - `site/src/pages/teams/index.astro` — the `/teams` index: List/Map
    toggle (no Calendar view — `Team` has no date field, the same real
    difference that makes Partner's simpler two-view toggle the closer
    analog than Opportunity's three-view one here). The map is the one
    piece of real new logic — see the city-badge Design Rationale entry
    above.
  - `site/src/pages/teams/[slug].astro` — one team's detail page.
    `getStaticPaths()` returns one path per `Team.team_id` (already the
    collision-free slug — `f"{league.lower()}-{number}"`, set at
    extraction time — so no separate slug field or slugify step was
    needed). Shows a mini-map with a location-precision caption
    ("Approximate (city center)", etc.) when the team has coordinates,
    and links to any `sibling_team_ids` (e.g. a school's FTC and FRC
    teams, or two FTC teams from the same school).
  - `Header.astro` / `Footer.astro` — "Teams" added to both hard-coded
    nav lists (Header's primary nav and Footer's "Explore" group) —
    they are two separate lists, not shared data, so both needed their
    own edit.
  - Every URL these pages emit goes through the same
    `const base = import.meta.env.BASE_URL.replace(/\/+$/, '')`
    convention every existing page uses.

### Consumes
- **`registry.schema.SourceConfig` / `registry.loader.load_active_sources`
  (from `registry/`)** — reused verbatim for per-league source config;
  no new schema. See `registry/DESIGN.md`.
- **`normalize.partners.normalize_org_name` (from `normalize/`)** —
  `teams/`'s only edge into `normalize/`, read-only, with two call sites
  now: `teams.merge.merge_teams()` (ticket 011-003, cross-league
  organization linking) and, since sprint 013,
  `teams.sponsor_extract.extract_sponsors()` (structured/scraped sponsor
  name consolidation — Design). Both are new callers of the same
  *existing* function, never a new dependency on `normalize/run()` or any
  other part of that pipeline — `teams/` still has no edge into
  `enrich/`, `normalize.run()`, `pipeline.run()`, or either existing
  export writer. See `normalize/DESIGN.md`.
- **`fetch.Fetcher` / `fetch.is_allowed` (from `fetch/`)** — the protocol
  every `TeamSource` method takes as an explicit argument. Production
  wiring to a real `fetch.PoliteFetcher` instance happens in `cli.py`'s
  `_run_teams()` handler, passed through `teams.pipeline.run_teams()`'s
  `fetcher` parameter — nothing in `teams/sources/` or
  `teams/pipeline.py` constructs a concrete fetcher's default itself
  except that one CLI call site, matching `adapters/leaguesync.py`'s
  convention of taking `Fetcher` as a parameter. Since sprint 013, the
  same `fetcher` parameter is also `teams.scrape.
  verify_team_websites()`'s only network dependency (Constraints,
  Interfaces above), and `fetch.is_allowed` is called directly (not only
  via `PoliteFetcher`'s internal check) to short-circuit a
  robots-disallowed URL before ever calling `fetcher.get()`, matching
  `discovery/hub_scan.py::scan_hub()`'s existing pattern. See
  `fetch/DESIGN.md`.
- **`anthropic` SDK (external)** (sprint 013) — `teams.sponsor_llm.
  AnthropicSponsorLLMClient` constructs `anthropic.Anthropic()` with no
  explicit `api_key`, resolving `ANTHROPIC_API_KEY` from the environment
  itself, exactly matching `enrich.llm_client.AnthropicLLMClient`'s own
  documented reason for not going through a `config.py` accessor. This is
  a second, independent construction of the same SDK client type — not a
  shared instance and not an import from `enrich/` (Design) — so a
  missing/invalid key surfaces at `teams.sponsor_extract`'s own call site
  and is caught by its per-team fail-open guard (Constraints), never by
  anything in `enrich/`.
- **`config.get_site_dir()` / `config.get_tba_api_key()` /
  `config.get_tba_url()` (from `config.py`)** — the last two, this
  ticket, mirror `get_leaguesync_api_key()`/`get_leaguesync_url()`
  line-for-line, including the SOPS-decrypted-secret quote-stripping;
  `config.py` remains the only module reading `os.environ`.
  `get_site_dir()` is ticket 011-002's, reused unmodified. See the root
  `partner_scrape/DESIGN.md`.

## 6. Open Questions / Known Limitations

- **(Sprint 012) The FLL successor program, if any, is unknown.** LEGO
  declined to renew its 28-year FIRST partnership on 2026-03-19, making
  2026-27 FLL's last season; `fll-sd.toml`'s `sunset_season` makes that
  loud (Constraints) rather than silent, but this subsystem has no way
  to react to whatever replaces FLL until a successor program actually
  exists with a name, data source, and roster shape — not something to
  speculatively build against now.
- **(Sprint 012) Pre-close verification requirement, carried forward
  directly from the ticket 011-003 lesson.** That defect shipped because
  a hand-authored test fixture (`"CA"` on every record) didn't match
  what TBA's real API actually returned (`"California"` on the
  majority), and was only caught by running the real pipeline during
  sprint validation, not by the fixture-based test suite. The FLL static
  roster is likewise a new external-data source this subsystem has never
  ingested before; its fixture must be a direct excerpt of the real
  committed roster file's rows (not a hand-authored approximation), and
  before this sprint closes, a real `partner-scrape teams --dry-run -v`
  run against the live registry (not fixtures) must confirm 278 teams
  overall and `meta.by_league["FLL"] == 48` — see `sprint.md`'s Test
  Strategy for the exact command. Recorded here as a standing
  reminder for whoever verifies this sprint before close, not just in
  the sprint document, since this file is where the ticket-011-003
  lesson itself was already recorded.
- **RESOLVED (ticket 011-003, reopened 2026-08-28) — a live
  `partner-scrape teams` run during ticket 011-005's work returned
  only 19 of the expected ~59 FRC teams (171 total, not 211); this was
  a real defect, not network conditions on one particular day.** Root
  cause: `sources.tba._extract_one()`'s filter compared TBA's raw
  `state_prov` field to the literal string `"CA"` with no
  normalization. Confirmed live: TBA reports the *full* state name
  (`"California"`) for the majority of San Diego County FRC records
  (59 of the real 78) and only the bare USPS abbreviation (`"CA"`) for
  the rest (19) — the original filter matched only the minority 19 and
  silently dropped the majority 59, with no error or warning logged
  (`TBASource` completed without raising; it just quietly under-filtered).
  Ticket 011-003's original test fixture was hand-authored with
  `"CA"` on every record, so this was never caught in tests — the
  fixture didn't match reality. **Fix:** `sources.tba._normalize_state()`
  maps any recognized full US state name to its USPS abbreviation
  before the comparison runs. **On the 19 `"CA"`-abbreviated records:**
  confirmed real, legitimate historical San Diego County FRC teams
  (verified against `/team/frcNNNN/years_participated`), just
  disproportionately old/inactive (all 19 last competed in or before
  2014) compared to the "California"-labeled 59 (40 of which last
  competed 2023 or later) — TBA's roster has no "active" flag and
  neither source populates `model.Team.active`, so age is not grounds
  to exclude them; both groups are included. **Corrected total,
  confirmed via a real `partner-scrape teams --dry-run` run
  (2026-08-28): 78 FRC, 230 overall (152 FTC + 78 FRC)**, with
  `by_location_precision` `{"school": 120 (79 FTC + 41 FRC), "zip": 33
  (all FRC), "city": 73 (69 FTC + 4 FRC), "none": 4 (all FTC — the same
  two Ensenada teams plus "San Antonio"/"Louisville", unaffected by
  this fix)}` and 13 `needs_review`. The committed fixture corpus was
  rebuilt from real, live-captured TBA records (not all 78 -- see
  `tests/teams/test_sources_tba.py`'s module docstring for the smaller,
  curated 7-record subset actually committed) and is now 159 teams
  (152 FTC + 7 FRC); every count elsewhere in this document citing
  "211"/"59"/"129" describes the now-superseded original fixture
  unless marked otherwise (see Orientation).
- **`school-overrides.toml` ships empty.** The algorithmic rungs (exact
  match + the stopword-normalized Jaccard fuzzy tiers) resolved the
  real corpus well enough that no hand correction was needed — measured
  129 school-precision/14 `needs_review` against the original 211-team
  fixture at ticket 011-004's build, and 120 school-precision/13
  `needs_review` against the real, live 230-team corpus at ticket
  011-003's reopening (see the bullet above) — and none of those flagged
  matches were bad enough to warrant a hand override rather than just a
  flag (each is a real, explainable wording difference — "Senior" vs.
  not, "HS" vs. spelled out, or the genuinely-ambiguous "Classical
  Academy Online" case). Future refreshes or a larger corpus (FLL, a
  follow-on sprint) may
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
- **The ZIP/city centroid tables cover what this ticket's real corpus
  (211-team fixture at ticket 011-004's build; 230-team live corpus as
  of ticket 011-003's reopening) and `sources.tba.SD_COUNTY_CITIES`'s
  full allowlist need, not a hand-picked "~38"/"~25" count the issue's
  early estimate mentioned.** `dev/refresh_school_directories.py` derives 95 ZIP
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
- `sources.tba.SD_COUNTY_CITIES` was originally assembled from this
  project's own historical FRC roster (`data/robot-teams.json`) plus
  every incorporated San Diego County city, not from a live capture of
  TBA's current data (no network access during ticket 011-003's
  original build). Ticket 011-003's reopening (2026-08-28) did perform
  a full live capture of all 24 TBA team pages (9,163 records) as part
  of diagnosing the `state_prov` defect above, and cross-checked every
  San Diego County match against this allowlist — no city was found
  missing (every one of the real 78 matches an existing entry), so this
  list is now empirically validated against live data, not just
  assembled from secondary sources. A San Diego city genuinely present
  in TBA's live data but missing from this list would still silently
  undercount if TBA's roster changes in the future; `meta.by_league
  ["FRC"]` reading below the measured 78 on a real run is the signal to
  check this list first.
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
  (not observed in the 152+78 real live corpus confirmed at ticket
  011-003's reopening, but not structurally impossible) would link —
  there is no
  manual-override mechanism (a `school-overrides.toml`-style table) for
  `merge.py` today.
- Whether `teams.json` is ever joined to the curated partner directory,
  and whether LLM-assisted website discovery is added later, are both
  explicitly out of scope for the whole sprint, not just this ticket —
  see `sprint.md`'s Design Rationale and Scope. (Sprint 013) The new
  per-team sponsor company-name data makes the partner-directory-join
  question more concretely answerable but does not answer it — still
  open.
- **(Sprint 013) `ANTHROPIC_API_KEY` provisioning for the `teams`
  subcommand's scheduled CI runs is unverified** — the exact gap sprint
  011 flagged for `TBA_KEY` (provisioned locally, not confirmed in the
  scheduled workflow's secrets). The main `run` pipeline already depends
  on this key for event enrichment, so it likely already exists in CI,
  but `teams` may run under a different workflow/secret scope. A missing
  key degrades sponsor extraction to a logged warning and
  structured-sponsors-only output (Constraints' fail-open guarantee),
  never aborting the run — but scheduled sponsor extraction silently
  produces nothing useful until this is confirmed.
- **(Sprint 013) Structured+scraped sponsor overlap for the same team is
  currently impossible in the live 278-team corpus** (FTC teams have no
  `website`; FRC teams have no structured `sponsors` field), so
  `extract_sponsors()`'s normalize/dedup/provenance-merge logic is built
  to handle a real collision generally but is exercised only by fixture
  tests, never a live one, this sprint. If a future source ever supplies
  both for the same team, this is the first place to check that the merge
  behaves as designed (structured display name and provenance win; the
  scraped name is absorbed into the same normalized key).
- **(Sprint 013) Whether the false-positive guard (verbatim-candidate
  validation plus a small denylist) is sufficient without a required
  human-sampling step on every future *scheduled* run, not just this
  sprint's one-time close-time review, is unresolved.** This sprint
  requires a human to sample the scraped sponsor output before close
  (see `sprint.md`'s Test Strategy); whether an unattended
  weekly/monthly re-run can be trusted to the code-level guard alone, or
  needs the same review repeated, is a product/process decision this
  sprint does not make.
- **(Sprint 013) Sponsor data is not carried forward between `teams`
  runs.** `Team` objects are rebuilt fresh from their sources every
  `run_teams()` call, with no read-back of the previous `teams.json` —
  the same stateless-rebuild convention every other stage in this
  subsystem already follows (geocoding, merging). For deterministic
  stages that is harmless; for sponsor scraping it means a transient
  fetch failure or a momentarily-down team site on a *later* run silently
  drops that team's previously-scraped sponsors (reverting to whatever
  the structured sources alone provide — currently none, for an FRC
  team) rather than preserving the last known-good result. Not solved
  this sprint — "sponsors only ever grow" is not actually true of this
  design, and a future sprint wanting persistence would need to read back
  the prior `teams.json` before merging, which no stage in this
  subsystem does today for any field.
