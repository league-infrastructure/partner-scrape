---
source_file: export-DESIGN.md
source_hash: a0326415d8a14b0f50c40de3f6ef4b93d828222b344f27f4a38f529fca4a5970
---
# Diff: export-DESIGN.md

Comparison of the sprint overlay copy of `export-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- export-DESIGN.md (pristine)
+++ export-DESIGN.md (current)
@@ -21,6 +21,14 @@
 event files, self-describing enough that a consumer needs no other data source (issue 15).
 This is still squarely "every write across the repo boundary" — it is a second *shape* of
 write, not a new responsibility for the subsystem.
+
+**(Sprint 033) `scrape-meta.json` gains a `"regions"` key.** `writer.py`'s
+`export_opportunities()` now also computes a per-region count over the exported
+(current/upcoming) payload — using `Opportunity.region`, a value `normalize/` has already
+derived (`normalize/DESIGN.md`'s sprint 033 addition) — and writes it into
+`scrape-meta.json` alongside the existing `last_updated`. This is additive: an existing
+consumer reading only `last_updated` is unaffected. See §4 and Migration Concerns in
+`sprint.md`.
 
 ## 2. Orientation
 
@@ -126,9 +134,20 @@
 - **`export/` re-derives nothing.** No field mapping, no taxonomy, no dedup. Its inputs
   arrive finished from `normalize/`. Adding a derivation here would apply it after
   deduplication chose a winner, silently diverging from what the rest of the pipeline
-  computed.
+  computed. **(Sprint 033)** The `scrape-meta.json` region count is a plain aggregation
+  (a `Counter` over an already-finished `Opportunity.region` value each record already
+  carries when it arrives here) — not a derivation. `writer.py` does not compute what a
+  record's region *is*; `normalize/` already decided that. This constraint is about
+  re-deciding a record's own classification after dedup already chose a winner; counting
+  an existing, finished field's already-decided values is the same "no re-derivation"
+  discipline `observability/yield_report.py`'s own found/dated counting already follows
+  for a different field.
 - **`Opportunity.sources` is dropped on serialization.** It is `normalize/`'s
-  cross-source bookkeeping, not part of the site's Opportunities table.
+  cross-source bookkeeping, not part of the site's Opportunities table. **(Sprint 033)**
+  `Opportunity.region` is dropped the same way — also `normalize/`'s internal bookkeeping,
+  not part of the site's Opportunities table — while its *aggregate* (a per-region count,
+  not the per-record value) is written into `scrape-meta.json` instead. `SITE_SCHEMA_FIELDS`
+  now excludes both `sources` and `region`.
 - **`images.py` never interprets downloaded bytes as anything but a static asset,** and
   refuses any URL that is not `http(s)://` before performing any I/O — `file://`, `data:`,
   and everything else are rejected without a fetch.
@@ -258,9 +277,12 @@
 ## 5. Interfaces
 
 ### Exposes
-- **`export_opportunities(opportunities, site_dir=None, *, today=None, dry_run=False) ->
-  list[dict]`** — writes `src/data/opportunities.json` and `src/data/scrape-meta.json`;
-  returns the payload it wrote (or would have written). Raises on an unwritable target.
+- **`export_opportunities(opportunities, *, today=None, dry_run=False, own_data_dir=None)
+  -> list[dict]`** — writes `opportunities.json` and `scrape-meta.json` into
+  `own_data_dir` (sprint 025's sole write target, see that sprint's `sprint.md`); returns
+  the payload it wrote (or would have written). Raises on an unwritable target. **(Sprint
+  033)** `scrape-meta.json` gains a `"regions"` key: a `dict[str, int]` mapping each known
+  region (plus `"unclassified"`) to its count over the exported payload.
 - **`export_ads(ad_configs, site_dir=None, *, dry_run=False)`** — writes
   `src/data/ads.json`. Same loud-failure contract.
 - **`load_ad_configs(directory=None) -> list[AdConfig]`** — parses ad TOML files
@@ -350,3 +372,14 @@
   files are unified into one contract, or the Astro site is refactored to read the new
   shape directly, remains an open, stakeholder-level product decision (issue 15's own
   framing) — this sprint deliberately keeps both live rather than deciding it.
+- **(Sprint 033)** `scrape-meta.json`'s `"regions"` key is written only by
+  `export_opportunities()` (the `own_data_dir`/`opportunities.json` contract) — not
+  threaded into `publish.py`'s separate `public/data/` projection, which has no
+  equivalent per-partner-projection meta file to add it to. Regional counts are a
+  whole-corpus measurement, not a per-partner one, so this is not considered a gap for
+  `publish.py` to close, only a note that the two contracts' meta shapes are not
+  symmetric (unchanged from before this sprint — see the sprint 009 entry above).
+- **(Sprint 033)** Whether `stem-ecosystem` ever surfaces `scrape-meta.json`'s regional
+  counts (an internal dashboard, a build-time check, a site footer stat) is out of this
+  repo's scope to decide — this sprint's job ends at publishing the count. See
+  `sprint.md`'s Migration Concerns.
```
