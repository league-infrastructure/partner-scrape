---
source_file: design.md
source_hash: 06871e4eccda3fb2505f49f54524f38ea5d6b56dfb9e39600ca9f03e2e3c78c3
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -4,7 +4,7 @@
 ---
 # partner-scrape — System Design
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable
 
 This is the top-level design document for the `partner-scrape` repository. It covers
 system-wide context, the subsystem map, and the global conventions every subsystem
@@ -15,7 +15,10 @@
 ## 1. What this project is
 
 `partner-scrape` is the data engine behind **sdstemecosystem.org**, the San Diego STEM
-Ecosystem's directory of STEM learning opportunities for K-12 youth.
+Ecosystem's directory of STEM learning opportunities for **learners of all ages**
+(sprint 014 widened this from an earlier K-12-only framing to match the site's own
+stated audience and its `Adult` age facet — see §3's sprint 014 note and
+`partner_scrape/enrich/DESIGN.md`).
 
 It is one half of a two-repository architecture:
 
@@ -97,6 +100,24 @@
 unchanged; the new modules do not import it. See
 `partner_scrape/teams/DESIGN.md`'s own sprint 013 section for the full
 write-up.
+
+**Sprint 014 addition — gate widening, ops reactivation, and registry growth,
+no pipeline stage or dependency change.** Four independent, code-light changes:
+`enrich/`'s relevance gate now judges "STEM learning opportunity for any audience"
+rather than K-12-only, with a new `prompt_version` cache-key component
+(`partner_scrape/enrich/DESIGN.md`) forcing exactly one re-evaluation per
+previously-cached event; the already-built headless-fetch path (`fetch/headless.py`,
+`pipeline.py`'s `fetch_strategy` wiring, both unchanged since sprint 003/005) gets
+turned on in more environments and flagged for more sources purely via registry data
+and CI/dependency configuration; roughly 33 previously zero-adapter-yield sources in
+`registry/sources/` get a triage disposition, including two corrected
+mis-registrations; and roughly 20 new sources are registered against the three
+existing structured-API adapters (`tec_rest`, `ical`, `localist`) with zero new
+adapter code. None of this moves the pipeline diagram in §3 above, changes which
+subsystem depends on which, or changes the `Opportunity` data model — see
+`partner_scrape/enrich/DESIGN.md`, `partner_scrape/registry/DESIGN.md`, and
+`partner_scrape/normalize/DESIGN.md`'s own sprint 014 sections, and this sprint's
+`sprint.md` Architecture section for why no component/dependency diagram is included.
 
 ## 4. Subsystem map
 
@@ -181,6 +202,12 @@
   publishing last run's data?) is undecided.
 - The site data contract is unversioned and unvalidated in either direction.
 - Yield alerts have no delivery channel beyond console output in the scheduled run's log.
+  **(Sprint 014)** This gap is more consequential now that the weekly cron is actually
+  reactivated (§3's sprint 014 addition): a zero-yield or cliff alert on an unattended
+  Monday run is visible only in that run's GitHub Actions job summary, which nobody is
+  guaranteed to open. Not solved this sprint — `observability/DESIGN.md`'s own Open
+  Questions already named this gap; sprint 014 makes it a live operational risk rather
+  than a theoretical one, and is not a scope change to `observability/` itself.
 - A circular import between `adapters.listing_html` and `discovery.listing` is worked
   around by import ordering rather than fixed.
 - **(Resolved, sprint 012)** DST is now handled: `normalize/run.py` resolves each
@@ -212,3 +239,18 @@
   silently drops that team's previously-scraped sponsors rather than
   preserving them. Not solved; see `partner_scrape/teams/DESIGN.md`'s Open
   Questions.
+- (Sprint 014) Registering Balboa Park's park-wide calendar alongside the individual
+  institutions it already covers exercises `normalize/`'s known "different titles for
+  the same event never merge" limitation for the first time at meaningful scale; some
+  duplicate publication is accepted, not fixed, this sprint. See
+  `partner_scrape/normalize/DESIGN.md`'s sprint 014 Open Questions entry.
+- (Sprint 014) `registry/`'s "no schema validation for `config`" limitation extends to
+  cross-field consistency generally — `sandiego-gov.toml`'s `org_name`/`site_url`
+  mismatch (corrected this sprint) was exactly this kind of silent error, and nothing
+  added this sprint prevents a similar one from recurring for any other source. See
+  `partner_scrape/registry/DESIGN.md`'s sprint 014 Open Questions entries.
+- (Sprint 014) LibCal (Carlsbad, Escondido) and the NPS events API (Cabrillo National
+  Monument) were evaluated but not registered — deferred, not engineered, pending
+  confirmation the existing plain `ical` adapter can consume their feeds unchanged. If
+  it cannot, they need either adapter work or are dropped; that decision is explicitly
+  out of this sprint's scope.
```
