---
source_file: design.md
source_hash: 3921bc05aec26828a5c65d50d9621828747a8f5d9ef26e0f6daf87269434ad87
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -200,6 +200,26 @@
 (sprint 019 converted `site/` to a build-time-only checkout of the separate
 `stem-ecosystem` repository).
 
+**Sprint 031 addition — four new ATS adapters and `fetch/`'s first non-GET verb.** Two
+independent, code-light extensions of the ATS-family pattern sprint 006 established
+(`greenhouse`/`lever`), no pipeline stage or dependency-direction change: (1) four new
+`adapter_type` values, `workday`, `neogov`, `smartrecruiters`, `workable` — a seventeenth
+through twentieth adapter type — each running its postings through the unchanged
+`adapters/ats_filters.py` classifier before emitting `kind="internship"` `Event`s, the
+identical downstream path (`enrich/`'s bypass, `normalize/`'s collapse/dedup bypass,
+`export/`'s `Work-based Learning` current/upcoming rule) sprint 006 built and sprint 027
+generalized, unchanged by this sprint; (2) `fetch/fetcher.py`'s `Fetcher` Protocol gains a
+`post()` method alongside `get()` — this codebase's first non-GET network call — because
+Workday's public job-search API requires a POST body with no GET-based equivalent. This is
+new composition on an existing edge (`adapters` → `fetch`), not a new subsystem or a
+changed dependency direction: `fetch/` remains the bottom of the dependency graph, and
+every existing `Fetcher` implementation/test double that never calls `post()` is
+unaffected. See `partner_scrape/adapters/DESIGN.md`'s and `partner_scrape/fetch/DESIGN.md`'s
+own sprint 031 sections for the full write-up, including the Design Rationale for
+extending the Protocol rather than having the Workday adapter open its own `urllib` call,
+and for why POST responses are deliberately not cached on disk at this sprint's traffic
+volume.
+
 ## 4. Subsystem map
 
 The source root itself carries an overview doc; each subsystem carries its own, co-located
@@ -208,12 +228,15 @@
 - [`partner_scrape/DESIGN.md`](../../partner_scrape/DESIGN.md) — **root overview**: the
   run end to end, the four top-level modules, and the shared conventions.
 - [`partner_scrape/adapters/DESIGN.md`](../../partner_scrape/adapters/DESIGN.md) —
-  sixteen per-vendor `discover → fetch → extract` strategies behind a one-line
+  twenty per-vendor `discover → fetch → extract` strategies behind a one-line
   dispatch table (sprint 027 adds the LLM-extraction `program_page`/
   `program_listing`/`program_page_multi` trio — see that doc's own sprint 027 section
   and its ticket 006 exception-cycle Revision note; sprint 028 adds the
   `activenet_camps`/`campbrain` camp-platform pair and an HTML-reduction step shared by
-  the whole LLM-extraction family — see that doc's own sprint 028 section).
+  the whole LLM-extraction family — see that doc's own sprint 028 section; sprint 031
+  adds four more ATS adapters — `workday`, `neogov`, `smartrecruiters`, `workable` —
+  extending sprint 006's `greenhouse`/`lever` family, see that doc's own sprint 031
+  section).
 - [`partner_scrape/directory/DESIGN.md`](../../partner_scrape/directory/DESIGN.md) —
   (sprint 018) a second, independent pipeline alongside `teams/`: curated, undated
   standing-entity directories — Places, Clubs, and (sprint 030) Offerings (volunteer
```
