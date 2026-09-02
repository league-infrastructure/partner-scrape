---
source_file: adapters-DESIGN.md
source_hash: c43a86f6a68513c592e9a1a3b3da667dbfc2cdaba3e19e93f14e256850df1c4f
---
# Diff: adapters-DESIGN.md

Comparison of the sprint overlay copy of `adapters-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- adapters-DESIGN.md (pristine)
+++ adapters-DESIGN.md (current)
@@ -3,6 +3,59 @@
 **Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
 
 ---
+
+## Revision (2026-09-02 — ticket 006 exception cycle)
+
+Ticket 006's own required live-verification step (its Fix shape's step 3)
+found that `ProgramListingAdapter.discover()`'s sole discovery signal —
+100% delegation to `discovery.listing.discover_via_listing`, whose only
+match is `discovery.sitemap.EVENT_PATH_RE` against raw `<a href>`
+targets — fits neither of this sprint's two headline listing sources'
+real markup. The UCSD Summer Program Finder's ~24 HS-eligible cards
+(`<li data-grade="High School">…<a class="learnmore" href=…>`) link to
+unrelated cross-domain program homepages with no `/program(s)?`-shaped
+path segment — 0 of the 24 HS-eligible cards are among the 8 (of ~60)
+links `EVENT_PATH_RE` did match. The SIO research-internships page isn't
+a cards-link-to-detail-pages listing at all: its ~10 programs
+(JT-SURF, MPL, CW3E, CCE LTER, …) are `<div class="page-section">`
+blocks whose deadlines are inline prose directly on the summary page,
+each linking out (at most) to a program homepage that doesn't itself
+carry the deadline — a shape `ProgramListingAdapter`'s card→detail-page
+model has no mechanism to represent, regardless of pattern tuning. This
+doc's own §6 Open Questions had already named the first risk
+speculatively before ticket 006's live verification encountered it for
+real, for both sources at once.
+
+**Surface reclassification.** The exception was thrown `surface:
+user-visible` (framed as a conflict with SUC-032's Main Flow). The
+team-lead reclassified it `internal` before dispatching this revision:
+SUC-032's Main Flow describes an outcome — "one Event per listing-page
+program card" — and never specifies *how* a card link is identified;
+the gap is entirely inside `ProgramListingAdapter.discover()`'s
+implementation strategy, a mechanism choice this sprint already owns,
+not a renegotiation of anything promised to the stakeholder. No SUC-032
+wording changes as a result of this revision.
+
+**Design decision.** The live evidence rules out fixing this by
+retuning `EVENT_PATH_RE` — neither target page's link shape is a path
+pattern problem. Instead this revision adds two independent, additive
+mechanisms, each matched to one of the two page shapes actually
+observed (full write-up in §4 below):
+
+1. A configurable CSS-selector discovery strategy for `program_listing`
+   sources (`config.link_selector`), alongside — never replacing —
+   `EVENT_PATH_RE` matching, for a listing whose card links are
+   identified by markup structure/attributes rather than URL path shape.
+2. A new `program_page_multi` adapter type for a page whose N program
+   records are inline sections on the page itself rather than links to
+   N separate detail pages.
+
+Both are designed as the general, reusable capability sprints 029
+(competitions) and 030 (educator pages) are already expected to build
+on — see §4's "Reuse surface" note. A third, smaller change closes this
+doc's own previously-speculative "discovers zero `EventRef`s silently"
+Open Question generically, for every adapter type, not only the two
+program families.
 
 ## 1. Purpose
 
@@ -34,6 +87,19 @@
 documented in `robotevents.py`'s own module docstring, to be re-verified live the first
 time a token is provisioned.
 
+**(Sprint 027)** Two new adapter types, `program_page` and `program_listing`, add a
+twelfth and thirteenth family: **LLM extraction**, alongside Structured API and HTML.
+Where every existing adapter maps a *deterministic* source (a known JSON shape, or
+HTML run through `extract/`'s confidence-ranked ladder) into `Event`s, these two map an
+arbitrary **prose program page** — a paid summer-research placement, a scholarship
+program, an application-window announcement — by asking an LLM to extract a bespoke,
+program-shaped field set {name, audience/grades, date range, application window/
+deadline, paid/cost, eligibility, open/closed status} that no structured API publishes
+and no deterministic ladder rung could recover. See §4 for why this lives here (as a
+12th/13th adapter type) rather than as a new top-level subsystem, and for the one
+documented deviation from §3's "adapters hold no instance state" invariant this family
+needs for test injectability.
+
 ## 2. Orientation
 
 The public contract is `base.py`'s `Adapter` Protocol: three methods, `discover` →
@@ -68,12 +134,19 @@
 `ADAPTERS` dispatch dict, instantiates it, materializes `discover()`'s output, truncates
 it to the source's `max_urls` cap, then loops fetch→extract accumulating events.
 
-Eleven adapter types are registered today, in two families:
+Fourteen adapter types are registered today, in three families:
 
 | Family | Types | Shape |
 |---|---|---|
 | Structured API | `tec_rest`, `wp_rest`, `ical`, `localist`, `bibliocommons`, `greenhouse`, `lever`, `leaguesync`, `robotevents` | Known endpoint, JSON/iCal parsing, `CONFIDENCE = 1.0` |
 | HTML | `generic_html`, `listing_html` | URL discovery via `discovery/`, field recovery via `extract/`'s ladder |
+| **LLM extraction (sprint 027)** | `program_page`, `program_listing`, `program_page_multi` | One registered page (or one crawled listing's cards, or one page read as N inline records), field recovery via a bespoke `ProgramLLMClient` call, never `extract/`'s ladder |
+
+**(Ticket 006 exception revision) `program_page_multi`.** A third LLM-extraction type,
+alongside `program_page`/`program_listing`: one registered page whose body contains N
+program records as inline sections (SIO's shape — see this doc's Revision note above),
+extracted with a single list-returning LLM call rather than one call per discovered
+detail page. See §4's write-up.
 
 `ats_filters.py` is a shared helper, not an adapter: the deterministic
 internship / STEM / San-Diego-local classifier the two applicant-tracking-system adapters
@@ -106,6 +179,28 @@
 - **Adapters hold no instance state.** Instances are constructed fresh per `run()` call
   and every method takes what it needs explicitly. Caching anything on `self` breaks the
   assumption that a fresh instance is equivalent to a reused one.
+  **(Sprint 027, documented deviation)** `ProgramPageAdapter`/`ProgramListingAdapter`
+  accept optional `llm_client`/`cache` constructor arguments, defaulting to a real
+  `AnthropicProgramLLMClient`/`ProgramExtractionCache` when omitted. This is a narrow,
+  justified exception, not a reversal of the invariant: `get_adapter()`'s zero-arg
+  `adapter_cls()` construction (`base.py`, unchanged) still produces a fully-working
+  production instance, since the defaults fill in — no change to `run()`/`get_adapter()`
+  was needed, matching §3's "never a change to `base.py`" rule. What the invariant
+  actually protects against — a fresh instance behaving differently from a reused one —
+  still holds: the constructor argument is a fixed collaborator (an LLM client and a
+  content-hash cache), not per-call mutable state, the same distinction `enrich.
+  enricher.LLMEnricher(llm_client, cache)` already relies on one layer up. The sole
+  reason for the constructor seam is test injectability: no existing adapter has ever
+  needed to call an external LLM, so there was no precedent for how a test substitutes
+  a fixture for one — every other adapter's "no instance state" is enforced by having
+  nothing to inject in the first place. Tests construct
+  `ProgramPageAdapter(llm_client=FixtureProgramLLMClient(...), cache=...)` directly and
+  call `.extract()`, bypassing `adapters.run()`/`get_adapter()` entirely — exactly how
+  every other adapter's own unit tests already call `SomeAdapter().extract(raw, source)`
+  directly rather than through the dispatch registry.
+  **(Ticket 006 exception revision)** `ProgramPageMultiAdapter` (new, §4) takes the
+  identical `llm_client`/`cache` constructor pair for the identical reason — it is not a
+  new deviation, just this one's third instance.
 - **Deliberate non-goal — no normalization, dedup, or taxonomy work here.** Adapters
   emit raw canonical `Event`s. Collapsing recurrences, cross-source merging, and
   controlled-vocabulary tagging belong to `normalize/`; doing any of it here would apply
@@ -203,6 +298,131 @@
 LLM enrichment and both normalize stages). Graduate/PhD-level postings are rejected
 here; the project's audience is K-12.
 
+**(Sprint 027) Why the new family lives inside `adapters/`, not a new top-level
+subsystem.** `adapters/`'s own one-sentence purpose — "translate one registered source
+into canonical `Event` records" — describes `program_page`/`program_listing` exactly;
+only the *means* of extraction differs (an LLM call instead of a JSON parse or the HTML
+ladder), which the `Adapter` Protocol (`discover → fetch → extract`) never constrained
+in the first place. `teams/` was the precedent considered and rejected: it is a
+*second, independent pipeline* precisely because a `Team` never becomes an `Opportunity`
+(`partner_scrape/DESIGN.md`'s Sprint 011 note). A program page's `Event` *does* flow
+through the normal `normalize.run()` → `export.writer` path (it only skips two of
+`normalize/`'s internal stages — see `normalize/DESIGN.md`), so it belongs where every
+other `Opportunity`-bound source's adapter lives.
+
+**New modules, one new capability.** `adapters/program_page.py` defines
+`ProgramPageAdapter` (`discover()` returns the one configured URL as a single
+`EventRef`, mirroring `greenhouse.py`/`lever.py`'s "no probe-then-paginate" shape) and
+`ProgramListingAdapter` (`discover()` crawls `source.config["listing_urls"]` and
+returns one `EventRef` per matched card/detail link, reusing
+`discovery.listing.discover_via_listing` — the same mechanism `listing_html` already
+uses, since `EVENT_PATH_RE` already matches a `/program(s)?` path segment). Both share
+one `extract()` implementation: check `adapters/program_cache.py`'s
+`ProgramExtractionCache` by URL + content-hash (mirrors `enrich/cache.py`'s shape,
+minus the `Event`-identity keying — there is no `Event` yet at fetch time, only a URL
+and a page body). Unlike `enrich/cache.py`'s deliberately single-threaded writes
+(`enrich/DESIGN.md`'s Constraints), concurrent writes here are safe by construction
+without that same restriction: `pipeline.py`'s per-*source* `ThreadPoolExecutor` is the
+only concurrency in play, each source's own `adapters.run()` call processes its
+discovered refs sequentially within that one worker thread, and every cache key is a
+distinct URL+hash — two threads can only ever write two different files, never the
+same path, so no lock or single-threaded discipline is needed here. On a miss, call the
+injected `ProgramLLMClient`
+(`adapters/program_llm.py` — `enrich_program(url, body) -> ProgramExtractionResult`,
+its JSON schema generated from the dataclass exactly as `enrich/llm_client.py`'s
+`_build_enrichment_json_schema()` already does, per this sprint's own explicit
+"reusing `enrich/llm_client.py`'s structured JSON-schema pattern" framing);
+map the result onto a canonical `Event` (`kind` from the source's `program_kind`
+config; `start`/`end` as the application-window open/deadline; `eligibility` and
+`opportunity_type` set via `Event.set(...)`, so `normalize/`'s existing
+field_provenance-presence precedence picks them up with no further code change — see
+`normalize/DESIGN.md`).
+
+**Deliberately mirrors, never imports, `enrich/llm_client.py`.** Same rationale as
+`teams/sponsor_llm.py`'s sprint 013 precedent (`teams/DESIGN.md`): a second Anthropic
+client sharing the injectable-Protocol/JSON-schema-from-dataclass *shape* costs one
+more small module, versus reaching across the `adapters` → `enrich` layering this
+codebase has never needed and does not want — `enrich/`'s own constraint that it "never
+imports `normalize/taxonomy.py`" despite overlapping vocabulary is the same accepted
+duplication-over-coupling trade, applied here to a sibling module instead.
+
+**Kind, not `opportunity_type`, is this mechanism's discriminator.** A registered
+source's `program_kind` config (`"internship"` or `"program"`) sets `Event.kind`
+directly; `opportunity_type` is a separate, independent decision (forced to
+`Work-based Learning` for `kind="internship"`, exactly as today; read from the LLM
+extraction result or a fixed per-source override for `kind="program"`). This keeps the
+bypass mechanism (§3's constructor note; `enrich/DESIGN.md`, `normalize/DESIGN.md`)
+orthogonal to which `opportunity_type` a given program ultimately displays as — the
+same separation the codebase already has between `kind`-based routing (collapse/dedup
+bypass) and `opportunity_type`-based display rules (`DEADLINE_FIRST_TYPES`).
+
+**(Ticket 006 exception revision) Selector-based listing discovery, alongside
+`EVENT_PATH_RE` — never replacing it.** `discovery/listing.py` gains a sibling function,
+`discover_via_selector(source, fetcher)`, used by `ProgramListingAdapter.discover()`
+only when `source.config` sets `link_selector` (a CSS selector string); a source with no
+`link_selector` key reproduces today's `discover_via_listing`/`EVENT_PATH_RE` behavior
+exactly, so `listing_html`'s existing Fleet Science Center registration and any future
+`program_listing` source whose card links genuinely are `/program(s)?`-shaped are
+unaffected. The two functions share the same per-listing-page fetch loop (resolve each
+`config.listing_urls` entry against `config.site_url`, GET via `acquisition_kwargs`, skip
+a non-200 page with a logged warning) and differ only in how links are picked out of the
+parsed tree: `EVENT_PATH_RE.search()` against every `<a href>` for the existing function,
+`tree.cssselect(link_selector)` for the new one. Deliberately no separate
+"grade filter" or "allow-cross-domain" config key: an operator-authored CSS selector
+already expresses both "which links" and "which cards" in one string — UCSD's own
+registration uses `li[data-grade*="High School"] a.learnmore`, which is simultaneously
+the discovery pattern and the HS-eligibility filter, live-confirmed against the real
+page markup during this revision. No cross-domain restriction is introduced because none
+existed before: `EVENT_PATH_RE` already matched "any href containing the pattern,
+regardless of domain" (this doc's own pre-revision Open Question said so), so a
+selector-based match inherits the identical, already-accepted absence of a domain check.
+
+**(Ticket 006 exception revision) `program_page_multi`: one page, N inline program
+records.** `ProgramPageMultiAdapter` (`adapters/program_page.py`) shares
+`ProgramPageAdapter`'s `discover()` verbatim — a `program_page_multi` source is still one
+fixed configured URL, one `EventRef`, no probe-then-paginate step — and differs only in
+`extract()`: it calls a new `ProgramLLMClient.extract_programs(url, body) ->
+list[ProgramExtractionResult]` method (added to the Protocol alongside the existing
+singular `extract_program`, implemented on both `AnthropicProgramLLMClient` — a second
+structured-output schema wrapping the same per-record object in `{"programs": [...]}`
+— and `FixtureProgramLLMClient`) and maps each returned result onto its own `Event`, via
+the same field-mapping logic `_extract_one_program` already applies per result. All N
+Events from one page share the same `url`/`source_id`; this is safe by construction, not
+by convention, because `Event.identity_key()` never keys on `url` — it is
+`(source_id, external_id)` when set, else `(source_id, normalized_title, start_date)`
+(`model.py`) — so N records with N distinct titles already get N distinct identity keys
+with no adapter-side bookkeeping. `ProgramExtractionCache` gains a parallel
+`lookup_many`/`store_many` pair, keyed identically (URL + content hash) but storing a
+JSON list instead of one object; the cache's `_CACHE_SCHEMA_VERSION` is bumped once,
+which forces exactly one harmless re-extraction of any pre-revision cache entry (a cache
+is a pure optimization, so a version-forced miss costs one extra LLM call, never a
+correctness issue — matching this cache's own existing "missing key or stale version is
+a miss, not a deserialization error" contract).
+
+**Reuse surface for sprints 029/030.** `program_page_multi` is deliberately generic, not
+SIO-specific: any future curated page whose N records live as sections on one page —
+named explicitly in this sprint's own dispatch as issue 30's competition pages and
+issue 33's educator-program pages — registers as a `program_page_multi` source with zero
+further adapter code, the same "onboarding is a data edit" property `program_page`/
+`program_listing` already have. This is this revision's answer to the dispatch's
+explicit ask to "design that surface for reuse."
+
+**(Ticket 006 exception revision) Zero-discovered-refs is no longer silent.**
+`adapters/base.py`'s `run()` now logs a `logger.warning` immediately after
+`refs = list(adapter.discover(source, fetcher))`, naming `source_id`, `adapter_type`,
+and the zero count, whenever an enabled source's (pre-truncation) discovery yields no
+refs at all — generic across all fourteen adapter types, not only the two program
+families, alongside the existing max_urls-truncation warning in the same function. This
+resolves this doc's own pre-revision Open Question ("a future `program_listing` source
+whose card links don't contain any matched path segment... would discover zero
+`EventRef`s silently") directly at its cause. It is a complement to, not a duplicate of,
+`observability/yield_report.py`'s existing per-run zero-yield alert (which already flags
+a source whose final Event count is zero): the yield report cannot distinguish "discover()
+itself found nothing" from "discover() found candidates but every one failed fetch or
+extraction" — this warning fires at the earlier, more specific point, giving an operator
+looking at logs (not only a periodic yield report) the finer-grained signal for exactly
+the failure mode ticket 006 hit.
+
 **Why a Protocol rather than an ABC.** Structural typing keeps concrete adapters from
 needing to inherit anything, and keeps test doubles trivial — a plain object with the
 three methods is a valid `Adapter`.
@@ -216,7 +436,9 @@
   type is unregistered; per-record failures inside `extract()` are swallowed by the
   adapter itself, so this returns a possibly-short list rather than raising. A
   fetch-level failure surfaces as a `RawResponse` with a non-2xx or sentinel status,
-  which `extract()` is responsible for handling.
+  which `extract()` is responsible for handling. **(Ticket 006 exception revision)** also
+  logs a warning (never raises) when `discover()` returns zero refs for an enabled
+  source, for every adapter type — see §4.
 - **`Adapter` Protocol, `EventRef`, `RawResponse`** — the contract a new adapter type
   implements.
 - **`ADAPTERS: dict[str, type[Adapter]]`** — the dispatch table. Mutated exactly once per
@@ -230,6 +452,28 @@
   read from `source.acquisition_policy`. Consumed by every `fetch()` implementation in
   this package and by `discovery/sitemap.py`/`discovery/listing.py`, which import it
   from here the same way they already import `EventRef` — see §2.
+- **`ProgramPageAdapter(llm_client=None, cache=None)`, `ProgramListingAdapter(llm_client=
+  None, cache=None)`** (sprint 027) — the two original adapter types; see §3's
+  constructor-injection note and §4's Design. **`ProgramPageMultiAdapter(llm_client=None,
+  cache=None)`** (ticket 006 exception revision) — the third, "one page, N inline
+  records" type; identical constructor shape, see §4.
+- **`ProgramLLMClient` Protocol, `ProgramExtractionResult`, `AnthropicProgramLLMClient`,
+  `FixtureProgramLLMClient`** (sprint 027, `adapters/program_llm.py`) — the injectable
+  LLM-extraction seam and its production/test implementations, structurally parallel to
+  `enrich/llm_client.py`'s `LLMClient`/`EnrichmentResult`/`AnthropicLLMClient`/
+  `FixtureLLMClient` but never importing them (see §4). **(Ticket 006 exception
+  revision)** `ProgramLLMClient` gains a second method, `extract_programs(url, body) ->
+  list[ProgramExtractionResult]`, for `program_page_multi`'s one-page/N-record shape;
+  both real and fixture implementations now support both methods.
+- **`ProgramExtractionCache(cache_dir=None)`** (sprint 027, `adapters/program_cache.py`)
+  — one JSON file per URL+content-hash under `{SCRAPE_CACHE_DIR}/
+  program_extraction_cache/`, avoiding a repeat `ProgramLLMClient` call for an unchanged
+  page across pipeline runs. Mirrors `enrich/cache.py`'s shape; a separate cache
+  directory and class, not a reuse of `EnrichmentCache`, because the cache key differs
+  (URL, not `Event.identity_key()` — no `Event` exists yet at fetch time). **(Ticket 006
+  exception revision)** gains `lookup_many`/`store_many`, the list-valued counterpart to
+  `lookup`/`store`, for `program_page_multi`; `_CACHE_SCHEMA_VERSION` is bumped once for
+  the new entry shape (see §4).
 
 ### Consumes
 - **`Fetcher` (from `fetch/`)** — every remote read. Injected per call; see `fetch/DESIGN.md`.
@@ -238,7 +482,9 @@
 - **`Event`, `Provenance` (from `model.py`)** — the output record. See the root
   `partner_scrape/DESIGN.md`.
 - **`discover_changed_urls` / `discover_via_listing` (from `discovery/`)** — URL
-  resolution for the two HTML adapters. See `discovery/DESIGN.md`.
+  resolution for the two HTML adapters. See `discovery/DESIGN.md`. **(Ticket 006
+  exception revision)** `discover_via_selector`, the new sibling function, is consumed by
+  `ProgramListingAdapter.discover()` the same way, when `config.link_selector` is set.
 - **`extract_fields` (from `extract/`)** — per-field values and confidences for the two
   HTML adapters. See `extract/DESIGN.md`.
 - **`config.get_leaguesync_api_key` / `get_leaguesync_url` (from `config.py`)** — the
@@ -247,6 +493,14 @@
 - **`config.get_robotevents_api_key` / `get_robotevents_url` (from `config.py`)**
   — **(Sprint 016 ticket 004)** the `robotevents` adapter's credentials, same
   `os.environ`-isolation convention as `leaguesync`'s pair above.
+- **The `anthropic` SDK** (sprint 027, `program_llm.py`'s `AnthropicProgramLLMClient`
+  only) — reads `ANTHROPIC_API_KEY` itself, not routed through `config.py`, matching
+  `enrich/llm_client.py`'s identical credential convention. This is a new external
+  dependency for `adapters/` specifically (the package as a whole already depended on
+  `anthropic` transitively via `enrich/`, but no adapter had ever called it directly).
+- **`config.get_scrape_cache_dir()` (from `config.py`)** (sprint 027,
+  `program_cache.py`) — the parent of `program_extraction_cache/`, matching
+  `enrich/cache.py`'s and `store/event_store.py`'s existing convention.
 
 ## 6. Open Questions / Known Limitations
 
@@ -265,3 +519,50 @@
   is deliberately permissive and relies on the downstream LLM relevance gate to catch
   what it lets through. If enrichment is disabled (`--no-enrich`), that safety net is
   absent.
+- **(Sprint 027, real risk, not yet fully resolved)** A program named in both a
+  `program_listing` source's crawl (e.g. the UCSD Summer Program Finder's own COSMOS/
+  OPTIMUS/ENLACE cards) and a separately-registered individual `program_page` source
+  for the same program would publish as two distinct `Opportunity` records — `kind in
+  PROGRAM_EXTRACTION_KINDS` records bypass cross-source dedup entirely (§4;
+  `normalize/DESIGN.md`), by design, for the correct reason (distinct internship
+  postings/programs are not recurrences of each other), but that same bypass means this
+  one accidental case is never caught automatically. Registering these two source
+  families for the same real-world program is a data-authoring error, not a code
+  defect — ticket-level work must reconcile the seed list (issue 28's own bullets name
+  COSMOS/OPTIMUS/ENLACE in both the listing description and the individual-pages list)
+  before both go live, and no code-level guard against it exists yet.
+- **(Sprint 027, RESOLVED by the ticket 006 exception revision)** ~~`discovery.listing.
+  discover_via_listing`'s `EVENT_PATH_RE` matches any href containing a `/program(s)?`
+  path segment, regardless of domain — reused as-is for `ProgramListingAdapter`... A
+  future `program_listing` source whose card links don't contain any matched path
+  segment would discover zero `EventRef`s silently.~~ This is exactly what ticket 006's
+  live verification hit for both of this sprint's actual listing sources — see this
+  doc's Revision note and §4. Resolved by the new `config.link_selector` discovery path
+  (for a shape a CSS selector can express) and the generic zero-refs warning (for
+  whatever shape still isn't covered). **Residual, not solved here:** no automatic
+  re-check that a registered `link_selector` still matches after a target site's markup
+  changes — a silent drift back to zero cards is caught by the new warning and by
+  `observability/`'s yield report, but nothing re-validates the selector itself or
+  alerts on a *partial* drift (e.g. 24 cards silently becoming 3). Not built
+  speculatively; revisit if a registered `link_selector` source is ever observed to
+  drift.
+- **(Ticket 006 exception revision)** `program_page_multi`'s per-page LLM call has no
+  guard against the model returning near-duplicate records for what is really one
+  program described twice in different words on the same page (SIO's own page has no
+  such duplication today, live-confirmed). Cross-record dedup *within* one
+  `program_page_multi` extraction is not built — `kind in PROGRAM_EXTRACTION_KINDS`'s
+  existing cross-source dedup bypass (§4, `normalize/DESIGN.md`) means nothing
+  downstream would catch it either. Not solved speculatively; revisit if a real page
+  exhibits this.
+- **(Sprint 027)** No per-run cost/latency budget exists for `ProgramLLMClient` calls
+  beyond `ProgramExtractionCache`'s cross-run reuse — a `program_listing` source's
+  `extract()` calls the LLM once per discovered card, sequentially, within that one
+  source's `adapters.run()` call (concurrency exists only *across* sources, via
+  `pipeline.py`'s existing `ThreadPoolExecutor`). At this sprint's scale (~21 UCSD cards
+  plus a handful more) this is an accepted, unmeasured cost; a future listing source
+  with materially more cards might need its own bounded concurrency, mirroring
+  `enrich/enricher.py`'s pattern — not built here. **(Ticket 006 exception revision)**
+  `program_page_multi` is one call per page regardless of how many records it returns
+  (cheaper per-record than `program_listing`'s one-call-per-card, since SIO's ~10
+  programs cost one call, not ten) — this doesn't change the calculus above, just notes
+  the new type's own cost shape for whoever revisits this.
```
