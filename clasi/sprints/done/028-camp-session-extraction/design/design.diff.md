---
source_file: design.md
source_hash: e767c8d21c87c062313cb64f83f939fc187f016c91f695f60757b21709f649cb
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -119,6 +119,64 @@
 `partner_scrape/normalize/DESIGN.md`'s own sprint 014 sections, and this sprint's
 `sprint.md` Architecture section for why no component/dependency diagram is included.
 
+**Sprint 028 addition — camp session extraction, plus an HTML-reduction step for the
+sprint 027 LLM-extraction family.** Two independent changes inside `adapters/`, no new
+pipeline stage: (1) closing issue 36, the `program_page`/`program_listing`/
+`program_page_multi` family now reduces a fetched page's HTML to bounded plain text
+(`extract.reduce_html_to_text()`, new — see `partner_scrape/extract/DESIGN.md`'s own
+sprint 028 section) before every LLM call, fixing the `sd-foundation-community-
+scholarship` and UCSD-card failures sprint 027 hit; (2) two new platform adapter types,
+`activenet_camps` and `campbrain`, extract dated, priced camp-session records from two
+camp-registration platforms, reusing the sprint 027 mechanism's own intermediate shape
+(`ProgramExtractionResult`) rather than adding a camp-specific one. See
+`partner_scrape/adapters/DESIGN.md`'s own sprint 028 section for the full write-up,
+including the Design Rationale for reusing that shape, deferring the third
+issue-29-listed platform (Pike13) to a follow-up issue, and excluding the one
+commercial-chain camp (Camp Galileo SD) that issue 29 otherwise lists alongside its
+verified nonprofit/institutional marketing-page targets.
+
+This sprint touches enough of `adapters/`'s own internal shape (a new dependency on
+`extract/`, plus two new adapter types) to warrant a component diagram — unlike sprint
+014 above, this is new composition, not independent same-shape edits:
+
+```mermaid
+graph LR
+    subgraph programFamily["adapters/ -- LLM-extraction family"]
+        PP["program_page.py<br/>(ProgramPageAdapter,<br/>ProgramListingAdapter,<br/>ProgramPageMultiAdapter)"]
+        AC["activenet_camps.py<br/>(new, sprint 028)"]
+        CB["campbrain.py<br/>(new, sprint 028)"]
+        PL["program_llm.py<br/>(ProgramLLMClient,<br/>ProgramExtractionResult)"]
+        PC["program_cache.py<br/>(ProgramExtractionCache)"]
+    end
+    EX["extract/<br/>(reduce_html_to_text --<br/>new export, sprint 028)"]
+    FE["fetch/<br/>(Fetcher)"]
+    RG["registry/<br/>(SourceConfig)"]
+    MD["model.py<br/>(Event)"]
+
+    PP -->|"reduce raw.body<br/>before hash/LLM call (NEW)"| EX
+    PP -->|"extract_program /<br/>extract_programs"| PL
+    PP -->|"lookup / store"| PC
+    AC -->|"deterministic parse,<br/>or LLM fallback via"| PL
+    AC -->|"reduce fallback body"| EX
+    CB -->|"deterministic parse,<br/>or LLM fallback via"| PL
+    CB -->|"reduce fallback body"| EX
+    PP -->|"fetcher.get()"| FE
+    AC -->|"fetcher.get()"| FE
+    CB -->|"fetcher.get()"| FE
+    PP -->|"reads config"| RG
+    AC -->|"reads config"| RG
+    CB -->|"reads config"| RG
+    PL -->|"emits, via _map_result_to_event"| MD
+```
+
+The one new edge that did not exist before this sprint is `program_page.py → extract/`
+(bold in the write-up above, though Mermaid itself doesn't distinguish it visually) —
+every other edge either already existed (sprint 027) or is the same shape repeated for
+the two new adapter modules. No edge points backward into `pipeline.py`, `enrich/`, or
+`normalize/` — this sprint's changes are fully contained inside `adapters/`'s existing
+one-way dependency direction (`adapters` → `discovery`/`extract`/`fetch`/`registry`,
+`partner_scrape/DESIGN.md`'s §5 convention, unchanged).
+
 ## 4. Subsystem map
 
 The source root itself carries an overview doc; each subsystem carries its own, co-located
@@ -127,10 +185,12 @@
 - [`partner_scrape/DESIGN.md`](../../partner_scrape/DESIGN.md) — **root overview**: the
   run end to end, the four top-level modules, and the shared conventions.
 - [`partner_scrape/adapters/DESIGN.md`](../../partner_scrape/adapters/DESIGN.md) —
-  fourteen per-vendor `discover → fetch → extract` strategies behind a one-line
+  sixteen per-vendor `discover → fetch → extract` strategies behind a one-line
   dispatch table (sprint 027 adds the LLM-extraction `program_page`/
   `program_listing`/`program_page_multi` trio — see that doc's own sprint 027 section
-  and its ticket 006 exception-cycle Revision note).
+  and its ticket 006 exception-cycle Revision note; sprint 028 adds the
+  `activenet_camps`/`campbrain` camp-platform pair and an HTML-reduction step shared by
+  the whole LLM-extraction family — see that doc's own sprint 028 section).
 - [`partner_scrape/discovery/DESIGN.md`](../../partner_scrape/discovery/DESIGN.md) —
   resolving sources into fetchable URLs; plus hub scanning for organization leads,
   structurally firewalled from the event pipeline.
@@ -139,7 +199,8 @@
 - [`partner_scrape/export/DESIGN.md`](../../partner_scrape/export/DESIGN.md) — every write
   across the repo boundary, plus image self-hosting and multi-checkout mirroring.
 - [`partner_scrape/extract/DESIGN.md`](../../partner_scrape/extract/DESIGN.md) — the
-  confidence-ranked extraction ladder for arbitrary HTML.
+  confidence-ranked extraction ladder for arbitrary HTML, plus (sprint 028) a
+  bounded HTML-to-text reduction function shared by the LLM-extraction adapter family.
 - [`partner_scrape/fetch/DESIGN.md`](../../partner_scrape/fetch/DESIGN.md) — the only
   network access in the system: robots, throttling, caching, optional headless browser.
 - [`partner_scrape/normalize/DESIGN.md`](../../partner_scrape/normalize/DESIGN.md) —
@@ -257,3 +318,12 @@
   confirmation the existing plain `ical` adapter can consume their feeds unchanged. If
   it cannot, they need either adapter work or are dropped; that decision is explicitly
   out of this sprint's scope.
+- (Sprint 028) An in-season-only camp source (Fleet) registered year-round legitimately
+  yields zero records off-season — indistinguishable from a broken source in
+  `observability/`'s yield report. Accepted, not solved: see
+  `partner_scrape/adapters/DESIGN.md`'s sprint 028 Design Rationale for why a
+  seasonal-recheck subsystem was deliberately not built.
+- (Sprint 028) Pike13 (issue 29's third-priority camp-platform adapter) is deferred to a
+  follow-up issue, carrying forward an unresolved question of its own: whether it
+  supersedes gaps in the already-shipped `leaguesync` adapter for the League's own camps.
+  See `partner_scrape/adapters/DESIGN.md`'s sprint 028 Design Rationale.
```
