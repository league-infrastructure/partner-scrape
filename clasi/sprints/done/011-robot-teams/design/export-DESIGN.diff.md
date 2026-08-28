---
source_file: export-DESIGN.md
source_hash: 8d1ac740bde3d6d9e4ea71c4ef45d4550de2239e75de6ce1ace6a0dd1ab2e1db
---
# Diff: export-DESIGN.md

Comparison of the sprint overlay copy of `export-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- export-DESIGN.md (pristine)
+++ export-DESIGN.md (current)
@@ -67,7 +67,12 @@
   — copies a *finished* export's output files (`opportunities.json`, `scrape-meta.json`,
   `ads.json`, plus the opportunity images) into additional site checkouts. Sprint 009:
   also recursively copies the new `public/data/` tree, same additive-only,
-  byte-identical-skip semantics as the existing image mirror.
+  byte-identical-skip semantics as the existing image mirror. **Sprint 011:**
+  `MIRRORED_DATA_FILES` gains `"teams.json"` — a one-line allowlist addition. The file
+  itself is written by `partner_scrape/teams/export.py`, a module in the new, structurally
+  separate `teams/` subsystem (see `teams/DESIGN.md`), not by this subsystem's own
+  `writer.py`/`ads.py`; `mirror.py` copies it purely by filename, the same way it already
+  copies `opportunities.json`/`ads.json` without caring which module produced them.
 
 `pipeline.run()` calls `export_opportunities`, `export_ads`, and (sprint 009)
 `partner_log.record`, and constructs the `EventImageDownloader` it passes into
@@ -119,6 +124,11 @@
   per checkout; overwriting it would clobber one site's roster with another's.
   `yield-history.json` is per-run operational state belonging to the run that produced it.
   `MIRRORED_DATA_FILES` is the explicit allowlist.
+- **(Sprint 011) `teams.json` is a flat, standalone file added to `MIRRORED_DATA_FILES`,
+  never a new responsibility for `writer.py`/`ads.py`.** `export/` did not gain a new
+  writer this sprint — `teams/export.py` (a different subsystem) writes the file;
+  `mirror.py` only extends its existing allowlist to include it. This subsystem's writers
+  (`writer.py`, `ads.py`) are unmodified.
 - **`images.py` never interprets downloaded bytes as anything but a static asset,** and
   refuses any URL that is not `http(s)://` before performing any I/O — `file://`, `data:`,
   and everything else are rejected without a fetch.
@@ -283,8 +293,9 @@
   stored local filename, or `""` for anything rejected. Never raises. Instance-scoped
   content-hash dedup.
 - **`mirror_site_data(primary_site_dir, target_site_dirs, *, dry_run=False)`** — copies
-  `MIRRORED_DATA_FILES`, `public/images/opportunities/`, and (sprint 009)
-  `public/data/` (recursively) into each target.
+  `MIRRORED_DATA_FILES` (sprint 011: `opportunities.json`, `scrape-meta.json`, `ads.json`,
+  `teams.json`), `public/images/opportunities/`, and (sprint 009) `public/data/`
+  (recursively) into each target.
 - **`AdConfig`, `ImageFetcher`, `UrllibImageFetcher`, `ImageFetchResponse`,
   `MIRRORED_DATA_FILES`.**
 - **`is_current_or_upcoming(opportunity, today) -> bool`, `SITE_SCHEMA_FIELDS`,
```
