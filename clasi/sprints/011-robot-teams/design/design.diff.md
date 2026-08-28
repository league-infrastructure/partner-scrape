---
source_file: design.md
source_hash: d93d22e96b7720c960f392db9163ae6cabef2d06b59d5ccdb11a7ab992ececbf
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -67,6 +67,20 @@
 store/          built, not wired in
 ```
 
+**Sprint 011 addition — a second, independent pipeline.**
+`partner_scrape/teams/` (own CLI subcommand: `partner-scrape teams`) is
+deliberately **not** part of the flow above. It acquires San Diego FIRST
+robotics team rosters (FTC via FTCScout, FRC via The Blue Alliance),
+resolves cross-league identity, locates each team through an
+offline-only geocoding ladder, and publishes `teams.json` alongside
+`opportunities.json`/`ads.json`. It reuses `registry/`'s schema/loader,
+`fetch/`'s `PoliteFetcher`, `config.py`, and one function of
+`normalize/partners.py`, but never touches `adapters/`, `enrich/`,
+`normalize.run()`, or `pipeline.run()` — a `Team` is a standing entity
+with no date, and would be silently dropped by `export/`'s
+current-and-upcoming filter if it were routed through `Opportunity`.
+See [`partner_scrape/teams/DESIGN.md`](../../partner_scrape/teams/DESIGN.md).
+
 ## 4. Subsystem map
 
 The source root itself carries an overview doc; each subsystem carries its own, co-located
@@ -95,6 +109,10 @@
   data-driven catalog of sources, hubs, ads, and candidates.
 - [`partner_scrape/store/DESIGN.md`](../../partner_scrape/store/DESIGN.md) — durable
   SQLite event table; built and tested, not wired into the pipeline.
+- [`partner_scrape/teams/DESIGN.md`](../../partner_scrape/teams/DESIGN.md) — (sprint 011)
+  a second, independent pipeline: scrapes, geocodes, and publishes San Diego FIRST
+  robotics teams (FTC/FRC) as `teams.json`, structurally disjoint from the
+  `Opportunity` pipeline above.
 
 ## 5. Global conventions
 
@@ -147,3 +165,7 @@
 - A circular import between `adapters.listing_html` and `discovery.listing` is worked
   around by import ordering rather than fixed.
 - DST is unhandled: `normalize/run.py` hard-codes a `-07:00` offset.
+- (Sprint 011) Whether `teams.json` is ever joined to the curated partner directory
+  is an open product question, not resolved here: only 1 of 105 distinct team
+  organizations is already a partner, while the other 104 are a candidate
+  recruitment list for Fleet/League staff to act on, not an architectural decision.
```
