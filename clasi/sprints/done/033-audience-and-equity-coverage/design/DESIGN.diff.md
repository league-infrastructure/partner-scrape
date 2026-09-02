---
source_file: DESIGN.md
source_hash: 6eb95ac104ccd714903551513e77d7d1ceefd33f90d375b52d2dff2dcc833acf
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -117,6 +117,12 @@
   030 (educator programs) build on: registering a source with `program_kind =
   "program"` gets the same bypass treatment with zero further code change.
 
+**Sprint 033 addition.** No root-level module (`pipeline.py`, `cli.py`, `config.py`,
+`model.py`) changes this sprint — `bilingual`/accessibility signals and the new `region`
+classification are both derived from an `Event`'s already-existing fields at normalize
+time, not stored on `Event` itself. See `normalize/DESIGN.md`, `observability/DESIGN.md`,
+and `export/DESIGN.md`'s own sprint 033 sections.
+
 ## 3. Subsystem Map
 
 Each has its own `DESIGN.md` in its own directory.
@@ -217,13 +223,14 @@
   exported opportunity payload.
 - **`model.Event`, `Provenance`, `Kind`, `identity_key`, `normalize_title`,
   `same_record`** — the shared record vocabulary every subsystem speaks.
-- **The site data contract** — `src/data/opportunities.json`, `src/data/scrape-meta.json`,
-  `src/data/ads.json`, and `public/images/opportunities/*` written into the
-  `stem-ecosystem` checkout; plus, since sprint 009, the additive public data contract
-  `public/data/partners.json` and each partner's `public/data/partners/<slug>/events.json`
-  / `past-events.json`, projected from the new persistent per-partner accumulation store
-  (not written into `src/data/`, since `src/` is Astro's own build input and this is meant
-  to be fetchable at runtime as a public API — see `export/DESIGN.md`).
+- **The site data contract** — `opportunities.json`, `scrape-meta.json`, `ads.json`, and
+  `images/opportunities/*` written into `own_data_dir` (sprint 025's sole write target);
+  plus, since sprint 009, the additive public data contract `public/data/partners.json`
+  and each partner's `public/data/partners/<slug>/events.json` / `past-events.json`,
+  projected from the new persistent per-partner accumulation store (not written into
+  `src/data/`, since `src/` is Astro's own build input and this is meant to be fetchable at
+  runtime as a public API — see `export/DESIGN.md`). **(Sprint 033)** `scrape-meta.json`
+  gains a `"regions"` key — a per-region opportunity count. See `export/DESIGN.md`.
 - **(Sprint 011) `partner-scrape teams`** — the new subcommand; and **`src/data/teams.json`**
   — a wholly separate, standalone data contract (San Diego FTC/FRC robotics teams). See
   `teams/DESIGN.md`.
```
