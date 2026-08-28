---
source_file: DESIGN.md
source_hash: a7c81a676d27a36ee242325cf080820e7e3813837fa47d76a779a20d071825dc
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -43,6 +43,21 @@
 `run()` returns, not inside it) that reads *all* accumulated per-partner logs — not only
 this run's — and projects them into the published `public/data/` contract. See
 `export/DESIGN.md` for both.
+
+**Sprint 011 addition — a second, sibling pipeline, not an extension of
+the one above.** `partner_scrape/teams/` (new subsystem — see
+`teams/DESIGN.md`) is invoked by its own CLI subcommand,
+`partner-scrape teams`, calling `teams.pipeline.run_teams()`, which
+sequences `teams.sources.{ftcscout,tba}` → `teams.merge` → `teams.geo`
+→ `teams.export`. It is not called from `pipeline.run()` and does not
+call it; it reuses `registry.schema/loader`, `fetch.PoliteFetcher`,
+`config.py` (see the `config.py` bullet below), and one function of
+`normalize.partners`, but has no edge into `adapters/`, `enrich/`,
+`normalize.run()`, or either existing export writer. This is
+deliberate, not an oversight: a `Team` is a standing entity with no
+date, and `export/writer.py`'s current-and-upcoming filter would drop
+every one of them if it were routed through `Opportunity`. See
+`teams/DESIGN.md` for the full module breakdown.
 
 **Root-level modules.**
 
@@ -58,11 +73,19 @@
   `pipeline.run()`, plus the `discover-candidates` subcommand for the lead-generation
   flow. Constructs the default concrete implementations (`LLMEnricher` with
   `AnthropicLLMClient`, `YieldReporter`) and owns the mirror step and console output. No
-  business decisions live here.
+  business decisions live here. **Sprint 011:** gains a `teams` subcommand
+  (`partner-scrape teams [--dry-run] [--source ftcscout|tba] [--site-dir DIR]
+  [--no-mirror] [-v]`), calling `teams.pipeline.run_teams()` and, unless `--no-mirror`,
+  `export.mirror_site_data`. The existing `run`/`discover-candidates` subcommands are
+  unchanged.
 - **`config.py`** — the only module in the package that reads `os.environ`. Accessors for
   `SCRAPE_CACHE_DIR` (required, no default), `SITE_DIR`, `MIRROR_SITE_DIRS`,
   `LEAGUESYNC_API_KEY`, and `LEAGUESYNC_URL`. Values are assembled by dotconfig into
   layered `.env` files before the process starts; this module only reads what landed.
+  **Sprint 011:** gains `get_tba_api_key()`/`get_tba_url()` (reading `TBA_KEY`/`TBA_URL`),
+  mirroring `get_leaguesync_api_key()`/`get_leaguesync_url()` exactly, including the
+  surrounding-quote stripping SOPS-decrypted secrets need. `config.py` remains the only
+  module touching `os.environ`.
 - **`model.py`** — the canonical `Event` record and the shared identity vocabulary. A flat
   dataclass (~26 fields, sprint 009: `opportunity_type` joins the classification fields
   alongside `areas_of_interest`/`age_grade_level`/`cost_range`/`time_of_day`) plus a
@@ -91,6 +114,7 @@
 | [`observability/`](observability/DESIGN.md) | Per-source yield accounting, run-over-run deltas, zero-yield and cliff alerts, and the `yield-history.json` snapshot. |
 | [`registry/`](registry/DESIGN.md) | The data-driven catalog: one TOML file per organization, plus separate hub, ad, and candidate catalogs. Onboarding is a data edit. |
 | [`store/`](store/DESIGN.md) | A durable SQLite table of canonical Events for future incremental scraping. Built and tested, **not wired into the pipeline**. |
+| [`teams/`](teams/DESIGN.md) | (sprint 011) A second, independent pipeline: acquires FTC/FRC team rosters, resolves cross-league identity, geocodes offline, and publishes `teams.json`. Structurally disjoint from every subsystem above — no shared adapter registration, no `Opportunity`. |
 
 ## 4. Shared Conventions
 
@@ -166,13 +190,18 @@
   / `past-events.json`, projected from the new persistent per-partner accumulation store
   (not written into `src/data/`, since `src/` is Astro's own build input and this is meant
   to be fetchable at runtime as a public API — see `export/DESIGN.md`).
+- **(Sprint 011) `partner-scrape teams`** — the new subcommand; and **`src/data/teams.json`**
+  — a wholly separate, standalone data contract (San Diego FTC/FRC robotics teams), mirrored
+  into extra checkouts the same way `opportunities.json` is. See `teams/DESIGN.md`.
 
 ### Consumes
 - **`stem-ecosystem`'s `src/data/partners.json`** — read-only, for the partner join.
 - **Environment** (via `config.py` only): `SCRAPE_CACHE_DIR` (required), `SITE_DIR`,
-  `MIRROR_SITE_DIRS`, `LEAGUESYNC_API_KEY`, `LEAGUESYNC_URL`; and `ANTHROPIC_API_KEY`,
-  resolved by the `anthropic` SDK itself.
+  `MIRROR_SITE_DIRS`, `LEAGUESYNC_API_KEY`, `LEAGUESYNC_URL`, and (sprint 011) `TBA_KEY`/
+  `TBA_URL`; and `ANTHROPIC_API_KEY`, resolved by the `anthropic` SDK itself.
 - **~100 partner websites and APIs**, reached only through `fetch/`.
+- **(Sprint 011) FTCScout and The Blue Alliance REST APIs**, reached only through
+  `fetch.PoliteFetcher`, from `teams/sources/`.
 
 ## 6. Open Questions / Known Limitations
 
@@ -191,3 +220,8 @@
   timestamps are wrong across the DST boundary.
 - `scrapy` and `w3lib` remain declared dependencies but the fetch path is stdlib
   `urllib`; the declarations should be audited.
+- (Sprint 011) Whether `teams.json` is ever joined to the curated partner directory is an
+  open product question — only 1 of 105 distinct team organizations is already a partner;
+  the other 104 are a candidate recruitment list, not resolved here. `TBA_KEY` is
+  provisioned and verified locally but not yet in the scheduled workflow's GitHub Actions
+  secrets — see `sprint.md`'s Migration Concerns.
```
