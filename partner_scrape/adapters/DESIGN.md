# Adapters

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## Revision (2026-09-02 — ticket 006 exception cycle)

Ticket 006's own required live-verification step (its Fix shape's step 3)
found that `ProgramListingAdapter.discover()`'s sole discovery signal —
100% delegation to `discovery.listing.discover_via_listing`, whose only
match is `discovery.sitemap.EVENT_PATH_RE` against raw `<a href>`
targets — fits neither of this sprint's two headline listing sources'
real markup. The UCSD Summer Program Finder's ~24 HS-eligible cards
(`<li data-grade="High School">…<a class="learnmore" href=…>`) link to
unrelated cross-domain program homepages with no `/program(s)?`-shaped
path segment — 0 of the 24 HS-eligible cards are among the 8 (of ~60)
links `EVENT_PATH_RE` did match. The SIO research-internships page isn't
a cards-link-to-detail-pages listing at all: its ~10 programs
(JT-SURF, MPL, CW3E, CCE LTER, …) are `<div class="page-section">`
blocks whose deadlines are inline prose directly on the summary page,
each linking out (at most) to a program homepage that doesn't itself
carry the deadline — a shape `ProgramListingAdapter`'s card→detail-page
model has no mechanism to represent, regardless of pattern tuning. This
doc's own §6 Open Questions had already named the first risk
speculatively before ticket 006's live verification encountered it for
real, for both sources at once.

**Surface reclassification.** The exception was thrown `surface:
user-visible` (framed as a conflict with SUC-032's Main Flow). The
team-lead reclassified it `internal` before dispatching this revision:
SUC-032's Main Flow describes an outcome — "one Event per listing-page
program card" — and never specifies *how* a card link is identified;
the gap is entirely inside `ProgramListingAdapter.discover()`'s
implementation strategy, a mechanism choice this sprint already owns,
not a renegotiation of anything promised to the stakeholder. No SUC-032
wording changes as a result of this revision.

**Design decision.** The live evidence rules out fixing this by
retuning `EVENT_PATH_RE` — neither target page's link shape is a path
pattern problem. Instead this revision adds two independent, additive
mechanisms, each matched to one of the two page shapes actually
observed (full write-up in §4 below):

1. A configurable CSS-selector discovery strategy for `program_listing`
   sources (`config.link_selector`), alongside — never replacing —
   `EVENT_PATH_RE` matching, for a listing whose card links are
   identified by markup structure/attributes rather than URL path shape.
2. A new `program_page_multi` adapter type for a page whose N program
   records are inline sections on the page itself rather than links to
   N separate detail pages.

Both are designed as the general, reusable capability sprints 029
(competitions) and 030 (educator pages) are already expected to build
on — see §4's "Reuse surface" note. A third, smaller change closes this
doc's own previously-speculative "discovers zero `EventRef`s silently"
Open Question generically, for every adapter type, not only the two
program families.

## 1. Purpose

`adapters/` owns the translation from *one registered source* into *canonical `Event`
records*. It is a subsystem because the codebase deliberately draws a seam between "how
you talk to a particular site or API" (endlessly varied, one implementation per vendor
shape, expected to grow) and everything downstream of it (which only ever sees `Event`).
That seam is what lets a new organization be onboarded by adding a TOML file plus, at
most, one new adapter class — never by editing the pipeline, the normalizer, or the
exporter. Nothing else in the system owns per-vendor protocol knowledge; if vendor
quirks appear outside this directory, the boundary has leaked.

**(Sprint 016 ticket 004)** `robotevents.py` (new) adds an eleventh adapter type,
`robotevents` — VEX Robotics Competition (V5RC/VIQRC) and Aerial Drone Competition
tournament events, via RobotEvents API v2 (`robotevents.com/api/v2`), the first robotics
league besides FIRST this project ingests. Structurally it is `tec_rest`/`localist`'s
exact shape (probe `page=1` at a cheap `per_page`, learn `meta.last_page`, enumerate the
rest) with `leaguesync`'s auth convention (`Authorization: Bearer <token>`, via the new
`config.get_robotevents_api_key()`/`get_robotevents_url()`, mirroring
`get_tba_api_key()`/`get_tba_url()`). One documented deviation from `localist`'s
probe-failure handling: a `401` probe response raises `RuntimeError` immediately (matching
`teams/sources/tba.py`'s explicit-401-raise precedent) rather than degrading to "assume 1
page" — an auth failure is not a transient probe hiccup, and raising here is what lets
`pipeline.run()`'s existing per-source isolation catch it, rather than silently returning
zero events for a broken credential. No `ROBOTEVENTS_KEY` was available during this
ticket's execution (see `config.py`'s own docstring), so the exact `/events` request/
response shape was confirmed against RobotEvents' own published OpenAPI schema (via the
open-source `robotevents` npm client's generated types) rather than a live probe —
documented in `robotevents.py`'s own module docstring, to be re-verified live the first
time a token is provisioned.

**(Sprint 027)** Two new adapter types, `program_page` and `program_listing`, add a
twelfth and thirteenth family: **LLM extraction**, alongside Structured API and HTML.
Where every existing adapter maps a *deterministic* source (a known JSON shape, or
HTML run through `extract/`'s confidence-ranked ladder) into `Event`s, these two map an
arbitrary **prose program page** — a paid summer-research placement, a scholarship
program, an application-window announcement — by asking an LLM to extract a bespoke,
program-shaped field set {name, audience/grades, date range, application window/
deadline, paid/cost, eligibility, open/closed status} that no structured API publishes
and no deterministic ladder rung could recover. See §4 for why this lives here (as a
12th/13th adapter type) rather than as a new top-level subsystem, and for the one
documented deviation from §3's "adapters hold no instance state" invariant this family
needs for test injectability.

## 2. Orientation

The public contract is `base.py`'s `Adapter` Protocol: three methods, `discover` →
`fetch` → `extract`, chained by the module-level `run(source, fetcher)` function.

- `discover(source, fetcher) -> Iterable[EventRef]` resolves a `SourceConfig` into the
  set of fetchable units. For a structured API that is usually "enumerate the pages",
  sometimes after a cheap probe call; for the HTML adapters it delegates to the
  `discovery/` subsystem.
- `fetch(ref, fetcher, source) -> RawResponse` retrieves one unit through the injected
  `Fetcher`. Adapters never open sockets themselves. **(Sprint 015 ticket 003)** gained
  the `source` parameter, matching `discover()`/`extract()`, which already received it
  — see below.
- `extract(raw, source) -> Iterable[Event]` maps one raw body into zero or more `Event`s.

**(Sprint 015 ticket 003)** `fetch()`'s `source` parameter exists so every
implementation can call the new `acquisition_kwargs(source) -> dict[str, Any]` helper
(also in `base.py`) and spread its result into its own `fetcher.get()` call(s):
`fetcher.get(url, **acquisition_kwargs(source))`. `acquisition_kwargs()` reads
`source.acquisition_policy["rate_limit_seconds"]`/`["respect_robots"]`, falling back to
`PoliteFetcher.get()`'s own defaults when a source sets neither — the same
default-merge pattern `run()`'s own `max_urls` handling already uses. Before this
ticket, `fetch()` took only `(ref, fetcher)`, so no adapter's fetch call could reach a
source's acquisition policy at all; every `fetcher.get()` call site in this package's
adapters and in `discovery/sitemap.py`/`discovery/listing.py` (which import
`acquisition_kwargs` from here the same way they already import `EventRef`) now passes
it through. This is what makes `leaguesync.toml`'s `respect_robots = false` — parsed
but previously never threaded anywhere — finally reach `PoliteFetcher.get()`. See
`fetch/DESIGN.md`'s own Sprint 015 addendum for the receiving side.

`run()` is the only chaining logic and is adapter-agnostic: it looks the class up in the
`ADAPTERS` dispatch dict, instantiates it, materializes `discover()`'s output, truncates
it to the source's `max_urls` cap, then loops fetch→extract accumulating events.

Fourteen adapter types are registered today, in three families:

| Family | Types | Shape |
|---|---|---|
| Structured API | `tec_rest`, `wp_rest`, `ical`, `localist`, `bibliocommons`, `greenhouse`, `lever`, `leaguesync`, `robotevents` | Known endpoint, JSON/iCal parsing, `CONFIDENCE = 1.0` |
| HTML | `generic_html`, `listing_html` | URL discovery via `discovery/`, field recovery via `extract/`'s ladder |
| **LLM extraction (sprint 027)** | `program_page`, `program_listing`, `program_page_multi` | One registered page (or one crawled listing's cards, or one page read as N inline records), field recovery via a bespoke `ProgramLLMClient` call, never `extract/`'s ladder |

**(Ticket 006 exception revision) `program_page_multi`.** A third LLM-extraction type,
alongside `program_page`/`program_listing`: one registered page whose body contains N
program records as inline sections (SIO's shape — see this doc's Revision note above),
extracted with a single list-returning LLM call rather than one call per discovered
detail page. See §4's write-up.

`ats_filters.py` is a shared helper, not an adapter: the deterministic
internship / STEM / San-Diego-local classifier the two applicant-tracking-system adapters
(`greenhouse`, `lever`) use to decide whether a job posting becomes an `Event` at all.

## 3. Constraints and Invariants

- **Registration is one line in `adapters/__init__.py`.** New types are added by
  assigning into `ADAPTERS`; `base.py`'s `run()`/`get_adapter()` are never touched. If a
  change to `base.py` looks necessary to add an adapter, the new adapter is being written
  against the wrong contract — fix the adapter, not the dispatch.
- **`ADAPTERS` is populated in `__init__.py`, never in `base.py`.** Each concrete adapter
  imports from `base`, so populating the table inside `base` would create an import
  cycle.
- **Per-record error isolation inside `extract()`.** One malformed record in an otherwise
  good response is logged and skipped, never raised. This is distinct from `pipeline.py`'s
  per-*source* isolation: without it, a single bad row silently discards every other
  record in the same page.
- **`discover()` must return an eagerly-computed list, not a lazy generator with
  per-item side effects.** `run()` materializes and slices the result to enforce
  `max_urls`; a generator whose side effects only fire on iteration would have the cap
  applied after the work was already done.
- **The `max_urls` cap (`acquisition_policy.max_urls`, default 300) is enforced
  centrally and never silently.** It is the adapter-agnostic backstop against one
  pathological source (a "sitemap" that is really hundreds of blog posts) dominating a
  run's wall clock. Truncation logs the discovered count and the dropped count.
- **Adapters do not construct `Fetcher`s.** The `Fetcher` arrives as an argument, chosen
  per source by `pipeline.run()`. No adapter knows whether it is being served static
  `urllib` responses or a headless browser, and none should learn.
- **Adapters hold no instance state.** Instances are constructed fresh per `run()` call
  and every method takes what it needs explicitly. Caching anything on `self` breaks the
  assumption that a fresh instance is equivalent to a reused one.
  **(Sprint 027, documented deviation)** `ProgramPageAdapter`/`ProgramListingAdapter`
  accept optional `llm_client`/`cache` constructor arguments, defaulting to a real
  `AnthropicProgramLLMClient`/`ProgramExtractionCache` when omitted. This is a narrow,
  justified exception, not a reversal of the invariant: `get_adapter()`'s zero-arg
  `adapter_cls()` construction (`base.py`, unchanged) still produces a fully-working
  production instance, since the defaults fill in — no change to `run()`/`get_adapter()`
  was needed, matching §3's "never a change to `base.py`" rule. What the invariant
  actually protects against — a fresh instance behaving differently from a reused one —
  still holds: the constructor argument is a fixed collaborator (an LLM client and a
  content-hash cache), not per-call mutable state, the same distinction `enrich.
  enricher.LLMEnricher(llm_client, cache)` already relies on one layer up. The sole
  reason for the constructor seam is test injectability: no existing adapter has ever
  needed to call an external LLM, so there was no precedent for how a test substitutes
  a fixture for one — every other adapter's "no instance state" is enforced by having
  nothing to inject in the first place. Tests construct
  `ProgramPageAdapter(llm_client=FixtureProgramLLMClient(...), cache=...)` directly and
  call `.extract()`, bypassing `adapters.run()`/`get_adapter()` entirely — exactly how
  every other adapter's own unit tests already call `SomeAdapter().extract(raw, source)`
  directly rather than through the dispatch registry.
  **(Ticket 006 exception revision)** `ProgramPageMultiAdapter` (new, §4) takes the
  identical `llm_client`/`cache` constructor pair for the identical reason — it is not a
  new deviation, just this one's third instance.
- **Deliberate non-goal — no normalization, dedup, or taxonomy work here.** Adapters
  emit raw canonical `Event`s. Collapsing recurrences, cross-source merging, and
  controlled-vocabulary tagging belong to `normalize/`; doing any of it here would apply
  it inconsistently, only to whichever sources happened to implement it.

## 4. Design

**Data shapes.** `EventRef` is a URL plus a free-form `context` dict; it names one
fetchable unit, which for a paginated API is one *page*, not one event. `RawResponse`
carries the originating `ref` alongside `status` and `body`, so `extract()` can log which
page a malformed body came from. Both are inert dataclasses with no behavior.

**Why `discover()` exists at all.** For the structured-API adapters it is nearly trivial
— enumerate known page URLs. It is part of the contract anyway because it is the seam the
HTML adapters need: `generic_html` implements it as a sitemap diff and `listing_html` as
a listing-page crawl, both by delegating to `discovery/`, with no change to `base.py`. The
contract was designed for the harder case before that case existed.

**Confidence.** Structured-API adapters set `CONFIDENCE = 1.0` and record it through
`Event.set(field, value, source, confidence)`, populating `field_provenance`. That
provenance is what lets `normalize/`'s collapse and dedup stages pick the
best-supported record when two sources disagree. HTML adapters instead pass through the
per-field confidence tiers `extract/ladder.py` returns.

**HTML adapters are thin.** `generic_html.py` (88 lines) and `listing_html.py` (103
lines) each do only: call the matching `discovery/` entry point for URLs, fetch, hand the
body to `extract.extract_fields()`, and assemble an `Event` from the returned
`{field: (value, confidence)}` map. All the real extraction logic lives in `extract/`,
all the real URL-resolution logic in `discovery/` — this keeps the two HTML adapters
differing only in their discovery strategy, which is the actual distinction between them.

**`listing_html`'s `default_location` fallback convention. (Sprint 015 ticket 004)**
`ListingHtmlAdapter.extract()` falls back to `source.config.get("default_location", "")`
for `Event.location` only when the extraction ladder recovered no location at all —
never overriding a ladder-recovered value. This exists because some `listing_html` sites
(Fleet Science Center's Drupal `/events` listing, confirmed live) have a single fixed
venue that is never printed per-page for the ladder to recover, so every raw `Event` from
that source carried an empty `location` and could never cross-source-dedup against a
calendar aggregator (e.g. Balboa Park's park-wide TEC feed) that does record the venue —
sprint 014 ticket 004 measured this precisely (0 collapses; see that ticket's Notes).
Deliberately a registry-generic adapter behavior, not Fleet-specific code: any current or
future `listing_html` source with the same fixed-undocumented-venue shape gets the same
fix as a one-line TOML edit (`registry/DESIGN.md`'s "onboarding is a data edit, not a
code change" design point). A source with no `default_location` key reproduces
pre-ticket-004 behavior exactly. The fallback value is recorded via `Event.set()` at
`CONFIDENCE_DEFAULT_LOCATION = 1.0` — an operator-curated, known value from the registry
TOML, not a guess extracted from ambiguous markup, so it is trusted at the ladder's own
top tier rather than a lower one.

**`ical.py` hardening against two live-measured parse failures. (Sprint 016
ticket 001)** Sprint 015 ticket 005's live dry-run verification found the
two highest-yield feeds in the robots-gated batch (`county-parks`, 553 raw
VEVENTs; `sd-astronomy-association`, 677 raw VEVENTs) both returned zero
events, from two distinct `ical.py` bugs unrelated to the robots-policy
question that ticket resolved. Both fixes stay entirely inside `ical.py`:

1. **Tockify's `X-PUBLISHED-TTL:P15M`, and (ticket 002) `REFRESH-
   INTERVAL:P15M`.** Calendar-level properties whose value `icalendar`'s
   duration parser can read as 15 *months* under ISO-8601 grammar rather
   than the 15 *minutes* Tockify evidently intends, which can abort
   `Calendar.from_ical()` before a single `VEVENT` is read. Ticket 001
   shipped a targeted strip of `X-PUBLISHED-TTL:` alone; ticket 002's
   live re-verification of the `county-parks` registration (the same
   feed) found the fix necessary but not sufficient — the identical
   `P15M` value also appears on `REFRESH-INTERVAL:`, immediately
   adjacent in the same `VCALENDAR` header, still aborting the parse.
   `extract()` now strips both known lines (via `_NONSTANDARD_DURATION_RE`,
   built from the `_NONSTANDARD_DURATION_PROPERTIES` list) before the
   body reaches `from_ical()` — properties this adapter never reads
   anyway. Deliberately a targeted strip of the evidenced properties, not
   a general X-property/custom-property sanitizer: a different malformed
   property still fails loudly through the existing top-level
   `except Exception` around `from_ical()`, until a third real case
   justifies widening the list further.
2. **A `VEVENT` with more than one `RRULE` property.** `icalendar`
   returns a Python `list` for `component.get("rrule")` in this case;
   `_extract_component` previously assumed a single `vRecur` and crashed
   (`AttributeError: 'list' object has no attribute 'to_ical'`) — an
   exception type outside `extract()`'s then-existing per-`VEVENT` catch
   (`ValueError, TypeError, KeyError`), so it escaped the per-record loop
   and aborted the whole source. `_extract_component` now detects a
   list-valued `rrule_prop`, logs a warning naming how many additional
   rules were discarded, and salvages via the first rule — matching RFC
   5545's technical allowance for multiple `RRULE`s while keeping the
   expansion itself unchanged. `extract()`'s per-`VEVENT` catch is also
   widened from the three-exception tuple to `except Exception`,
   matching this module's own top-level precedent above and the §3
   per-record-isolation invariant directly — the narrower tuple was
   itself the bug that let the `AttributeError` propagate.

**ATS adapters are a filtered family.** `greenhouse` and `lever` read public job-board
JSON, then run `ats_filters.classify_posting()` to decide whether a posting is an
internship, is STEM, and is San Diego-local. Postings that survive become
`kind="internship"` Events, which are treated specially further downstream (they bypass
LLM enrichment and both normalize stages). Graduate/PhD-level postings are rejected
here; the project's audience is K-12.

**(Sprint 027) Why the new family lives inside `adapters/`, not a new top-level
subsystem.** `adapters/`'s own one-sentence purpose — "translate one registered source
into canonical `Event` records" — describes `program_page`/`program_listing` exactly;
only the *means* of extraction differs (an LLM call instead of a JSON parse or the HTML
ladder), which the `Adapter` Protocol (`discover → fetch → extract`) never constrained
in the first place. `teams/` was the precedent considered and rejected: it is a
*second, independent pipeline* precisely because a `Team` never becomes an `Opportunity`
(`partner_scrape/DESIGN.md`'s Sprint 011 note). A program page's `Event` *does* flow
through the normal `normalize.run()` → `export.writer` path (it only skips two of
`normalize/`'s internal stages — see `normalize/DESIGN.md`), so it belongs where every
other `Opportunity`-bound source's adapter lives.

**New modules, one new capability.** `adapters/program_page.py` defines
`ProgramPageAdapter` (`discover()` returns the one configured URL as a single
`EventRef`, mirroring `greenhouse.py`/`lever.py`'s "no probe-then-paginate" shape) and
`ProgramListingAdapter` (`discover()` crawls `source.config["listing_urls"]` and
returns one `EventRef` per matched card/detail link, reusing
`discovery.listing.discover_via_listing` — the same mechanism `listing_html` already
uses, since `EVENT_PATH_RE` already matches a `/program(s)?` path segment). Both share
one `extract()` implementation: check `adapters/program_cache.py`'s
`ProgramExtractionCache` by URL + content-hash (mirrors `enrich/cache.py`'s shape,
minus the `Event`-identity keying — there is no `Event` yet at fetch time, only a URL
and a page body). Unlike `enrich/cache.py`'s deliberately single-threaded writes
(`enrich/DESIGN.md`'s Constraints), concurrent writes here are safe by construction
without that same restriction: `pipeline.py`'s per-*source* `ThreadPoolExecutor` is the
only concurrency in play, each source's own `adapters.run()` call processes its
discovered refs sequentially within that one worker thread, and every cache key is a
distinct URL+hash — two threads can only ever write two different files, never the
same path, so no lock or single-threaded discipline is needed here. On a miss, call the
injected `ProgramLLMClient`
(`adapters/program_llm.py` — `enrich_program(url, body) -> ProgramExtractionResult`,
its JSON schema generated from the dataclass exactly as `enrich/llm_client.py`'s
`_build_enrichment_json_schema()` already does, per this sprint's own explicit
"reusing `enrich/llm_client.py`'s structured JSON-schema pattern" framing);
map the result onto a canonical `Event` (`kind` from the source's `program_kind`
config; `start`/`end` as the application-window open/deadline; `eligibility` and
`opportunity_type` set via `Event.set(...)`, so `normalize/`'s existing
field_provenance-presence precedence picks them up with no further code change — see
`normalize/DESIGN.md`).

**Deliberately mirrors, never imports, `enrich/llm_client.py`.** Same rationale as
`teams/sponsor_llm.py`'s sprint 013 precedent (`teams/DESIGN.md`): a second Anthropic
client sharing the injectable-Protocol/JSON-schema-from-dataclass *shape* costs one
more small module, versus reaching across the `adapters` → `enrich` layering this
codebase has never needed and does not want — `enrich/`'s own constraint that it "never
imports `normalize/taxonomy.py`" despite overlapping vocabulary is the same accepted
duplication-over-coupling trade, applied here to a sibling module instead.

**Kind, not `opportunity_type`, is this mechanism's discriminator.** A registered
source's `program_kind` config (`"internship"` or `"program"`) sets `Event.kind`
directly; `opportunity_type` is a separate, independent decision (forced to
`Work-based Learning` for `kind="internship"`, exactly as today; read from the LLM
extraction result or a fixed per-source override for `kind="program"`). This keeps the
bypass mechanism (§3's constructor note; `enrich/DESIGN.md`, `normalize/DESIGN.md`)
orthogonal to which `opportunity_type` a given program ultimately displays as — the
same separation the codebase already has between `kind`-based routing (collapse/dedup
bypass) and `opportunity_type`-based display rules (`DEADLINE_FIRST_TYPES`).

**(Ticket 006 exception revision) Selector-based listing discovery, alongside
`EVENT_PATH_RE` — never replacing it.** `discovery/listing.py` gains a sibling function,
`discover_via_selector(source, fetcher)`, used by `ProgramListingAdapter.discover()`
only when `source.config` sets `link_selector` (a CSS selector string); a source with no
`link_selector` key reproduces today's `discover_via_listing`/`EVENT_PATH_RE` behavior
exactly, so `listing_html`'s existing Fleet Science Center registration and any future
`program_listing` source whose card links genuinely are `/program(s)?`-shaped are
unaffected. The two functions share the same per-listing-page fetch loop (resolve each
`config.listing_urls` entry against `config.site_url`, GET via `acquisition_kwargs`, skip
a non-200 page with a logged warning) and differ only in how links are picked out of the
parsed tree: `EVENT_PATH_RE.search()` against every `<a href>` for the existing function,
`tree.cssselect(link_selector)` for the new one. Deliberately no separate
"grade filter" or "allow-cross-domain" config key: an operator-authored CSS selector
already expresses both "which links" and "which cards" in one string — UCSD's own
registration uses `li[data-grade*="High School"] a.learnmore`, which is simultaneously
the discovery pattern and the HS-eligibility filter, live-confirmed against the real
page markup during this revision. No cross-domain restriction is introduced because none
existed before: `EVENT_PATH_RE` already matched "any href containing the pattern,
regardless of domain" (this doc's own pre-revision Open Question said so), so a
selector-based match inherits the identical, already-accepted absence of a domain check.

**(Ticket 006 exception revision) `program_page_multi`: one page, N inline program
records.** `ProgramPageMultiAdapter` (`adapters/program_page.py`) shares
`ProgramPageAdapter`'s `discover()` verbatim — a `program_page_multi` source is still one
fixed configured URL, one `EventRef`, no probe-then-paginate step — and differs only in
`extract()`: it calls a new `ProgramLLMClient.extract_programs(url, body) ->
list[ProgramExtractionResult]` method (added to the Protocol alongside the existing
singular `extract_program`, implemented on both `AnthropicProgramLLMClient` — a second
structured-output schema wrapping the same per-record object in `{"programs": [...]}`
— and `FixtureProgramLLMClient`) and maps each returned result onto its own `Event`, via
the same field-mapping logic `_extract_one_program` already applies per result. All N
Events from one page share the same `url`/`source_id`; this is safe by construction, not
by convention, because `Event.identity_key()` never keys on `url` — it is
`(source_id, external_id)` when set, else `(source_id, normalized_title, start_date)`
(`model.py`) — so N records with N distinct titles already get N distinct identity keys
with no adapter-side bookkeeping. `ProgramExtractionCache` gains a parallel
`lookup_many`/`store_many` pair, keyed identically (URL + content hash) but storing a
JSON list instead of one object; the cache's `_CACHE_SCHEMA_VERSION` is bumped once,
which forces exactly one harmless re-extraction of any pre-revision cache entry (a cache
is a pure optimization, so a version-forced miss costs one extra LLM call, never a
correctness issue — matching this cache's own existing "missing key or stale version is
a miss, not a deserialization error" contract).

**Reuse surface for sprints 029/030.** `program_page_multi` is deliberately generic, not
SIO-specific: any future curated page whose N records live as sections on one page —
named explicitly in this sprint's own dispatch as issue 30's competition pages and
issue 33's educator-program pages — registers as a `program_page_multi` source with zero
further adapter code, the same "onboarding is a data edit" property `program_page`/
`program_listing` already have. This is this revision's answer to the dispatch's
explicit ask to "design that surface for reuse."

**(Ticket 006 exception revision) Zero-discovered-refs is no longer silent.**
`adapters/base.py`'s `run()` now logs a `logger.warning` immediately after
`refs = list(adapter.discover(source, fetcher))`, naming `source_id`, `adapter_type`,
and the zero count, whenever an enabled source's (pre-truncation) discovery yields no
refs at all — generic across all fourteen adapter types, not only the two program
families, alongside the existing max_urls-truncation warning in the same function. This
resolves this doc's own pre-revision Open Question ("a future `program_listing` source
whose card links don't contain any matched path segment... would discover zero
`EventRef`s silently") directly at its cause. It is a complement to, not a duplicate of,
`observability/yield_report.py`'s existing per-run zero-yield alert (which already flags
a source whose final Event count is zero): the yield report cannot distinguish "discover()
itself found nothing" from "discover() found candidates but every one failed fetch or
extraction" — this warning fires at the earlier, more specific point, giving an operator
looking at logs (not only a periodic yield report) the finer-grained signal for exactly
the failure mode ticket 006 hit.

**Why a Protocol rather than an ABC.** Structural typing keeps concrete adapters from
needing to inherit anything, and keeps test doubles trivial — a plain object with the
three methods is a valid `Adapter`.

## 5. Interfaces

### Exposes
- **`run(source: SourceConfig, fetcher: Fetcher) -> list[Event]`** — the whole
  subsystem's entry point. Dispatches on `source.adapter_type`, chains
  discover→fetch→extract, applies the `max_urls` cap. Raises `UnknownAdapterType` if the
  type is unregistered; per-record failures inside `extract()` are swallowed by the
  adapter itself, so this returns a possibly-short list rather than raising. A
  fetch-level failure surfaces as a `RawResponse` with a non-2xx or sentinel status,
  which `extract()` is responsible for handling. **(Ticket 006 exception revision)** also
  logs a warning (never raises) when `discover()` returns zero refs for an enabled
  source, for every adapter type — see §4.
- **`Adapter` Protocol, `EventRef`, `RawResponse`** — the contract a new adapter type
  implements.
- **`ADAPTERS: dict[str, type[Adapter]]`** — the dispatch table. Mutated exactly once per
  type, at import of `adapters/__init__.py`.
- **`get_adapter(adapter_type) -> Adapter`** — instantiates a registered adapter; raises
  `UnknownAdapterType` with the known-type list rather than a bare `KeyError`.
- **`ats_filters.classify_posting(...) -> PostingVerdict`** — shared internship/STEM/
  locality classification for the ATS adapters.
- **`acquisition_kwargs(source: SourceConfig) -> dict[str, Any]`** — **(Sprint 015
  ticket 003)** the `rate_limit_seconds`/`respect_robots` kwargs for `fetcher.get()`,
  read from `source.acquisition_policy`. Consumed by every `fetch()` implementation in
  this package and by `discovery/sitemap.py`/`discovery/listing.py`, which import it
  from here the same way they already import `EventRef` — see §2.
- **`ProgramPageAdapter(llm_client=None, cache=None)`, `ProgramListingAdapter(llm_client=
  None, cache=None)`** (sprint 027) — the two original adapter types; see §3's
  constructor-injection note and §4's Design. **`ProgramPageMultiAdapter(llm_client=None,
  cache=None)`** (ticket 006 exception revision) — the third, "one page, N inline
  records" type; identical constructor shape, see §4.
- **`ProgramLLMClient` Protocol, `ProgramExtractionResult`, `AnthropicProgramLLMClient`,
  `FixtureProgramLLMClient`** (sprint 027, `adapters/program_llm.py`) — the injectable
  LLM-extraction seam and its production/test implementations, structurally parallel to
  `enrich/llm_client.py`'s `LLMClient`/`EnrichmentResult`/`AnthropicLLMClient`/
  `FixtureLLMClient` but never importing them (see §4). **(Ticket 006 exception
  revision)** `ProgramLLMClient` gains a second method, `extract_programs(url, body) ->
  list[ProgramExtractionResult]`, for `program_page_multi`'s one-page/N-record shape;
  both real and fixture implementations now support both methods.
- **`ProgramExtractionCache(cache_dir=None)`** (sprint 027, `adapters/program_cache.py`)
  — one JSON file per URL+content-hash under `{SCRAPE_CACHE_DIR}/
  program_extraction_cache/`, avoiding a repeat `ProgramLLMClient` call for an unchanged
  page across pipeline runs. Mirrors `enrich/cache.py`'s shape; a separate cache
  directory and class, not a reuse of `EnrichmentCache`, because the cache key differs
  (URL, not `Event.identity_key()` — no `Event` exists yet at fetch time). **(Ticket 006
  exception revision)** gains `lookup_many`/`store_many`, the list-valued counterpart to
  `lookup`/`store`, for `program_page_multi`; `_CACHE_SCHEMA_VERSION` is bumped once for
  the new entry shape (see §4).

### Consumes
- **`Fetcher` (from `fetch/`)** — every remote read. Injected per call; see `fetch/DESIGN.md`.
- **`SourceConfig` and `DEFAULT_MAX_URLS_PER_SOURCE` (from `registry/`)** — the per-source
  data that drives dispatch and the URL cap. See `registry/DESIGN.md`.
- **`Event`, `Provenance` (from `model.py`)** — the output record. See the root
  `partner_scrape/DESIGN.md`.
- **`discover_changed_urls` / `discover_via_listing` (from `discovery/`)** — URL
  resolution for the two HTML adapters. See `discovery/DESIGN.md`. **(Ticket 006
  exception revision)** `discover_via_selector`, the new sibling function, is consumed by
  `ProgramListingAdapter.discover()` the same way, when `config.link_selector` is set.
- **`extract_fields` (from `extract/`)** — per-field values and confidences for the two
  HTML adapters. See `extract/DESIGN.md`.
- **`config.get_leaguesync_api_key` / `get_leaguesync_url` (from `config.py`)** — the
  `leaguesync` adapter's credentials, read through the one module allowed to touch
  `os.environ`.
- **`config.get_robotevents_api_key` / `get_robotevents_url` (from `config.py`)**
  — **(Sprint 016 ticket 004)** the `robotevents` adapter's credentials, same
  `os.environ`-isolation convention as `leaguesync`'s pair above.
- **The `anthropic` SDK** (sprint 027, `program_llm.py`'s `AnthropicProgramLLMClient`
  only) — reads `ANTHROPIC_API_KEY` itself, not routed through `config.py`, matching
  `enrich/llm_client.py`'s identical credential convention. This is a new external
  dependency for `adapters/` specifically (the package as a whole already depended on
  `anthropic` transitively via `enrich/`, but no adapter had ever called it directly).
- **`config.get_scrape_cache_dir()` (from `config.py`)** (sprint 027,
  `program_cache.py`) — the parent of `program_extraction_cache/`, matching
  `enrich/cache.py`'s and `store/event_store.py`'s existing convention.

## 6. Open Questions / Known Limitations

- There is a real circular-import hazard between `adapters.listing_html` and
  `discovery.listing`: each needs a name from the other's package. `cli.py` works around
  it by importing `partner_scrape.pipeline` before `partner_scrape.discovery`, with an
  explanatory comment. That is a load-order workaround, not a fix; the cycle should be
  broken properly (most likely by moving the shared path regex out of `discovery`).
- `EventRef.context` is an untyped `dict[str, Any]`. It works, but there is no schema and
  no cross-adapter convention for what goes in it.
- Every adapter re-implements its own `_strip_html`, `_parse_datetime`, and HTML-entity
  table. Five near-identical copies exist. Deduplication was deferred on the grounds that
  each adapter's version has drifted to fit its own source's quirks; that reasoning is
  worth re-testing.
- `bibliocommons`'s audience prefilter defaults `KEEP_IF_UNKNOWN_AUDIENCE = True`, which
  is deliberately permissive and relies on the downstream LLM relevance gate to catch
  what it lets through. If enrichment is disabled (`--no-enrich`), that safety net is
  absent.
- **(Sprint 027, real risk, not yet fully resolved)** A program named in both a
  `program_listing` source's crawl (e.g. the UCSD Summer Program Finder's own COSMOS/
  OPTIMUS/ENLACE cards) and a separately-registered individual `program_page` source
  for the same program would publish as two distinct `Opportunity` records — `kind in
  PROGRAM_EXTRACTION_KINDS` records bypass cross-source dedup entirely (§4;
  `normalize/DESIGN.md`), by design, for the correct reason (distinct internship
  postings/programs are not recurrences of each other), but that same bypass means this
  one accidental case is never caught automatically. Registering these two source
  families for the same real-world program is a data-authoring error, not a code
  defect — ticket-level work must reconcile the seed list (issue 28's own bullets name
  COSMOS/OPTIMUS/ENLACE in both the listing description and the individual-pages list)
  before both go live, and no code-level guard against it exists yet.
- **(Sprint 027, RESOLVED by the ticket 006 exception revision)** ~~`discovery.listing.
  discover_via_listing`'s `EVENT_PATH_RE` matches any href containing a `/program(s)?`
  path segment, regardless of domain — reused as-is for `ProgramListingAdapter`... A
  future `program_listing` source whose card links don't contain any matched path
  segment would discover zero `EventRef`s silently.~~ This is exactly what ticket 006's
  live verification hit for both of this sprint's actual listing sources — see this
  doc's Revision note and §4. Resolved by the new `config.link_selector` discovery path
  (for a shape a CSS selector can express) and the generic zero-refs warning (for
  whatever shape still isn't covered). **Residual, not solved here:** no automatic
  re-check that a registered `link_selector` still matches after a target site's markup
  changes — a silent drift back to zero cards is caught by the new warning and by
  `observability/`'s yield report, but nothing re-validates the selector itself or
  alerts on a *partial* drift (e.g. 24 cards silently becoming 3). Not built
  speculatively; revisit if a registered `link_selector` source is ever observed to
  drift.
- **(Ticket 006 exception revision)** `program_page_multi`'s per-page LLM call has no
  guard against the model returning near-duplicate records for what is really one
  program described twice in different words on the same page (SIO's own page has no
  such duplication today, live-confirmed). Cross-record dedup *within* one
  `program_page_multi` extraction is not built — `kind in PROGRAM_EXTRACTION_KINDS`'s
  existing cross-source dedup bypass (§4, `normalize/DESIGN.md`) means nothing
  downstream would catch it either. Not solved speculatively; revisit if a real page
  exhibits this.
- **(Sprint 027)** No per-run cost/latency budget exists for `ProgramLLMClient` calls
  beyond `ProgramExtractionCache`'s cross-run reuse — a `program_listing` source's
  `extract()` calls the LLM once per discovered card, sequentially, within that one
  source's `adapters.run()` call (concurrency exists only *across* sources, via
  `pipeline.py`'s existing `ThreadPoolExecutor`). At this sprint's scale (~21 UCSD cards
  plus a handful more) this is an accepted, unmeasured cost; a future listing source
  with materially more cards might need its own bounded concurrency, mirroring
  `enrich/enricher.py`'s pattern — not built here. **(Ticket 006 exception revision)**
  `program_page_multi` is one call per page regardless of how many records it returns
  (cheaper per-record than `program_listing`'s one-call-per-card, since SIO's ~10
  programs cost one call, not ten) — this doesn't change the calculus above, just notes
  the new type's own cost shape for whoever revisits this.
