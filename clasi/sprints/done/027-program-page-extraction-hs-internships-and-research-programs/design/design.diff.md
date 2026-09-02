---
source_file: design.md
source_hash: c884887c75cb14a68cd4fdd76183c5bded93f8820c25b98ed40c844353120abf
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -126,8 +126,11 @@
 
 - [`partner_scrape/DESIGN.md`](../../partner_scrape/DESIGN.md) — **root overview**: the
   run end to end, the four top-level modules, and the shared conventions.
-- [`partner_scrape/adapters/DESIGN.md`](../../partner_scrape/adapters/DESIGN.md) — eleven
-  per-vendor `discover → fetch → extract` strategies behind a one-line dispatch table.
+- [`partner_scrape/adapters/DESIGN.md`](../../partner_scrape/adapters/DESIGN.md) —
+  fourteen per-vendor `discover → fetch → extract` strategies behind a one-line
+  dispatch table (sprint 027 adds the LLM-extraction `program_page`/
+  `program_listing`/`program_page_multi` trio — see that doc's own sprint 027 section
+  and its ticket 006 exception-cycle Revision note).
 - [`partner_scrape/discovery/DESIGN.md`](../../partner_scrape/discovery/DESIGN.md) —
   resolving sources into fetchable URLs; plus hub scanning for organization leads,
   structurally firewalled from the event pipeline.
```
