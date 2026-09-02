---
source_file: design.md
source_hash: 30f87444b6b50126bd5c6adbbc2e398156f57e6d3ae5d600f3d6d9f2963a1c48
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -177,6 +177,29 @@
 one-way dependency direction (`adapters` → `discovery`/`extract`/`fetch`/`registry`,
 `partner_scrape/DESIGN.md`'s §5 convention, unchanged).
 
+**Sprint 030 addition — a third `directory/` standing-entity type, `Offering`, plus a
+third `adapters/` program-page extraction profile.** Two independent, code-light
+extensions of already-established patterns, no new pipeline stage or dependency-
+direction change: (1) `directory/` (sprint 018's second, independent pipeline — see
+that sprint's own note below) gains `Offering`, an undated standing-entity record
+serving both a volunteer-org-profile use case and a free/Title-I-school-program use
+case with one shape, extending the exact `Place`/`Club` generalization that module
+already exists to house (see `partner_scrape/directory/DESIGN.md`'s own sprint 030
+section); (2) `adapters/program_llm.py` gains a third `ProgramLLMClient` extraction
+profile, `profile="pd"`, for educator-PD workshop/conference pages, alongside the
+`"program"` and sprint-029 `"competition"` profiles (see
+`partner_scrape/adapters/DESIGN.md`'s own sprint 030 section). Neither touches the
+pipeline diagram in §3 above or changes which subsystem depends on which — `directory/`
+remains structurally disjoint from `adapters/`/`enrich/`/`normalize/`/`pipeline.run()`
+exactly as sprint 018 established, and the `adapters/` change is contained entirely
+inside that package's existing one-way dependency direction, matching sprint 014's own
+"no diagram needed" precedent for a same-shape, no-new-composition addition. **Scope
+note, not an architecture change:** this sprint's `offerings.json` export is this
+repo's data contract only — see `partner_scrape/directory/DESIGN.md`'s sprint 030
+Migration Concerns for why rendering it as a site page is out of this repo's scope
+(sprint 019 converted `site/` to a build-time-only checkout of the separate
+`stem-ecosystem` repository).
+
 ## 4. Subsystem map
 
 The source root itself carries an overview doc; each subsystem carries its own, co-located
@@ -191,6 +214,15 @@
   and its ticket 006 exception-cycle Revision note; sprint 028 adds the
   `activenet_camps`/`campbrain` camp-platform pair and an HTML-reduction step shared by
   the whole LLM-extraction family — see that doc's own sprint 028 section).
+- [`partner_scrape/directory/DESIGN.md`](../../partner_scrape/directory/DESIGN.md) —
+  (sprint 018) a second, independent pipeline alongside `teams/`: curated, undated
+  standing-entity directories — Places, Clubs, and (sprint 030) Offerings (volunteer
+  org profiles and free/Title-I school programs) — published as `places.json`/
+  `clubs.json`/`offerings.json`. Never touches `adapters/`, `enrich/`,
+  `normalize.run()`, or `pipeline.run()`, the same "standing entity, not a dated
+  event" boundary `teams/` established. *(This bullet was missing from this document
+  before sprint 030 — an unrelated pre-existing gap from sprint 018, fixed here since
+  this sprint substantially extends the subsystem it should have already linked.)*
 - [`partner_scrape/discovery/DESIGN.md`](../../partner_scrape/discovery/DESIGN.md) —
   resolving sources into fetchable URLs; plus hub scanning for organization leads,
   structurally firewalled from the event pipeline.
```
