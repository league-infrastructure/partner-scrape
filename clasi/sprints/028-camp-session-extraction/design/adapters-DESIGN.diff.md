---
source_file: adapters-DESIGN.md
source_hash: f27f32399030f6c72754b733975a12a48702c2cda476628c69726b1976a076e8
---
# Diff: adapters-DESIGN.md

Comparison of the sprint overlay copy of `adapters-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- adapters-DESIGN.md (pristine)
+++ adapters-DESIGN.md (current)
@@ -57,6 +57,36 @@
 Open Question generically, for every adapter type, not only the two
 program families.
 
+## Revision (2026-09-01 — sprint 028)
+
+Issue 36 (found during sprint 027's own live verification, recorded in the previous
+Revision note's neighbor, `sd-foundation-community-scholarship.toml`'s `enabled = false`
+disable reason) and issue 29 (camp session extraction) both land in this sprint. Four
+changes to this family, all additive:
+
+1. **HTML-to-text reduction, closing issue 36.** `_extract_one_program`/
+   `_extract_many_programs` now call the new `extract.reduce_html_to_text()`
+   (`extract/DESIGN.md`'s sprint 028 section) on `raw.body` before every cache lookup and
+   LLM call, instead of passing the raw fetched body straight through. This directly
+   re-enables `sd-foundation-community-scholarship.toml` (`enabled = true` again this
+   sprint) and the UCSD Summer Program Finder cards that previously failed the same way.
+2. **`is_open`'s prompt-level definition generalizes** from "applications are open" to
+   "open for enrollment/application; false if closed, full, or sold out" — see §4's
+   Design Rationale below for why this is the right way to serve camp sessions' sold-out
+   flags without a schema change.
+3. **Two new adapter types, `activenet_camps` and `campbrain`** (a fifteenth and
+   sixteenth adapter type; `docs/design/design.md`'s subsystem-map count moves fourteen
+   → sixteen) — structured platform adapters for `campscui.active.com` (ActiveNet) and
+   CampBrain, the two highest-priority items in issue 29's platform-adapter list. See
+   §4's Design section.
+4. **Pike13 (issue 29's third-priority platform) is explicitly deferred**, not designed
+   here — see §4's Design Rationale and `sprint.md`'s "Deferred to a follow-up issue".
+
+No `Opportunity`/`Event` schema change. No change to `enrich/` or `normalize/` — the
+`kind in PROGRAM_EXTRACTION_KINDS` bypass sprint 027 already generalized covers every
+record this sprint's adapters emit unchanged, since all of them still set
+`kind="program"`.
+
 ## 1. Purpose
 
 `adapters/` owns the translation from *one registered source* into *canonical `Event`
@@ -100,6 +130,14 @@
 documented deviation from §3's "adapters hold no instance state" invariant this family
 needs for test injectability.
 
+**(Sprint 028)** Two more adapter types, `activenet_camps` and `campbrain`, extend the
+LLM-extraction family's own extension pattern one step further: where `program_page`/
+`program_listing`/`program_page_multi` map an arbitrary *prose* page onto `Event`s via an
+LLM call, these two map a **known camp-registration platform's** session listing — a
+JSON API when the vendor exposes one cleanly, an LLM-extracted page otherwise — onto the
+exact same intermediate shape (`ProgramExtractionResult`), so the existing
+`_map_result_to_event` mapping serves them with zero new mapping code. See §4.
+
 ## 2. Orientation
 
 The public contract is `base.py`'s `Adapter` Protocol: three methods, `discover` →
@@ -134,13 +172,14 @@
 `ADAPTERS` dispatch dict, instantiates it, materializes `discover()`'s output, truncates
 it to the source's `max_urls` cap, then loops fetch→extract accumulating events.
 
-Fourteen adapter types are registered today, in three families:
+Sixteen adapter types are registered today, in four families:
 
 | Family | Types | Shape |
 |---|---|---|
 | Structured API | `tec_rest`, `wp_rest`, `ical`, `localist`, `bibliocommons`, `greenhouse`, `lever`, `leaguesync`, `robotevents` | Known endpoint, JSON/iCal parsing, `CONFIDENCE = 1.0` |
 | HTML | `generic_html`, `listing_html` | URL discovery via `discovery/`, field recovery via `extract/`'s ladder |
-| **LLM extraction (sprint 027)** | `program_page`, `program_listing`, `program_page_multi` | One registered page (or one crawled listing's cards, or one page read as N inline records), field recovery via a bespoke `ProgramLLMClient` call, never `extract/`'s ladder |
+| LLM extraction (sprint 027) | `program_page`, `program_listing`, `program_page_multi` | One registered page (or one crawled listing's cards, or one page read as N inline records), field recovery via a bespoke `ProgramLLMClient` call, never `extract/`'s ladder |
+| **Camp platform (sprint 028)** | `activenet_camps`, `campbrain` | One registered per-organization camp-listing endpoint on a known registration platform; session records recovered deterministically when the platform exposes a parseable JSON response, else via the same `ProgramLLMClient.extract_programs()` call `program_page_multi` uses — either way, normalized into `ProgramExtractionResult` before mapping |
 
 **(Ticket 006 exception revision) `program_page_multi`.** A third LLM-extraction type,
 alongside `program_page`/`program_listing`: one registered page whose body contains N
@@ -201,6 +240,11 @@
   **(Ticket 006 exception revision)** `ProgramPageMultiAdapter` (new, §4) takes the
   identical `llm_client`/`cache` constructor pair for the identical reason — it is not a
   new deviation, just this one's third instance.
+  **(Sprint 028)** `ActiveNetCampsAdapter`/`CampBrainAdapter` (new, §4) take the same
+  `llm_client`/`cache` constructor pair — their fourth and fifth instance — for their
+  LLM-extraction fallback path (their deterministic-JSON path needs no LLM client at all,
+  but the constructor shape stays uniform across the whole family so a source can be
+  registered either way with no adapter-selection logic anywhere else).
 - **Deliberate non-goal — no normalization, dedup, or taxonomy work here.** Adapters
   emit raw canonical `Event`s. Collapsing recurrences, cross-source merging, and
   controlled-vocabulary tagging belong to `normalize/`; doing any of it here would apply
@@ -426,6 +470,175 @@
 **Why a Protocol rather than an ABC.** Structural typing keeps concrete adapters from
 needing to inherit anything, and keeps test doubles trivial — a plain object with the
 three methods is a valid `Adapter`.
+
+**(Sprint 028) HTML-to-text reduction, closing issue 36.** `_extract_one_program`/
+`_extract_many_programs` (`program_page.py`) now call
+`extract.reduce_html_to_text(raw.body)` immediately after the non-200 status check, and
+use the *reduced* text for everything downstream: `cache.lookup`/`cache.lookup_many`,
+`llm_client.extract_program`/`extract_programs`, and `cache.store`/`store_many`. This
+means the extraction cache's key (`content_hash`, `adapters/DESIGN.md`'s own §5 entry for
+`ProgramExtractionCache`) is now a hash of the reduced text, not the raw fetched body —
+see the Design Rationale below for why this is a deliberate improvement, not an
+incidental side effect. `_CACHE_SCHEMA_VERSION` is **not** bumped: the entry's on-disk
+*shape* (`schema_version`/`content_hash`/`result`|`results`) is unchanged, only what gets
+hashed — an old entry's stored hash simply won't match the new hash on the next run,
+which the cache's existing "stale content hash is a miss, not an error" contract already
+handles as a normal, harmless one-time re-extraction per already-cached page (same
+"pure optimization" reasoning `_CACHE_SCHEMA_VERSION`'s own docstring already relies on).
+
+**Design Rationale: hash the reduced text, not the raw HTML.**
+- *Decision*: `content_hash()` is computed over `reduce_html_to_text()`'s output, called
+  once per fetch, with the same value reused for the cache key and the LLM call.
+- *Context*: `ProgramExtractionCache` already existed keyed on `content_hash(raw body)`;
+  adding a reduction step needed a decision about which text to hash.
+- *Alternatives considered*: keep hashing `raw.body` (the fetched HTML) and only pass the
+  reduced text to the LLM call.
+- *Why this choice*: a page's raw HTML changes on every visit to a boilerplate element
+  that `reduce_html_to_text()` already discards (a nav-menu link, an inline script's
+  cache-busting query string, an ad-tag version bump) — hashing the raw body would
+  invalidate the cache on changes that can never affect the extracted fields, since the
+  LLM never sees them. Hashing the reduced text instead means the cache only misses when
+  content the LLM actually reads has changed — a strictly better hit rate with no
+  correctness cost.
+- *Consequences*: every previously-cached `program_page`/`program_listing`/
+  `program_page_multi` entry misses exactly once on this sprint's first post-deploy run
+  (its stored hash was computed over raw HTML, the new code hashes reduced text) and is
+  then cached under the new key going forward — a one-time, bounded-cost, already-
+  contracted-for cache miss, not a bug.
+
+**(Sprint 028) `is_open`'s prompt-level definition generalizes, and camp sessions surface
+sold-out status via `Event.description`.** `program_llm.py`'s `_FIELD_EXTRACTION_RULES`
+(shared verbatim between the single- and multi-record system prompts) rewords `is_open`'s
+guidance from "true if the page indicates applications are currently open... false if...
+closed for the current cycle" to "true if open for enrollment/application; false if
+closed, full, or sold out" — a backward-compatible broadening, not a new field: an
+internship/program page's own truth value is unaffected (a closed application window was
+already "not open"; a sold-out camp session is now also "not open," a case that simply
+never arose for the pre-028 program_kind population). `_map_result_to_event`
+(`program_page.py`) gains one new branch: when the resolved `opportunity_type` is
+`"Camps"` and `result.is_open` is `False`, it now calls `event.set("description", "Sold
+out", source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE)` — the one field this
+mechanism has left conspicuously unset since sprint 027 (see this doc's own "No
+`description` field" note in `program_page.py`'s module docstring), now given exactly one
+use, gated narrowly enough that no other `program_kind`/`opportunity_type` combination's
+`Event.description` changes from its pre-sprint-028 unset state.
+
+**Design Rationale: reuse `ProgramExtractionResult`/`program_page_multi` unchanged for
+camp sessions, rather than a camp-specific result shape.**
+- *Decision*: A camp session (dates, price, sold-out flag) is represented as one
+  `ProgramExtractionResult`, extracted via the existing `program_page_multi` mechanism —
+  no new dataclass, no new adapter-family prompt shape.
+- *Context*: issue 29 explicitly asked whether `program_page_multi` serves camps
+  directly or needs a camp-specific shape, since sessions carry price + sold-out +
+  week-by-week dates that `ProgramExtractionResult` might not carry.
+- *Alternatives considered*: (a) a new `CampSessionExtractionResult` dataclass plus a
+  parallel prompt/schema/cache/adapter path; (b) extend `ProgramExtractionResult` with new
+  fields (e.g. `sold_out: bool`, `session_label: str`).
+- *Why this choice*: on inspection, the existing fields already have a 1:1 mapping onto a
+  camp session's real needs — `date_start`/`date_end` are the session's own week dates
+  (exactly what `program_page_multi`'s "N inline records, each independently dated"
+  design already provides), `cost` is a free-text price string (already accepts "$525/wk"
+  as readily as "Free"), and `is_open` already means "currently available" once its
+  prompt wording is read generically rather than application-window-specifically (the
+  wording change above). (a) would duplicate roughly 400 lines of schema/prompt/cache
+  machinery for a shape that turns out not to need new fields. (b) is a real schema
+  change to a dataclass three existing use cases (SUC-031 through SUC-035) already
+  depend on, for no field this sprint's actual data needs. Reusing the shape as-is, with
+  only prose-level prompt generalization and one small `_map_result_to_event` branch,
+  needed neither.
+- *Consequences*: no new LLM-extraction schema, no new cache entry shape, no
+  `_CACHE_SCHEMA_VERSION` bump for this reason. The tradeoff is that `is_open`'s field
+  name reads oddly for a camp session ("is open" meaning "not sold out") — judged an
+  acceptable naming cost against duplicating the whole mechanism, and documented here so
+  a future reader of `program_llm.py` understands why.
+
+**(Sprint 028) An in-season-only page's empty result is valid, not an error, closing the
+Fleet seasonal-recheck requirement.** `_SYSTEM_PROMPT_MULTI` gains one explicit
+instruction: "If no distinct programs are described on the page, return an empty list."
+`_extract_many_programs` already maps a zero-length `results`/`list_responses` to zero
+`Event`s with no special-casing needed — the only change is telling the model that zero
+is an acceptable, correct answer rather than something to guess around.
+
+**Design Rationale: no new seasonal-recheck subsystem.**
+- *Decision*: Fleet's marketing page (and any other in-season-only camp page) is
+  registered `enabled = true` year-round; the existing weekly scheduled run
+  (`.github/workflows/scheduled-run.yml`) is the entire "recheck" mechanism.
+- *Context*: the roadmap `sprint.md`'s Success Criteria asked for "a season-ahead view":
+  a camp whose registration opens later should be "scheduled for a seasonal re-check
+  rather than silently stale."
+- *Alternatives considered*: a per-source `next_check_date`/recheck-interval field in
+  `registry/`'s `SourceConfig`, read by `pipeline.run()` to skip a source outside its
+  window; a cron-level seasonal filter.
+- *Why this choice*: the pipeline already re-fetches every enabled source on every
+  scheduled run, unconditionally — there was never a technical gap in *re-checking*
+  Fleet's page. The actual gap was narrower and already fixed above: `extract_programs()`
+  had no explicit permission to return an empty list for a page with nothing on it yet,
+  so an off-season run risked either a hallucinated session or a parse error, not silence.
+  Building registry-level scheduling machinery for a problem that doesn't require it
+  would be exactly the "speculative generality" this codebase's own architecture-quality
+  principles warn against, and this project's own `registry/DESIGN.md` already treats
+  "no schema validation for `config`" as an accepted minimalism tradeoff of the same
+  shape.
+- *Consequences*: an off-season Fleet run legitimately yields zero `Camps` records, which
+  is indistinguishable in `observability/`'s yield report from a broken source — see §6's
+  new Open Question for this residual, accepted gap.
+
+**(Sprint 028) `activenet_camps`/`campbrain`: platform adapters sharing the LLM family's
+own intermediate shape.** `ActiveNetCampsAdapter`/`CampBrainAdapter` share
+`ProgramPageAdapter`'s exact `discover()`/`fetch()` shape — one registered
+`config.url` per organization (the platform's per-org camp-listing endpoint), one
+`EventRef`, no probe-then-paginate step, matching the "onboarding is a data edit"
+convention every other adapter type already follows (`registry/DESIGN.md`'s own §1). They
+differ only in `extract()`: each vendor's response is first attempted as a deterministic
+parse (a known JSON shape, `CONFIDENCE_STRUCTURED_PLATFORM = 1.0`, mirroring the
+Structured API family's own confidence convention) into one `ProgramExtractionResult` per
+session found; if the platform's actual response turns out not to be cleanly structured
+(confirmed at ticket time via live verification — issue 29 calls ActiveNet "HTML-ish", not
+confirmed JSON), `extract()` falls back to `extract.reduce_html_to_text()` plus
+`ProgramLLMClient.extract_programs()` — the exact same call `program_page_multi` already
+makes, with the exact same `_SYSTEM_PROMPT_MULTI`. Either path produces a
+`list[ProgramExtractionResult]`, mapped onto `Event`s via the existing
+`_map_result_to_event` with zero new mapping code — see this section's earlier Design
+Rationale for why `ProgramExtractionResult` was kept as the one shared intermediate shape.
+`config.opportunity_type = "Camps"` is set on every registered `activenet_camps`/
+`campbrain` source, the same operator-curated override convention
+`sd-foundation-community-scholarship.toml` already established for `"Funding
+Opportunities"`.
+
+**Design Rationale: defer Pike13; exclude Camp Galileo SD; avoid dual-registering Air &
+Space Museum/Helen Woodward.**
+- *Decision*: this sprint designs and registers only `activenet_camps` and `campbrain`
+  (issue 29's first- and second-priority platforms). Pike13 (third priority) is deferred
+  to a follow-up issue. Camp Galileo SD is not registered by any path. Air & Space Museum
+  and Helen Woodward are registered only via `activenet_camps`, never also via a
+  marketing-page `program_page_multi` source.
+- *Context*: issue 29 lists all three platforms and names Camp Galileo SD among the
+  marketing-page targets; both Air & Space Museum and Helen Woodward appear in issue 29's
+  marketing-page list *and* its ActiveNet-coverage note.
+- *Alternatives considered*: build all three platform adapters this sprint; register
+  Camp Galileo SD pending the stakeholder's still-open commercial-chain decision;
+  register Air & Space/Helen Woodward through both paths and rely on downstream dedup.
+- *Why this choice*: Pike13 needs its own credential provisioning and has an unresolved
+  overlap question with the already-shipped `leaguesync` adapter (issue 29's own text) —
+  forcing it in risks a low-confidence adapter or a stalled ticket, so it is scoped out
+  explicitly rather than attempted and left half-verified. Camp Galileo is the studio
+  brand named in the roadmap `sprint.md`'s own commercial-chain exclusion list — the
+  scope decision already made at roadmap time applies to it regardless of which list
+  issue 29 happens to also put it on. Registering Air & Space/Helen Woodward through two
+  adapter types would repeat, for a case we can see coming, the exact dual-registration
+  risk `adapters/DESIGN.md`'s own sprint 027 Open Question documents as unresolved for
+  COSMOS/OPTIMUS/ENLACE (`kind in PROGRAM_EXTRACTION_KINDS` records bypass cross-source
+  dedup by design, so nothing downstream would catch the duplicate).
+- *Consequences*: a follow-up issue is filed at sprint close for Pike13, carrying the
+  leaguesync-overlap question forward. `registry/sources/` gets no Camp Galileo entry.
+  Air & Space Museum/Helen Woodward's marketing pages, though scrapable, are deliberately
+  never registered as `program_page_multi` sources.
+
+**Reuse surface for future platforms.** `activenet_camps`/`campbrain`'s "deterministic
+parse, LLM fallback, `ProgramExtractionResult` either way" shape is deliberately generic:
+a future camp-registration platform (or Pike13, when its follow-up issue is picked up)
+can follow the identical pattern with zero change to `program_llm.py`, `program_cache.py`,
+or `_map_result_to_event`.
 
 ## 5. Interfaces
 
@@ -465,6 +678,15 @@
   revision)** `ProgramLLMClient` gains a second method, `extract_programs(url, body) ->
   list[ProgramExtractionResult]`, for `program_page_multi`'s one-page/N-record shape;
   both real and fixture implementations now support both methods.
+- **`ActiveNetCampsAdapter(llm_client=None, cache=None)`, `CampBrainAdapter(llm_client=
+  None, cache=None)`** (sprint 028) — the two new camp-platform adapter types; see §4's
+  Design. Same constructor-injection shape as the `program_page` family, for the same
+  test-injectability reason.
+- **`CONFIDENCE_STRUCTURED_PLATFORM`** (sprint 028, `adapters/activenet_camps.py`/
+  `campbrain.py`) — the confidence stamped on a deterministically-parsed platform
+  session field, `1.0`, matching every Structured API adapter's own `CONFIDENCE = 1.0`
+  convention. Not used on the LLM-fallback path, which stamps `PROGRAM_LLM_CONFIDENCE`
+  (`0.9`) exactly as `program_page_multi` already does.
 - **`ProgramExtractionCache(cache_dir=None)`** (sprint 027, `adapters/program_cache.py`)
   — one JSON file per URL+content-hash under `{SCRAPE_CACHE_DIR}/
   program_extraction_cache/`, avoiding a repeat `ProgramLLMClient` call for an unchanged
@@ -501,6 +723,15 @@
 - **`config.get_scrape_cache_dir()` (from `config.py`)** (sprint 027,
   `program_cache.py`) — the parent of `program_extraction_cache/`, matching
   `enrich/cache.py`'s and `store/event_store.py`'s existing convention.
+- **`extract.reduce_html_to_text(html, max_chars)` (from `extract/`)** (sprint 028) — the
+  new dependency this sprint adds: `program_page.py` now imports from `extract/`, which
+  it previously never did (only `generic_html.py`/`listing_html.py` depended on `extract/`
+  before this sprint). See `extract/DESIGN.md`'s sprint 028 section. No credential or
+  API-key dependency was added for `activenet_camps`/`campbrain` this sprint — both
+  platforms' endpoints are treated as public for architecture purposes, pending each
+  registration's own live verification; if verification finds a required API key, that
+  ticket adds a `config.py` accessor pair mirroring `get_leaguesync_api_key()`/
+  `get_robotevents_api_key()`, not designed in advance of evidence requiring it.
 
 ## 6. Open Questions / Known Limitations
 
@@ -566,3 +797,25 @@
   (cheaper per-record than `program_listing`'s one-call-per-card, since SIO's ~10
   programs cost one call, not ten) — this doesn't change the calculus above, just notes
   the new type's own cost shape for whoever revisits this.
+- **(Sprint 028)** An off-season, in-season-only camp page (Fleet) legitimately yields
+  zero `Camps` records, which is indistinguishable in `observability/`'s per-run yield
+  report from a broken source. Accepted per this doc's own Design Rationale above (no
+  seasonal-recheck subsystem was built); not solved here. A future sprint could give
+  `registry/` sources an optional "expected zero-yield window" annotation if this proves
+  to generate false-positive yield alerts in practice — not built speculatively.
+- **(Sprint 028)** `activenet_camps`/`campbrain`'s exact response shape (a clean JSON API
+  vs. server-rendered HTML needing the LLM-fallback path) is unconfirmed at
+  architecture-authoring time — issue 29 calls ActiveNet "HTML-ish" without further
+  detail. Both adapters are designed to support either shape identically (see §4), but
+  which shape each vendor actually needs is a ticket-level live-verification finding,
+  not an architecture decision made here.
+- **(Sprint 028)** Whether Coastal Roots Farm's existing marketing-page table
+  (`program_page_multi`) is sufficient on its own, or whether its CampBrain-hosted
+  registration data would ever need to supersede it, is a ticket-level judgment call once
+  the `campbrain` adapter's actual per-organization coverage is confirmed live — this
+  sprint registers Coastal Roots Farm via its marketing page only (see `sprint.md`'s
+  SUC-043), not via `campbrain`, to avoid the same dual-registration risk named above for
+  Air & Space Museum/Helen Woodward.
+- **(Sprint 028)** Pike13 (issue 29's third-priority platform) is deferred, along with
+  its own open question — whether it supersedes gaps in the already-shipped `leaguesync`
+  adapter for the League's own camps — to a follow-up issue. Not designed here.
```
