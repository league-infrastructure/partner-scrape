# Enrich

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## 1. Purpose

`enrich/` is the LLM layer: it recovers fields the deterministic extractors could not
find, assigns controlled-vocabulary classifications, and decides whether an event is
relevant to the site's audience at all. It is a subsystem because it is the one place
where a non-deterministic, paid, network-bound, failure-prone external service enters the
pipeline — and that requires its own cost-control cache, its own failure policy, and its
own injectable seam. It owns the *relevance gate*: the judgment that a scraped record is
not a STEM learning opportunity for K-12 youth and should not ship. Nothing else makes
that call.

## 2. Orientation

Three modules, layered:

- `llm_client.py` — the injectable `LLMClient` Protocol (`enrich_event(event) ->
  EnrichmentResult`), the `EnrichmentResult` dataclass, the real `AnthropicLLMClient`
  (model `claude-haiku-4-5-20251001`), and `FixtureLLMClient` for tests. The request's
  JSON output schema is *generated from `EnrichmentResult`'s own dataclass annotations*
  by `_build_enrichment_json_schema()`, so the schema and the parser cannot drift apart.
- `cache.py` — `EnrichmentCache`, keyed by `Event.identity_key()`, one JSON file per
  event under `{SCRAPE_CACHE_DIR}/enrichment_cache/`, storing
  `(schema_version, content_hash, EnrichmentResult, enriched_at)`. `schema_version`
  (sprint 009) is a small integer bumped whenever `EnrichmentResult`'s shape changes; a
  stored entry whose version doesn't match `_CACHE_SCHEMA_VERSION` is treated as a miss,
  the same as a `content_hash` mismatch — see Constraints below.
- `enricher.py` — `LLMEnricher`, which satisfies `pipeline.Enricher` structurally and
  sequences everything.

`LLMEnricher.enrich(events)` runs in four passes:

1. **Sequential** over the input in order: `kind="internship"` events bypass everything;
   the rest get a cache lookup. Hits are applied immediately (no LLM call). Misses are
   collected.
2. **Concurrent**: every miss's `llm_client.enrich_event()` is submitted to a
   `ThreadPoolExecutor(max_workers=8)`.
3. **Sequential apply**, back on the main thread, iterating misses in their *original*
   order: apply the result via `Event.set(...)` and write the cache entry.
4. **Relevance gate** over the full input list in original order: drop
   `relevant=False` events unless `event.trusted`.

`EnrichmentResult` carries both recoverable fields (`start`, `end`, `all_day`,
`location`, `cost`, `registration_url`) and classification fields (`areas_of_interest`,
`age_grade_level`, `cost_range`, `time_of_day`, and, since sprint 009,
`opportunity_type`), plus `relevant` and `relevance_reason`. `opportunity_type` is always
produced, like the other classification fields, and — unlike `cost_range`'s "" for
unknown — is never empty: the prompt instructs the model to fall back to the general
`"Out-of-school Programs"` bucket when nothing more specific applies, matching
`normalize.taxonomy.classify_opportunity_type`'s existing default and giving the site a
real value to filter on rather than a blank field.

## 3. Constraints and Invariants

- **Fail open, always.** Any exception from the LLM call — not only `LLMEnrichmentError`,
  but network errors, malformed responses, anything — is logged as a warning and falls
  back to `normalize.taxonomy`'s keyword derivation with `relevant=True`. A record must
  never be dropped because the LLM was unavailable. Failing closed would silently empty
  the site during any API outage.
- **A failed call writes no cache entry.** Caching a degraded fallback would make the
  next run reuse it instead of retrying the LLM, turning a transient outage into
  permanent data loss for those records.
- **Cache writes are strictly single-threaded.** The on-disk layout is one JSON file per
  event; concurrent writers would race on the same path. Only the LLM calls themselves
  run concurrently — pass 2 above touches no shared mutable state beyond each future's own
  return value.
- **The returned list's order and membership must be identical to what a fully sequential
  implementation would produce.** Concurrency changes only how fast the calls happen.
  `max_workers=1` must behave exactly like the original sequential code. Any change that
  makes output depend on completion order breaks reproducibility of a run.
- **`kind="internship"` events bypass this subsystem entirely** — no cache lookup, no LLM
  call, no field mutation. An internship arrives already classified and gated
  deterministically by `adapters/ats_filters.py`, and this module's prompt is written
  around a "STEM learning opportunity for K-12 youth" framing that would misjudge
  legitimate job-posting text as adult-only and silently drop it.
- **`event.trusted` overrides the relevance gate.** First-party curated sources (the
  League's own classes via `adapters/leaguesync.py`) are still enriched and classified
  normally but must never be gate-dropped. Removing this makes the site's own operator
  subject to the classifier's judgment about the operator's own programs.
- **The content hash covers only *enrichable* fields** — exactly the fields
  `_build_user_prompt` reads. Hashing the whole `Event` would make the classification
  fields this cache itself writes back, and `field_provenance` bookkeeping, force
  spurious re-enrichment on every run. That is a direct, recurring dollar cost.
- **A cache entry's `schema_version` must match `_CACHE_SCHEMA_VERSION` to count as a hit**
  (sprint 009). `content_hash` alone cannot catch an `EnrichmentResult` *output* shape
  change (adding `opportunity_type` doesn't touch any input field the hash covers), so
  without an explicit version an old entry would either silently omit the new field
  forever or fail to deserialize. A version mismatch (including a pre-sprint-009 entry
  with no `schema_version` key at all) is a miss, forcing exactly one re-enrichment per
  affected Event — real, one-time Anthropic spend proportional to the corpus, not a bug.
  See `sprint.md`'s Migration Concerns.
- **`llm_client.py` deliberately does not import `normalize/taxonomy.py`,** even though
  their controlled vocabularies overlap. Duplication is the accepted cost of keeping this
  module's only outward dependency the Anthropic API itself.
- **Every consumer depends on `LLMClient`, never on the `anthropic` SDK directly.**
- **One event's failure or gating never affects another in the same batch.** Each is
  handled independently, matching `pipeline.py`'s per-source isolation convention.

## 4. Design

**Why a new cache instead of reusing `fetch/`'s.** The fetch cache answers "what did this
URL return?"; this cache answers "have we already enriched this content?". Different key
(an `Event` identity, not a URL), different invalidation signal (content hash of
enrichable fields, not HTTP validators), different lifetime. It shards keys into
filesystem-safe filenames the same way `fetch/cache.py` does, because
`identity_key()` is a tuple whose `external_id` variant can contain characters unsafe in
a path.

**Why the schema is generated from the dataclass.** `_field_json_schema` walks
`EnrichmentResult`'s annotations to build the JSON schema sent to the API. The alternative
— a hand-maintained schema literal — drifts the moment a field is added, and the failure
mode is a silently unparsed response rather than an error. This is exactly why adding
`opportunity_type` (sprint 009) required no separate schema edit: it is picked up by
`_build_enrichment_json_schema()` automatically, the same way every prior classification
field was.

**Why a schema version, not just a bigger content hash.** The content hash's whole point
(the bullet above) is to answer "did the *input* change," so the cache can skip an
unnecessary LLM call. It deliberately does not — and must not — depend on
`EnrichmentResult`'s own shape, or every classification field this cache round-trips would
make the hash a moving target. A schema version is a separate, orthogonal signal: "is the
*stored value's shape* still what this code expects." Conflating the two (e.g. by hashing
the dataclass's field names into the content hash) would tie an unrelated concern
(input-change detection) to schema evolution, and would still need special-casing for the
very first version bump (nothing to compare against). An explicit integer, defaulting
absent-means-`0` treated as always-stale-for-current, is simpler and says exactly what it
means.

**Provenance stamping.** Applied results are written through `Event.set(field, value,
source, confidence)` with `source="llm_enrichment"`, `confidence=0.7`; the taxonomy
fallback uses `source="taxonomy_fallback"`, `confidence=0.3`. Both sit below the
structured-API adapters' 1.0 and the JSON-LD ladder rung's 1.0, so an LLM guess never
beats a publisher-authored value in `normalize/`'s merge selection. Only fields the
extractors left empty are recovered.

**Why concurrency was added, and only there.** A full corpus refresh was roughly 100
minutes of pure sequential LLM latency. The calls are independent and I/O-bound —
the textbook case for a bounded thread pool. Everything else (cache reads, cache writes,
result application, gating) stayed on the main thread, which is what preserves both the
ordering invariant and the single-writer cache guarantee.

**Enrichment defaults to on.** `cli.py` constructs
`LLMEnricher(AnthropicLLMClient(), EnrichmentCache())` unless `--no-enrich` is passed.
The flag is the escape hatch for local and dry-run work that must not incur API cost or
require a key.

**Credentials.** `AnthropicLLMClient` constructs `anthropic.Anthropic()` with no explicit
`api_key`; the SDK resolves `ANTHROPIC_API_KEY` itself. This is deliberately not routed
through `config.py` — the SDK, not this package, is reading the environment.

## 5. Interfaces

### Exposes
- **`LLMEnricher(llm_client, cache, max_workers=8)`** with **`.enrich(events) ->
  list[Event]`** — satisfies `pipeline.Enricher` structurally. Mutates the input `Event`
  objects in place via `Event.set(...)` and returns the gated subset in original order.
  Never raises for an LLM failure.
- **`LLMClient` Protocol** — `enrich_event(event) -> EnrichmentResult`. The injectable
  seam.
- **`EnrichmentResult`** — recoverable fields, classification fields, `relevant`,
  `relevance_reason`.
- **`AnthropicLLMClient`** (production) and **`FixtureLLMClient`** (tests, canned
  responses keyed by a caller-supplied function, records `.calls`).
- **`EnrichmentCache(cache_dir=None, clock=...)`** with `.lookup(event)` / `.store(event,
  result)`.
- **`content_hash(event) -> str`** — the enrichable-fields hash, also reused verbatim by
  `store/event_store.py` so the two caches' notion of "content changed" cannot drift.
- **`ENRICHMENT_JSON_SCHEMA`, `MODEL_ID`, `LLM_SOURCE`, `LLM_CONFIDENCE`,
  `FALLBACK_SOURCE`, `FALLBACK_CONFIDENCE`, `LLMEnrichmentError`.**
- **`_CACHE_SCHEMA_VERSION`** (sprint 009, `cache.py`) — the current stored-entry schema
  version; bumped whenever `EnrichmentResult`'s shape changes.

### Consumes
- **`Event`, `Event.set`, `Event.identity_key` (from `model.py`)** — the record being
  enriched and the provenance mechanism. See the root `partner_scrape/DESIGN.md`.
- **`normalize.taxonomy` (from `normalize/`)** — keyword-rule derivation, used *only* as
  the fail-open fallback. See `normalize/DESIGN.md`.
- **`config.get_scrape_cache_dir()` (from `config.py`)** — cache location.
- **The `anthropic` SDK** — external, reached only from `AnthropicLLMClient`.

## 6. Open Questions / Known Limitations

- The fail-open policy means an API outage produces a full run of `taxonomy_fallback`
  classifications at confidence 0.3, exported with no visible marker on the site. The
  yield report shows counts, not classification quality.
- There is no cost accounting or per-run call budget. A registry growth spurt or a cache
  wipe means a proportionally larger bill with no guard rail.
- The enrichment cache has no eviction; entries for events that no longer exist persist
  indefinitely.
- `relevance_reason` is captured on the `Event` but is not exported anywhere and not
  surfaced in the yield report, so gate decisions are only reviewable by re-reading cache
  files.
- The model ID is a hard-coded constant. Model migration is a code change, not
  configuration.
- `_recoverable_fields` and the classification vocabularies are duplicated between this
  package and `normalize/taxonomy.py` by deliberate choice; if they drift, nothing
  detects it. Sprint 009 adds `opportunity_type` to this duplication (the LLM's controlled
  vocabulary in `llm_client.py` and `normalize.taxonomy.OPPORTUNITY_TYPE_KEYWORDS` must be
  read together to see the whole picture) — deliberately not unified, same rationale as
  every other duplicated vocabulary here, and deliberately *not* symmetric: the LLM's
  vocabulary includes `"Funding Opportunities"`, which the keyword fallback still does not
  produce (see `normalize/DESIGN.md`) because a keyword rule for it was already shown to
  false-positive on unrelated text.
