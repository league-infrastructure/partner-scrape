---
source_file: design.md
source_hash: 7a77f7b5151a38fbdba17b0cceafd226eb11575ff0b6960c3c9fbbe91a4346d9
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -70,16 +70,17 @@
 **Sprint 011 addition — a second, independent pipeline.**
 `partner_scrape/teams/` (own CLI subcommand: `partner-scrape teams`) is
 deliberately **not** part of the flow above. It acquires San Diego FIRST
-robotics team rosters (FTC via FTCScout, FRC via The Blue Alliance),
-resolves cross-league identity, locates each team through an
-offline-only geocoding ladder, and publishes `teams.json` alongside
-`opportunities.json`/`ads.json`. It reuses `registry/`'s schema/loader,
-`fetch/`'s `PoliteFetcher`, `config.py`, and one function of
-`normalize/partners.py`, but never touches `adapters/`, `enrich/`,
-`normalize.run()`, or `pipeline.run()` — a `Team` is a standing entity
-with no date, and would be silently dropped by `export/`'s
-current-and-upcoming filter if it were routed through `Opportunity`.
-See [`partner_scrape/teams/DESIGN.md`](../../partner_scrape/teams/DESIGN.md).
+robotics team rosters (FTC via FTCScout, FRC via The Blue Alliance,
+static FLL as of sprint 012), resolves cross-league identity, locates
+each team through an offline-only geocoding ladder, and publishes
+`teams.json` alongside `opportunities.json`/`ads.json`. It reuses
+`registry/`'s schema/loader, `fetch/`'s `PoliteFetcher`, `config.py`,
+and one function of `normalize/partners.py`, but never touches
+`adapters/`, `enrich/`, `normalize.run()`, or `pipeline.run()` — a
+`Team` is a standing entity with no date, and would be silently dropped
+by `export/`'s current-and-upcoming filter if it were routed through
+`Opportunity`. See
+[`partner_scrape/teams/DESIGN.md`](../../partner_scrape/teams/DESIGN.md).
 
 ## 4. Subsystem map
 
@@ -164,8 +165,17 @@
 - Yield alerts have no delivery channel beyond console output in the scheduled run's log.
 - A circular import between `adapters.listing_html` and `discovery.listing` is worked
   around by import ordering rather than fixed.
-- DST is unhandled: `normalize/run.py` hard-codes a `-07:00` offset.
+- **(Resolved, sprint 012)** DST is now handled: `normalize/run.py` resolves each
+  naive datetime's UTC offset from `zoneinfo.ZoneInfo("America/Los_Angeles")` at
+  serialization time instead of a hard-coded `-07:00` constant. See
+  `partner_scrape/normalize/DESIGN.md` for the fold-convention decision on the
+  two DST-transition edge cases.
 - (Sprint 011) Whether `teams.json` is ever joined to the curated partner directory
   is an open product question, not resolved here: only 1 of 105 distinct team
   organizations is already a partner, while the other 104 are a candidate
   recruitment list for Fleet/League staff to act on, not an architectural decision.
+- (Sprint 012) `partner_scrape/teams/` now carries a third source,
+  `static_roster` (FLL, 48 teams, one-time-dated per season), alongside the two
+  live sources (FTCScout, TBA) — see `partner_scrape/teams/DESIGN.md`. FLL's
+  season is documented as the program's last (`sunset_season = "2026-27"`); what
+  replaces it, if anything, is unresolved and out of this project's control.
```
