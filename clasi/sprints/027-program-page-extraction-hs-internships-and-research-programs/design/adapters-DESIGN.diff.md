---
source_file: adapters-DESIGN.md
source_hash: 15cedf69f46d49ea3917049c8343c8e44751dd42c1ee6477dad7dd4dca61cb33
---
# Diff: adapters-DESIGN.md

Comparison of the sprint overlay copy of `adapters-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- adapters-DESIGN.md (pristine)
+++ adapters-DESIGN.md (current)
@@ -34,6 +34,19 @@
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
@@ -68,12 +81,13 @@
 `ADAPTERS` dispatch dict, instantiates it, materializes `discover()`'s output, truncates
 it to the source's `max_urls` cap, then loops fetch→extract accumulating events.
 
-Eleven adapter types are registered today, in two families:
+Thirteen adapter types are registered today, in three families:
 
 | Family | Types | Shape |
 |---|---|---|
 | Structured API | `tec_rest`, `wp_rest`, `ical`, `localist`, `bibliocommons`, `greenhouse`, `lever`, `leaguesync`, `robotevents` | Known endpoint, JSON/iCal parsing, `CONFIDENCE = 1.0` |
 | HTML | `generic_html`, `listing_html` | URL discovery via `discovery/`, field recovery via `extract/`'s ladder |
+| **LLM extraction (sprint 027)** | `program_page`, `program_listing` | One registered page (or one crawled listing's cards), field recovery via a bespoke `ProgramLLMClient` call, never `extract/`'s ladder |
 
 `ats_filters.py` is a shared helper, not an adapter: the deterministic
 internship / STEM / San-Diego-local classifier the two applicant-tracking-system adapters
@@ -106,6 +120,25 @@
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
 - **Deliberate non-goal — no normalization, dedup, or taxonomy work here.** Adapters
   emit raw canonical `Event`s. Collapsing recurrences, cross-source merging, and
   controlled-vocabulary tagging belong to `normalize/`; doing any of it here would apply
@@ -203,6 +236,64 @@
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
 **Why a Protocol rather than an ABC.** Structural typing keeps concrete adapters from
 needing to inherit anything, and keeps test doubles trivial — a plain object with the
 three methods is a valid `Adapter`.
@@ -230,6 +321,20 @@
   read from `source.acquisition_policy`. Consumed by every `fetch()` implementation in
   this package and by `discovery/sitemap.py`/`discovery/listing.py`, which import it
   from here the same way they already import `EventRef` — see §2.
+- **`ProgramPageAdapter(llm_client=None, cache=None)`, `ProgramListingAdapter(llm_client=
+  None, cache=None)`** (sprint 027) — the two new adapter types; see §3's constructor-
+  injection note and §4's Design.
+- **`ProgramLLMClient` Protocol, `ProgramExtractionResult`, `AnthropicProgramLLMClient`,
+  `FixtureProgramLLMClient`** (sprint 027, `adapters/program_llm.py`) — the injectable
+  LLM-extraction seam and its production/test implementations, structurally parallel to
+  `enrich/llm_client.py`'s `LLMClient`/`EnrichmentResult`/`AnthropicLLMClient`/
+  `FixtureLLMClient` but never importing them (see §4).
+- **`ProgramExtractionCache(cache_dir=None)`** (sprint 027, `adapters/program_cache.py`)
+  — one JSON file per URL+content-hash under `{SCRAPE_CACHE_DIR}/
+  program_extraction_cache/`, avoiding a repeat `ProgramLLMClient` call for an unchanged
+  page across pipeline runs. Mirrors `enrich/cache.py`'s shape; a separate cache
+  directory and class, not a reuse of `EnrichmentCache`, because the cache key differs
+  (URL, not `Event.identity_key()` — no `Event` exists yet at fetch time).
 
 ### Consumes
 - **`Fetcher` (from `fetch/`)** — every remote read. Injected per call; see `fetch/DESIGN.md`.
@@ -247,6 +352,14 @@
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
 
@@ -265,3 +378,31 @@
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
+- **(Sprint 027)** `discovery.listing.discover_via_listing`'s `EVENT_PATH_RE` matches
+  any href containing a `/program(s)?` (or `/course`, `/camp`, etc.) path segment,
+  regardless of domain — reused as-is for `ProgramListingAdapter` rather than
+  extended, since the UCSD Summer Program Finder's own card links already fit this
+  shape. A future `program_listing` source whose card links don't contain any matched
+  path segment (e.g. a listing that links out to bare organization homepages) would
+  discover zero `EventRef`s silently; not encountered in this sprint's two registered
+  listing sources, so not solved speculatively here.
+- **(Sprint 027)** No per-run cost/latency budget exists for `ProgramLLMClient` calls
+  beyond `ProgramExtractionCache`'s cross-run reuse — a `program_listing` source's
+  `extract()` calls the LLM once per discovered card, sequentially, within that one
+  source's `adapters.run()` call (concurrency exists only *across* sources, via
+  `pipeline.py`'s existing `ThreadPoolExecutor`). At this sprint's scale (~21 UCSD cards
+  plus a handful more) this is an accepted, unmeasured cost; a future listing source
+  with materially more cards might need its own bounded concurrency, mirroring
+  `enrich/enricher.py`'s pattern — not built here.
```
