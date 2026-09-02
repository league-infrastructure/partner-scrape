---
source_file: DESIGN.md
source_hash: 90884fd08ea3ce09959e1ddbf4573bde8cb51528b6eb9a28dd68b9c30bc5e0be
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -100,7 +100,22 @@
   utility promoted here from `normalize/run.py` because sprint 009 needs it in two places
   (the per-event slug in `normalize/run.py`, the per-partner slug in the new
   `export/partner_log.py`) and this is the module every other module already treats as the
-  home for shared identity primitives. `Kind` is `"event" | "program" | "internship"`.
+  home for shared identity primitives. `Kind` is `"event" | "program" | "internship"` —
+  unchanged this sprint, both non-`"event"` values already existed (`"program"` was
+  reserved but unused before sprint 027).
+  **(Sprint 027)** Two additive changes: `Event` gains `eligibility: str = ""` (a
+  per-record eligibility note, set via `Event.set(...)` by the new program-page
+  extraction path — see `adapters/DESIGN.md` — for the case a per-*source*
+  `taxonomy_defaults.eligibility` default cannot express, e.g. a listing source
+  whose individual program cards each need a different eligibility note); and
+  `model.py` gains `PROGRAM_EXTRACTION_KINDS = frozenset({"internship",
+  "program"})`, a shared constant naming which `Kind` values get the
+  curated-record bypass treatment (`enrich/`'s enrichment pass, `normalize/`'s
+  collapse/dedup) — generalizing what was previously a single hardcoded
+  `kind == "internship"` check duplicated at three call sites across two
+  modules. This is the explicit reuse surface sprints 029 (competitions) and
+  030 (educator programs) build on: registering a source with `program_kind =
+  "program"` gets the same bypass treatment with zero further code change.
 
 ## 3. Subsystem Map
 
@@ -108,7 +123,7 @@
 
 | Subsystem | One line |
 |---|---|
-| [`adapters/`](adapters/DESIGN.md) | Ten per-vendor strategies implementing `discover → fetch → extract`, dispatched by `adapter_type` through a one-line registration table. |
+| [`adapters/`](adapters/DESIGN.md) | Thirteen per-vendor strategies implementing `discover → fetch → extract`, dispatched by `adapter_type` through a one-line registration table. (Sprint 027) Two of the thirteen, `program_page`/`program_listing`, extract via a bespoke LLM call rather than a structured API or the HTML ladder. |
 | [`discovery/`](discovery/DESIGN.md) | Resolving a source into fetchable URLs (sitemap diff, listing crawl) — plus hub scanning, which generates *organization* leads and is structurally forbidden from producing Events. |
 | [`enrich/`](enrich/DESIGN.md) | The LLM layer: field recovery, controlled-vocabulary classification, and the relevance gate, behind a content-hash cache and a fail-open policy. |
 | [`export/`](export/DESIGN.md) | Every write across the repo boundary into the site: `opportunities.json`, `ads.json`, self-hosted images, and (sprint 009) a persistent per-partner accumulation log plus the published `public/data/` partners-and-events contract projected from it. |
```
