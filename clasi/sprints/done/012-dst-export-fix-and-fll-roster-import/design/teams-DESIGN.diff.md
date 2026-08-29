---
source_file: teams-DESIGN.md
source_hash: 3af34f6d8f069e9183d8b5bb62186baee5b81443660151e1d11e174c846ec636
---
# Diff: teams-DESIGN.md

Comparison of the sprint overlay copy of `teams-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- teams-DESIGN.md (pristine)
+++ teams-DESIGN.md (current)
@@ -1,6 +1,6 @@
 # teams
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 (ticket 011-003, reopened — TBA `state_prov` filter defect) · **Status:** increments 1-4 complete (FTC + FRC + geocoding + site pages); increment 5 (FLL) deferred to a follow-on sprint
+**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 (sprint 012 — FLL static roster added) · **Status:** all five increments complete (FTC + FRC + geocoding + site pages + FLL static roster)
 
 ---
 
@@ -83,6 +83,36 @@
 "59" describes that now-superseded original fixture unless marked
 otherwise.
 
+**Sprint 012 adds the fifth and final increment: a static FLL roster.**
+Sprint 011 deliberately deferred First LEGO League (48 teams) because
+there is no public FLL API and no third-party aggregator — probed and
+confirmed at issue-write time. The only source is a hand-maintained,
+dated export living in a sibling repo
+(`../robot-team-analysis/fll/sd-fll-teams-contact-list.md`), which also
+carries contact data (40 email addresses, six of them volunteer
+coaches' personal Gmail accounts) this project has never published and
+structurally cannot — `model.Team` has no `email` field, by design (see
+Constraints). `teams.sources.static_roster.StaticRosterSource` reads a
+committed, already-contact-stripped roster file under `teams/data/` and
+never calls the injected `Fetcher` — a "source" in name and protocol
+shape only; there is no acquisition step to isolate a failure from, only
+a file read. Registered via a new `teams/registry/fll-sd.toml` entry
+(`adapter_type = "static_roster"`) alongside the two live sources, it
+needed zero changes to `merge_teams()`, `geocode_teams()`, or
+`export_teams()` — the pipeline stages after acquisition were already
+source-agnostic by the design choices sprint 011 made (see Design,
+below, for the specific paragraph that anticipated this). Because FLL's
+2026-27 season is announced as the program's last ever (LEGO declined to
+renew its FIRST partnership, 2026-03-19), the registry entry also
+carries `sunset_season = "2026-27"`; `run_teams()` logs a WARNING once
+`date.today()` passes that season rather than silently continuing to
+publish undated-feeling "current" data for a program that no longer
+exists. Expected total once this ships: **278 teams (152 FTC + 78 FRC +
+48 FLL)** — see Open Questions for the real-run confirmation this
+sprint requires before close, matching the ticket 011-003 lesson
+(commit a fixture built from real captured data, then verify against a
+live run, not just the fixture suite).
+
 ```
 BUILT (ticket 011-001):
   registry.load_active_sources(teams/registry/)   reused verbatim
@@ -139,6 +169,16 @@
      ↓                                       collision-free by construction)
   Header.astro / Footer.astro                "Teams" added to both hard-coded
                                               nav lists
+
+BUILT (sprint 012):
+  sources.static_roster.StaticRosterSource   reads committed, contact-stripped
+     ↓                                       roster file under teams/data/ --
+     ↓                                       never calls the injected Fetcher
+  teams/registry/fll-sd.toml                 adapter_type = "static_roster",
+     ↓                                       config.sunset_season = "2026-27"
+  teams.pipeline._TEAM_SOURCES               gains one entry; run_teams() gains
+     ↓                                       a sunset-date staleness WARNING
+  (feeds into merge_teams()/geocode_teams()/export_teams(), all unchanged)
 ```
 
 A freshly-extracted `Team` from either source still has
@@ -407,6 +447,43 @@
   publish with no `export.py` change; ticket 011-004's `latitude`/
   `longitude`/`location_precision` next) is published automatically
   with no `export.py` change required.
+- **(Sprint 012) `sources/static_roster.py` never calls the injected
+  `Fetcher`, structurally, not just by convention.** Every `TeamSource`
+  method still takes `fetcher` as a parameter (the protocol shape is
+  unchanged — `sources/base.py`'s `TeamSource` is a fixed three-method
+  contract), but `StaticRosterSource.fetch()` reads the committed roster
+  file straight off disk (`Path.read_text()`) and ignores the `fetcher`
+  argument entirely; `discover()` returns a single `TeamRef` whose `url`
+  is a local file path, never an HTTP URL. `tests/teams/
+  test_sources_static_roster.py` asserts this with a `Fetcher` test
+  double that raises on any call, run through the full `sources.base.run()`
+  chain — a stronger guarantee than an unused-parameter convention, the
+  same spirit as `test_sources_base.py`'s forbidden-import AST scan
+  (Constraints, above) even though the mechanism here is a runtime
+  assertion rather than a static one (an AST scan cannot prove a method
+  *never calls* an object it legitimately imports the type of).
+- **(Sprint 012) Contact fields are stripped at import time, never
+  carried into this module.** The upstream roster
+  (`../robot-team-analysis/fll/sd-fll-teams-contact-list.md`) carries
+  email addresses; the *committed* roster file under `teams/data/` that
+  `static_roster.py` actually reads has already had every contact column
+  removed before it was committed — `StaticRosterSource.extract()` never
+  sees a contact field, let alone filters one out. This is a stronger
+  guarantee than "filter emails at extraction time" would have been: a
+  bug in a filter can leak; a column that was never committed cannot.
+  Combined with `model.Team` having no `email` field at all (existing
+  invariant, above), there are now two independent layers between any
+  upstream contact data and a published `Team`.
+- **(Sprint 012) A `sunset_season` past its date degrades to a loud
+  warning, never a failure.** `teams.pipeline.run_teams()` parses
+  `SourceConfig.config["sunset_season"]` (a `"YYYY-YY"` string, e.g.
+  `"2026-27"`) once per run for any active source that declares it, and
+  logs `logging.WARNING` if `date.today()` is past the parsed season-end
+  date — the FLL program's own last season is 2026-27, and this project
+  has no way to know today what, if anything, replaces it (see Open
+  Questions). The roster keeps publishing regardless; a sunset date is a
+  staleness signal for an operator to notice and act on, not a reason to
+  stop shipping data that may still be the best available answer.
 
 ## 4. Design
 
@@ -445,6 +522,16 @@
 source (e.g. increment 5's FLL static roster) needs no `merge.py`
 change to get the same protection, only its own extraction-time
 mapping to `organization=""` where appropriate.
+
+**Confirmed true in practice (sprint 012).** `sources/static_roster.py`
+needed zero `merge.py` changes to ship. 28 of the FLL roster's 48
+records are family/home teams with no sponsoring school — the roster's
+own upstream data marks these distinctly from its 20 school-affiliated
+records, and `static_roster.py` maps that distinction to
+`organization=""`/`org_type="family_community"` the same way
+`sources/ftcscout.py` maps its `"Family/Community"` sentinel, landing
+in the identical "never group" bucket with no FLL-specific case
+anywhere in `merge.py`.
 
 **Why `location_precision` defaults to `"none"` here rather than
 `"city"`.** FTCScout does give city-level data, so it might seem
@@ -636,12 +723,28 @@
   `config.get_tba_url()`). Auth via `config.get_tba_api_key()`, read
   fresh per call (`_auth_headers()`, matching `adapters/leaguesync.py`'s
   pattern).
-- **`teams/registry/ftc-sd.toml`** / **`teams/registry/frc-sd.toml`**
-  (the latter this ticket) — the FTCScout and TBA sources'
-  `SourceConfig`s, loaded via `registry.loader.load_active_sources`
-  pointed at `teams/registry/` (not the main
-  `partner_scrape/registry/sources/` directory — a separate, disjoint
-  registry namespace).
+- **`sources.static_roster.StaticRosterSource`** (sprint 012) — the
+  concrete `TeamSource` for the committed FLL roster file. `discover()`
+  returns a single `TeamRef` pointing at the roster path under
+  `teams/data/` (read from `SourceConfig.config["roster_path"]`, no
+  network URL); `fetch()` reads that file directly off disk, ignoring
+  the `fetcher` argument (Constraints); `extract()` maps each roster row
+  to a `Team` with `sources=["static_roster"]`, `league="FLL"`, and
+  `organization=""`/`org_type="family_community"` for the 28 rows with
+  no sponsoring school, mirroring `sources/ftcscout.py`'s sentinel
+  mapping (Design). Never sets `latitude`/`longitude`/
+  `location_precision` — like every other source, that is exclusively
+  `teams.geo.geocode_teams()`'s job, run after this source the same way
+  it runs after FTCScout/TBA.
+- **`teams/registry/ftc-sd.toml`** / **`teams/registry/frc-sd.toml`** /
+  **`teams/registry/fll-sd.toml`** (the last, sprint 012) — the
+  FTCScout, TBA, and static-roster sources' `SourceConfig`s, loaded via
+  `registry.loader.load_active_sources` pointed at `teams/registry/`
+  (not the main `partner_scrape/registry/sources/` directory — a
+  separate, disjoint registry namespace). `fll-sd.toml`'s `config` dict
+  additionally carries `sunset_season = "2026-27"` (Constraints) — no
+  `SourceConfig` schema change, since `config` is already free-form per
+  `adapter_type` (`registry/schema.py`).
 - **`merge.merge_teams(teams: list[Team]) -> list[Team]`** (this
   ticket) — sets `Team.org_key`/`sibling_team_ids` in place by grouping
   on `normalize.partners.normalize_org_name`-normalized
@@ -804,6 +907,29 @@
 
 ## 6. Open Questions / Known Limitations
 
+- **(Sprint 012) The FLL successor program, if any, is unknown.** LEGO
+  declined to renew its 28-year FIRST partnership on 2026-03-19, making
+  2026-27 FLL's last season; `fll-sd.toml`'s `sunset_season` makes that
+  loud (Constraints) rather than silent, but this subsystem has no way
+  to react to whatever replaces FLL until a successor program actually
+  exists with a name, data source, and roster shape — not something to
+  speculatively build against now.
+- **(Sprint 012) Pre-close verification requirement, carried forward
+  directly from the ticket 011-003 lesson.** That defect shipped because
+  a hand-authored test fixture (`"CA"` on every record) didn't match
+  what TBA's real API actually returned (`"California"` on the
+  majority), and was only caught by running the real pipeline during
+  sprint validation, not by the fixture-based test suite. The FLL static
+  roster is likewise a new external-data source this subsystem has never
+  ingested before; its fixture must be a direct excerpt of the real
+  committed roster file's rows (not a hand-authored approximation), and
+  before this sprint closes, a real `partner-scrape teams --dry-run -v`
+  run against the live registry (not fixtures) must confirm 278 teams
+  overall and `meta.by_league["FLL"] == 48` — see `sprint.md`'s Test
+  Strategy for the exact command. Recorded here as a standing
+  reminder for whoever verifies this sprint before close, not just in
+  the sprint document, since this file is where the ticket-011-003
+  lesson itself was already recorded.
 - **RESOLVED (ticket 011-003, reopened 2026-08-28) — a live
   `partner-scrape teams` run during ticket 011-005's work returned
   only 19 of the expected ~59 FRC teams (171 total, not 211); this was
```
