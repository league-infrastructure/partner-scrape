---
source_file: design.md
source_hash: d33ce153e6dabef7aa5a01d6d77a04293574aef6a4fb1c5a3c10a7d610f72ee4
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -219,6 +219,30 @@
 extending the Protocol rather than having the Workday adapter open its own `urllib` call,
 and for why POST responses are deliberately not cached on disk at this sprint's traffic
 volume.
+
+**Sprint 033 addition — audience and equity coverage measurement, no pipeline stage or
+dependency-direction change.** Three independent, code-light changes inside already-
+existing modules: (1) `normalize/taxonomy.py` gains `derive_specific_attention()`, which
+finally populates the site schema's own long-stubbed `Opportunity.specific_attention`
+field (documented since before this repo's own git history began tracking it, hardcoded to
+`[]` since sprint 015) with values already named in the site's own vocabulary
+(`"Programs in Spanish"`, `"Programs for students with disabilities"`) — a content change
+to an existing exported field, not a schema change; (2) `normalize/taxonomy.py` also gains
+`derive_region()` and `Opportunity` gains one new internal (non-site-schema) field,
+`region`, feeding a new per-region count in `observability/`'s yield report and in
+`export/`'s `scrape-meta.json`, closing issue 34's "no measurement exists for regional
+coverage" gap the same way per-source yield already exists; (3) a registry data addition/
+fix (no new adapter code) for whichever of the three known accessibility offerings (Fleet
+Accessibility Mornings, the Nat's ASD Mornings, CMOD Sensory Friendly Mornings) is not
+currently surfacing. LLM translation of bilingual-flagged descriptions (issue 34 item b) is
+explicitly deferred to a follow-up issue — see this sprint's `sprint.md` Design Rationale.
+No `PROMPT_VERSION` bump; nothing in this sprint touches `enrich/` or any LLM call. A
+component diagram is omitted: every changed data flow travels through the pipeline's
+already-existing `normalize/run.py` → `observability/` and `normalize/run.py` → `export/`
+Opportunity-list edges, unchanged in direction or presence — matching sprint 014's own
+"same-shape, no new composition" no-diagram precedent. See
+`partner_scrape/normalize/DESIGN.md`, `partner_scrape/observability/DESIGN.md`, and
+`partner_scrape/export/DESIGN.md`'s own sprint 033 sections for the full write-up.
 
 ## 4. Subsystem map
 
@@ -382,3 +406,16 @@
   follow-up issue, carrying forward an unresolved question of its own: whether it
   supersedes gaps in the already-shipped `leaguesync` adapter for the League's own camps.
   See `partner_scrape/adapters/DESIGN.md`'s sprint 028 Design Rationale.
+- (Sprint 033) LLM translation of bilingual-flagged records' descriptions (issue 34 item
+  b) is deferred to a follow-up issue, not built this sprint — see `sprint.md`'s Design
+  Rationale for the full tradeoff (a `PROMPT_VERSION`-forced full re-enrichment vs. a new,
+  separately-cached LLM-call path outside `enrich/`'s existing schema, both real scope
+  deserving their own ticket). Whether/how `stem-ecosystem` ever exposes a filter UI for
+  the now-populated `specific_attention` field (already wired into the DOM via
+  `data-attention`, per the sprint's own finding) is that repo's own follow-up to verify,
+  not decided here. El Trompo's binational-listing question (issue 34 item c) remains an
+  unresolved stakeholder decision, unactioned by any ticket.
+- (Sprint 033) The `region` classification's keyword vocabulary is spot-checked, not
+  validated against a labelled address set — see `partner_scrape/normalize/DESIGN.md`'s
+  sprint 033 Open Questions for the unclassified-bucket caveat and the rejected
+  ZIP/lat-long-geocoding alternative.
```
