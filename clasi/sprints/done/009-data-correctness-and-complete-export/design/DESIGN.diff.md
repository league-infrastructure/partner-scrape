---
source_file: DESIGN.md
source_hash: db83bf5487781d5c3793c45bcba1a5e53aa872dbd98cf4de82df4e890a28230b
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -25,13 +25,24 @@
 registry.load_active_sources()
   → ThreadPoolExecutor(8) × [ adapters.run(source, fetcher) ]     per-source isolation
       where adapters.run = discover → fetch → extract             (discovery/, fetch/, extract/)
-  → enrichers  (enrich.LLMEnricher: recover fields, classify, gate relevance)
+  → enrichers  (enrich.LLMEnricher: recover fields, classify (incl. opportunity_type), gate relevance)
   → normalize.run(events, partners.json, image_resolver)          collapse → dedup → map
-  → export.export_opportunities(...) + export.export_ads(...)
+  → export.export_opportunities(...) + export.export_ads(...) + export.partner_log.record(...)
 ```
 
-`cli.py` then optionally calls `export.mirror_site_data(...)` and prints the yield report
+`cli.py` then, after `run()` returns, calls `export.publish.project(...)` (collapses the
+accumulated per-partner logs into the published `public/data/` tree — sprint 009) and
+`export.mirror_site_data(...)` (now also mirrors that tree), and prints the yield report
 from `observability/`. The whole run touches the network only through `fetch/`.
+
+**Sprint 009 addition.** `export.partner_log.record(...)` is a new call inside
+`pipeline.run()`, alongside the existing `export_opportunities`/`export_ads` calls: it
+persists this run's `Opportunity`s into a durable, per-partner, append-only log (never
+overwritten, unlike the flat `opportunities.json`). `export.publish.project(...)` is a new,
+separate, CLI-sequenced step (mirroring how `mirror_site_data` is already sequenced after
+`run()` returns, not inside it) that reads *all* accumulated per-partner logs — not only
+this run's — and projects them into the published `public/data/` contract. See
+`export/DESIGN.md` for both.
 
 **Root-level modules.**
 
@@ -53,11 +64,16 @@
   `LEAGUESYNC_API_KEY`, and `LEAGUESYNC_URL`. Values are assembled by dotconfig into
   layered `.env` files before the process starts; this module only reads what landed.
 - **`model.py`** — the canonical `Event` record and the shared identity vocabulary. A flat
-  dataclass (~25 fields) plus a side-car `field_provenance: dict[str, Provenance]` map;
-  `Event.set(field, value, source, confidence)` writes both at once. Also owns
-  `normalize_title`, `identity_key`/`Event.identity_key()` (acquisition identity: "have we
-  seen this exact record from this source?"), and `same_record`. `Kind` is
-  `"event" | "program" | "internship"`.
+  dataclass (~26 fields, sprint 009: `opportunity_type` joins the classification fields
+  alongside `areas_of_interest`/`age_grade_level`/`cost_range`/`time_of_day`) plus a
+  side-car `field_provenance: dict[str, Provenance]` map; `Event.set(field, value, source,
+  confidence)` writes both at once. Also owns `normalize_title`, `identity_key`/
+  `Event.identity_key()` (acquisition identity: "have we seen this exact record from this
+  source?"), `same_record`, and (sprint 009) `slugify` — a small, shared text-to-slug
+  utility promoted here from `normalize/run.py` because sprint 009 needs it in two places
+  (the per-event slug in `normalize/run.py`, the per-partner slug in the new
+  `export/partner_log.py`) and this is the module every other module already treats as the
+  home for shared identity primitives. `Kind` is `"event" | "program" | "internship"`.
 
 ## 3. Subsystem Map
 
@@ -68,7 +84,7 @@
 | [`adapters/`](adapters/DESIGN.md) | Ten per-vendor strategies implementing `discover → fetch → extract`, dispatched by `adapter_type` through a one-line registration table. |
 | [`discovery/`](discovery/DESIGN.md) | Resolving a source into fetchable URLs (sitemap diff, listing crawl) — plus hub scanning, which generates *organization* leads and is structurally forbidden from producing Events. |
 | [`enrich/`](enrich/DESIGN.md) | The LLM layer: field recovery, controlled-vocabulary classification, and the relevance gate, behind a content-hash cache and a fail-open policy. |
-| [`export/`](export/DESIGN.md) | Every write across the repo boundary into the site: `opportunities.json`, `ads.json`, self-hosted images, and mirroring into additional checkouts. |
+| [`export/`](export/DESIGN.md) | Every write across the repo boundary into the site: `opportunities.json`, `ads.json`, self-hosted images, mirroring into additional checkouts, and (sprint 009) a persistent per-partner accumulation log plus the published `public/data/` partners-and-events contract projected from it. |
 | [`extract/`](extract/DESIGN.md) | The confidence-ranked extraction ladder: one HTML page in, `{field: (value, confidence)}` out. Pure, no I/O. |
 | [`fetch/`](fetch/DESIGN.md) | The only network access in the system: the `Fetcher` seam, robots.txt, per-domain throttling, on-disk conditional-GET cache, and the optional headless browser. |
 | [`normalize/`](normalize/DESIGN.md) | Recurrence collapse, cross-source dedup, taxonomy derivation, partner join — `Event`s in, site-shaped `Opportunity` records out. |
@@ -145,7 +161,11 @@
   `same_record`** — the shared record vocabulary every subsystem speaks.
 - **The site data contract** — `src/data/opportunities.json`, `src/data/scrape-meta.json`,
   `src/data/ads.json`, and `public/images/opportunities/*` written into the
-  `stem-ecosystem` checkout(s).
+  `stem-ecosystem` checkout(s); plus, since sprint 009, the additive public data contract
+  `public/data/partners.json` and each partner's `public/data/partners/<slug>/events.json`
+  / `past-events.json`, projected from the new persistent per-partner accumulation store
+  (not written into `src/data/`, since `src/` is Astro's own build input and this is meant
+  to be fetchable at runtime as a public API — see `export/DESIGN.md`).
 
 ### Consumes
 - **`stem-ecosystem`'s `src/data/partners.json`** — read-only, for the partner join.
@@ -161,7 +181,10 @@
 - There is a circular import between `adapters.listing_html` and `discovery.listing`,
   currently worked around by import ordering in `cli.py`.
 - The site data contract is unversioned and unvalidated. A field rename on the site side
-  shows up as missing data on a rendered page, not as an export failure.
+  shows up as missing data on a rendered page, not as an export failure. This now applies
+  to two parallel contracts (`src/data/opportunities.json` and, since sprint 009,
+  `public/data/partners.json` + per-partner event files) — see `export/DESIGN.md`'s Open
+  Questions for why the sprint kept them parallel rather than unifying them now.
 - Yield alerts are printed to the console. A zero-yield source in a scheduled run is only
   noticed if someone reads the log.
 - `_TZ_OFFSET` in `normalize/run.py` is the hard-coded literal `-07:00`, so exported
```
