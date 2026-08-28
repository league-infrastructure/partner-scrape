---
source_file: enrich-DESIGN.md
source_hash: c8ad638f222c88511fd7a8d3ff5c945331287e536a77d86e594fd95025dd8aec
---
# Diff: enrich-DESIGN.md

Comparison of the sprint overlay copy of `enrich-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- enrich-DESIGN.md (pristine)
+++ enrich-DESIGN.md (current)
@@ -26,7 +26,10 @@
   by `_build_enrichment_json_schema()`, so the schema and the parser cannot drift apart.
 - `cache.py` — `EnrichmentCache`, keyed by `Event.identity_key()`, one JSON file per
   event under `{SCRAPE_CACHE_DIR}/enrichment_cache/`, storing
-  `(content_hash, EnrichmentResult, enriched_at)`.
+  `(schema_version, content_hash, EnrichmentResult, enriched_at)`. `schema_version`
+  (sprint 009) is a small integer bumped whenever `EnrichmentResult`'s shape changes; a
+  stored entry whose version doesn't match `_CACHE_SCHEMA_VERSION` is treated as a miss,
+  the same as a `content_hash` mismatch — see Constraints below.
 - `enricher.py` — `LLMEnricher`, which satisfies `pipeline.Enricher` structurally and
   sequences everything.
 
@@ -44,7 +47,13 @@
 
 `EnrichmentResult` carries both recoverable fields (`start`, `end`, `all_day`,
 `location`, `cost`, `registration_url`) and classification fields (`areas_of_interest`,
-`age_grade_level`, `cost_range`, `time_of_day`), plus `relevant` and `relevance_reason`.
+`age_grade_level`, `cost_range`, `time_of_day`, and, since sprint 009,
+`opportunity_type`), plus `relevant` and `relevance_reason`. `opportunity_type` is always
+produced, like the other classification fields, and — unlike `cost_range`'s "" for
+unknown — is never empty: the prompt instructs the model to fall back to the general
+`"Out-of-school Programs"` bucket when nothing more specific applies, matching
+`normalize.taxonomy.classify_opportunity_type`'s existing default and giving the site a
+real value to filter on rather than a blank field.
 
 ## 3. Constraints and Invariants
 
@@ -77,6 +86,14 @@
   `_build_user_prompt` reads. Hashing the whole `Event` would make the classification
   fields this cache itself writes back, and `field_provenance` bookkeeping, force
   spurious re-enrichment on every run. That is a direct, recurring dollar cost.
+- **A cache entry's `schema_version` must match `_CACHE_SCHEMA_VERSION` to count as a hit**
+  (sprint 009). `content_hash` alone cannot catch an `EnrichmentResult` *output* shape
+  change (adding `opportunity_type` doesn't touch any input field the hash covers), so
+  without an explicit version an old entry would either silently omit the new field
+  forever or fail to deserialize. A version mismatch (including a pre-sprint-009 entry
+  with no `schema_version` key at all) is a miss, forcing exactly one re-enrichment per
+  affected Event — real, one-time Anthropic spend proportional to the corpus, not a bug.
+  See `sprint.md`'s Migration Concerns.
 - **`llm_client.py` deliberately does not import `normalize/taxonomy.py`,** even though
   their controlled vocabularies overlap. Duplication is the accepted cost of keeping this
   module's only outward dependency the Anthropic API itself.
@@ -97,7 +114,22 @@
 **Why the schema is generated from the dataclass.** `_field_json_schema` walks
 `EnrichmentResult`'s annotations to build the JSON schema sent to the API. The alternative
 — a hand-maintained schema literal — drifts the moment a field is added, and the failure
-mode is a silently unparsed response rather than an error.
+mode is a silently unparsed response rather than an error. This is exactly why adding
+`opportunity_type` (sprint 009) required no separate schema edit: it is picked up by
+`_build_enrichment_json_schema()` automatically, the same way every prior classification
+field was.
+
+**Why a schema version, not just a bigger content hash.** The content hash's whole point
+(the bullet above) is to answer "did the *input* change," so the cache can skip an
+unnecessary LLM call. It deliberately does not — and must not — depend on
+`EnrichmentResult`'s own shape, or every classification field this cache round-trips would
+make the hash a moving target. A schema version is a separate, orthogonal signal: "is the
+*stored value's shape* still what this code expects." Conflating the two (e.g. by hashing
+the dataclass's field names into the content hash) would tie an unrelated concern
+(input-change detection) to schema evolution, and would still need special-casing for the
+very first version bump (nothing to compare against). An explicit integer, defaulting
+absent-means-`0` treated as always-stale-for-current, is simpler and says exactly what it
+means.
 
 **Provenance stamping.** Applied results are written through `Event.set(field, value,
 source, confidence)` with `source="llm_enrichment"`, `confidence=0.7`; the taxonomy
@@ -140,6 +172,8 @@
   `store/event_store.py` so the two caches' notion of "content changed" cannot drift.
 - **`ENRICHMENT_JSON_SCHEMA`, `MODEL_ID`, `LLM_SOURCE`, `LLM_CONFIDENCE`,
   `FALLBACK_SOURCE`, `FALLBACK_CONFIDENCE`, `LLMEnrichmentError`.**
+- **`_CACHE_SCHEMA_VERSION`** (sprint 009, `cache.py`) — the current stored-entry schema
+  version; bumped whenever `EnrichmentResult`'s shape changes.
 
 ### Consumes
 - **`Event`, `Event.set`, `Event.identity_key` (from `model.py`)** — the record being
@@ -165,4 +199,10 @@
   configuration.
 - `_recoverable_fields` and the classification vocabularies are duplicated between this
   package and `normalize/taxonomy.py` by deliberate choice; if they drift, nothing
-  detects it.
+  detects it. Sprint 009 adds `opportunity_type` to this duplication (the LLM's controlled
+  vocabulary in `llm_client.py` and `normalize.taxonomy.OPPORTUNITY_TYPE_KEYWORDS` must be
+  read together to see the whole picture) — deliberately not unified, same rationale as
+  every other duplicated vocabulary here, and deliberately *not* symmetric: the LLM's
+  vocabulary includes `"Funding Opportunities"`, which the keyword fallback still does not
+  produce (see `normalize/DESIGN.md`) because a keyword rule for it was already shown to
+  false-positive on unrelated text.
```
