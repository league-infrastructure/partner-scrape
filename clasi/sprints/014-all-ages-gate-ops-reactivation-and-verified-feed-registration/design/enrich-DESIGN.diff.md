---
source_file: enrich-DESIGN.md
source_hash: 9be21b1acd4e1695aa0ff8230c171c21c416519d1ce4857a778f8c73a80011a7
---
# Diff: enrich-DESIGN.md

Comparison of the sprint overlay copy of `enrich-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- enrich-DESIGN.md (pristine)
+++ enrich-DESIGN.md (current)
@@ -1,6 +1,6 @@
 # Enrich
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable
 
 ---
 
@@ -12,8 +12,15 @@
 where a non-deterministic, paid, network-bound, failure-prone external service enters the
 pipeline — and that requires its own cost-control cache, its own failure policy, and its
 own injectable seam. It owns the *relevance gate*: the judgment that a scraped record is
-not a STEM learning opportunity for K-12 youth and should not ship. Nothing else makes
-that call.
+not a STEM learning opportunity for *any* audience and should not ship. Nothing else
+makes that call.
+
+**(Sprint 014)** The gate's audience scope widened from K-12-only to all ages —
+matching the site's own "learners of all ages" framing and its existing `Adult`
+age-facet — while noise rejection (non-STEM recreation, galas, closure notices,
+nav pages) is unchanged. See §2's cache-versioning addition and §6's Open
+Questions for how ~9,700 pre-existing cache entries, written under the old
+K-12-only framing, get exactly one forced re-evaluation each.
 
 ## 2. Orientation
 
@@ -26,10 +33,16 @@
   by `_build_enrichment_json_schema()`, so the schema and the parser cannot drift apart.
 - `cache.py` — `EnrichmentCache`, keyed by `Event.identity_key()`, one JSON file per
   event under `{SCRAPE_CACHE_DIR}/enrichment_cache/`, storing
-  `(schema_version, content_hash, EnrichmentResult, enriched_at)`. `schema_version`
-  (sprint 009) is a small integer bumped whenever `EnrichmentResult`'s shape changes; a
-  stored entry whose version doesn't match `_CACHE_SCHEMA_VERSION` is treated as a miss,
-  the same as a `content_hash` mismatch — see Constraints below.
+  `(schema_version, prompt_version, content_hash, EnrichmentResult, enriched_at)`.
+  `schema_version` (sprint 009) is a small integer bumped whenever `EnrichmentResult`'s
+  *shape* changes; a stored entry whose version doesn't match `_CACHE_SCHEMA_VERSION` is
+  treated as a miss, the same as a `content_hash` mismatch — see Constraints below.
+  `prompt_version` (sprint 014) is a second, independent small integer — imported from
+  `llm_client.PROMPT_VERSION` — bumped whenever `_SYSTEM_PROMPT`'s *semantics* change; a
+  mismatch (including a pre-sprint-014 entry with no `prompt_version` key at all) is
+  likewise treated as a miss. The two version fields answer different questions (is the
+  stored *shape* current; is the stored *judgment* current under the current prompt) and
+  are checked independently — see Design below.
 - `enricher.py` — `LLMEnricher`, which satisfies `pipeline.Enricher` structurally and
   sequences everything.
 
@@ -75,9 +88,14 @@
   makes output depend on completion order breaks reproducibility of a run.
 - **`kind="internship"` events bypass this subsystem entirely** — no cache lookup, no LLM
   call, no field mutation. An internship arrives already classified and gated
-  deterministically by `adapters/ats_filters.py`, and this module's prompt is written
-  around a "STEM learning opportunity for K-12 youth" framing that would misjudge
-  legitimate job-posting text as adult-only and silently drop it.
+  deterministically by `adapters/ats_filters.py`, which is the correct classifier for
+  work-based-learning postings; this module's relevance prompt judges *learning
+  opportunities* (events and programs), a different content shape, so routing internships
+  through it at all — regardless of audience scope — would be applying the wrong
+  classifier, not a risk of misjudging one. (Before sprint 014 this bullet's stated risk
+  was specifically that the old K-12-only framing would misjudge job-posting text as
+  "adult-only" and drop it; that specific risk is moot now that the gate accepts any
+  audience, but the bypass itself is unchanged and independently justified.)
 - **`event.trusted` overrides the relevance gate.** First-party curated sources (the
   League's own classes via `adapters/leaguesync.py`) are still enriched and classified
   normally but must never be gate-dropped. Removing this makes the site's own operator
@@ -94,6 +112,17 @@
   with no `schema_version` key at all) is a miss, forcing exactly one re-enrichment per
   affected Event — real, one-time Anthropic spend proportional to the corpus, not a bug.
   See `sprint.md`'s Migration Concerns.
+- **A cache entry's `prompt_version` must match `llm_client.PROMPT_VERSION` to count as a
+  hit** (sprint 014). `content_hash` deliberately covers only an event's *input* fields
+  (the bullet above), so it cannot and must not detect a change to the *prompt's own
+  semantics* — widening the audience scope touches no field the hash reads. Without an
+  explicit prompt version, every one of the ~9,700 pre-sprint-014 cache entries (written
+  under the old K-12-only prompt) would stay a permanent, silent hit under the new prompt,
+  and the gate change would never actually take effect for existing corpus. A mismatch
+  (including a pre-sprint-014 entry with no `prompt_version` key) is a miss, forcing
+  exactly one re-enrichment per affected Event, the same shape as the `schema_version`
+  check but checked independently — bumping one must never imply or require bumping the
+  other, since they answer unrelated questions (see Design below).
 - **`llm_client.py` deliberately does not import `normalize/taxonomy.py`,** even though
   their controlled vocabularies overlap. Duplication is the accepted cost of keeping this
   module's only outward dependency the Anthropic API itself.
@@ -130,6 +159,28 @@
 very first version bump (nothing to compare against). An explicit integer, defaulting
 absent-means-`0` treated as always-stale-for-current, is simpler and says exactly what it
 means.
+
+**Why `prompt_version` is a new, separate constant, not a reuse of
+`_CACHE_SCHEMA_VERSION`** (sprint 014). *Context:* the gate-widening change (issue 22)
+needed some way to force re-evaluation of ~9,700 pre-existing cache entries whose stored
+`relevant` verdict was computed under the old, narrower prompt. *Alternatives considered:*
+bump `_CACHE_SCHEMA_VERSION` instead of adding a new field — rejected. That constant's
+entire documented purpose (§3 above, and its own module docstring) is answering "is the
+*stored value's shape* still what this code expects," a question about `EnrichmentResult`'s
+dataclass fields, orthogonal to whether the *judgment* those fields hold is still valid
+under the current prompt. Conflating them would mean every future prompt tweak also has
+to reason about whether it accidentally implies a schema change (and vice versa: a real
+schema change would force an unrelated re-judgment of `relevant`, which happens to be
+harmless today but is not a property the two concerns should share by construction).
+*Why this choice:* a second, independently-checked version integer costs one more field
+per cache entry and preserves the same "orthogonal signal" principle
+`_CACHE_SCHEMA_VERSION` itself was designed around (see the schema-version rationale
+directly above this one) — extended, not violated, by this addition. *Consequences:* a
+change that touches both `_SYSTEM_PROMPT`'s semantics and `EnrichmentResult`'s shape in
+the same sprint bumps both constants and forces two independent miss checks that happen
+to agree on the outcome for every entry; this has no different practical effect than one
+combined check would, so the cost of keeping them separate is purely conceptual clarity,
+paid once, here.
 
 **Provenance stamping.** Applied results are written through `Event.set(field, value,
 source, confidence)` with `source="llm_enrichment"`, `confidence=0.7`; the taxonomy
@@ -174,6 +225,10 @@
   `FALLBACK_SOURCE`, `FALLBACK_CONFIDENCE`, `LLMEnrichmentError`.**
 - **`_CACHE_SCHEMA_VERSION`** (sprint 009, `cache.py`) — the current stored-entry schema
   version; bumped whenever `EnrichmentResult`'s shape changes.
+- **`PROMPT_VERSION`** (sprint 014, `llm_client.py`) — the current `_SYSTEM_PROMPT`
+  semantic version; bumped whenever the prompt's judgment criteria change (e.g. the
+  audience-scope widening this sprint makes). Read by `cache.py` as an independent
+  cache-hit signal alongside `_CACHE_SCHEMA_VERSION`.
 
 ### Consumes
 - **`Event`, `Event.set`, `Event.identity_key` (from `model.py`)** — the record being
@@ -185,6 +240,13 @@
 
 ## 6. Open Questions / Known Limitations
 
+- **(Sprint 014)** The gate-widening prompt change forces exactly one re-enrichment for
+  every previously-cached `Event` — roughly 9,700 records at sprint start — via the new
+  `prompt_version` check. This is a real, one-time Anthropic API cost, accepted as the
+  direct price of correcting the K-12-only framing rather than avoided by any code
+  mechanism; it is not covered by (and does not resolve) the pre-existing "no cost
+  accounting or per-run call budget" limitation immediately below, which is about
+  *ongoing*, unbounded growth, not this one-time, bounded, known-size event.
 - The fail-open policy means an API outage produces a full run of `taxonomy_fallback`
   classifications at confidence 0.3, exported with no visible marker on the site. The
   yield report shows counts, not classification quality.
```
