---
source_file: registry-DESIGN.md
source_hash: 390c295f49861cc76bb765bf383a3e937a0b65267a796d36080cde38d6920272
---
# Diff: registry-DESIGN.md

Comparison of the sprint overlay copy of `registry-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- registry-DESIGN.md (pristine)
+++ registry-DESIGN.md (current)
@@ -1,8 +1,78 @@
 # Registry
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 030 — Offering Registry catalog + educator-PD program-page registrations) · **Status:** stable
 
 ---
+
+## Revision (2026-09-02 — sprint 030 educator layer and volunteer org profiles)
+
+Two independent registration efforts, one per linked issue, using two
+different already-existing mechanisms — no new registry schema or
+loader either way:
+
+**Issue 14 Strategy B / issue 33 part 2 (`Offering` records) — the
+Directory Registry, not this document's main `sources/` catalog.**
+`directory/registry/offerings-sd.toml` is a new entry in the same
+curated, non-`Opportunity` registry directory `places-sd.toml`/
+`hack-club-sd.toml` already live in (`partner_scrape/directory/
+registry/`, loaded by the identical `registry.loader.
+load_active_sources()` call those two already use, structurally
+disjoint from this document's own `sources/`/`hubs/`/`candidates/`/
+`ads/` catalogs — see `directory/DESIGN.md`'s Constraints for why).
+`adapter_type = "offering_static_roster"`, dispatched by `directory.
+pipeline.run_directory()`'s now-three-way `_OFFERING_SOURCES` check —
+see `directory/DESIGN.md`'s own sprint 030 Revision for the full
+`Offering` model/source/export write-up; this document's job is only
+to record that the registration mechanism is the existing curated-
+roster pattern, not a new one. No live scraper — the six volunteer org
+profiles (Fleet, SDZWA, Birch, the Nat, ILACSD, San Diego River Park
+Foundation) and seven free/Title I school-program records are
+hand-curated directly into `offerings.toml`, mirroring `places.toml`'s
+own "committed curation, not a live acquisition source" precedent
+exactly (issue 35's original instruction against live directory
+scrapers, still in force).
+
+**Issue 33 part 1 (educator-PD program pages) — this document's main
+`registry/sources/` catalog, the existing `program_page`/
+`program_page_multi`/`program_listing` `adapter_type` family.** UCSD
+CREATE, SD Science Project, UCSD Math Project, Code.org regional
+partner, CSTA-SD, SDSU CRMSE, Fleet educator workshops, Salk STEM
+Educators Summit, and Zoo teacher workshops each register with
+`config.opportunity_type = "Professional Development / Conferences"`
+and `config.program_kind = "program"` — the identical operator-curated-
+override mechanism sprint 029's competition batch used, now selecting
+`adapters/program_llm.py`'s new `profile="pd"` (see `adapters/
+DESIGN.md`'s own sprint 030 Revision) rather than any new registry
+field. Each source's `adapter_type` (`program_page` for a single-event
+page, `program_page_multi` for one page/list holding several session
+dates inline, `program_listing` for a listing whose cards link to N
+detail pages, `config.link_selector` set where a listing's cards aren't
+`EVENT_PATH_RE`-shaped) is chosen per-source at registration time from
+each page's actual observed markup — decided during ticket execution's
+required live-verification step, not assumed at planning time, per
+sprint 029's own hard-learned lesson (this document's Revision above).
+
+**SDCOE's own PD registration system, k12oms.org, is confirmed
+already excluded** — `registry/DO_NOT_SCRAPE.md`'s existing "SDCOE OMS
+(k12oms.org)" entry (`robots Disallow: /`, per issue 36's 2026-08-30
+research) already covers it; this sprint adds no new
+`DO_NOT_SCRAPE.md` entry, it only re-confirms the existing one applies
+here too before any educator-PD source is registered.
+
+**Issue 14's dated volunteer-event sources (UCSD Localist's
+Volunteer event type, Coastkeeper TEC, Surfrider SD Google Calendar,
+ILACSD) are a verification pass, not a new registration effort.**
+Per issue 14's own 2026-08-30 research conclusion, these already flow
+through the normal `Opportunity` pipeline (`localist`/`tec_rest`/
+`ical`/`generic_html` adapters, whichever each one already uses) once
+registered — this sprint confirms each one's current `enabled`
+state/live yield is still correct (re-verifying, not re-registering;
+see this sprint's sprint.md ticket for whichever of these turn out to
+need a config fix versus already being fine). Strategy A (scraping
+third-party volunteer-aggregator platforms) remains excluded per
+`DO_NOT_SCRAPE.md`'s existing Idealist/VolunteerMatch, ActivityHero, and
+JustServe/HandsOn San Diego/Points of Light entries — no change to that
+file from this sprint either.
 
 ## Revision (2026-09-02 — sprint 029 competition-genre extraction fix)
 
```
