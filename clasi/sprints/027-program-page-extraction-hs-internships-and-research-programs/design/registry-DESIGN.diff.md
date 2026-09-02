---
source_file: registry-DESIGN.md
source_hash: 8a9c0de01ee04243866aa739858decc3d8a862d76f41e177083a9801c2e978d9
---
# Diff: registry-DESIGN.md

Comparison of the sprint overlay copy of `registry-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- registry-DESIGN.md (pristine)
+++ registry-DESIGN.md (current)
@@ -68,6 +68,20 @@
 "malformed or missing-required-field file is logged and skipped" isolation
 covers a bad *file*; a missing *credential* is `pipeline.run()`'s existing
 per-source isolation instead, unaffected by this file being present).
+
+**(Sprint 027)** Two new `adapter_type` values, `program_page` and `program_listing`
+(`adapters/DESIGN.md`), are registered exactly like any other source — a new
+`sources/*.toml` file with `adapter_type = "program_page"` (or `"program_listing"`),
+`config.url` (or `config.listing_urls`/`config.site_url`), and a new conventional
+`config.program_kind` key (`"internship"` or `"program"`) the adapter reads to set
+`Event.kind`. No registry code changes: `schema.py`/`loader.py` already accept any
+string `adapter_type` value without validating it against a known set (§3's "no schema
+validation for the contents of `config`" limitation, unchanged, extends to
+`program_kind` the same way it already covers every other adapter-specific config key)
+— dispatch to the right `Adapter` implementation happens entirely in `adapters/`, which
+this module has no dependency on. This sprint is a pure exercise of "onboarding is a
+data edit," at the granularity of ~18 new source files (roughly 15 individual program
+pages, 2 listing sources, 1 scholarship).
 
 ## 2. Orientation
 
@@ -194,6 +208,15 @@
 contents of `config`" limitation applies identically to `taxonomy_defaults`: a typo'd key
 (e.g. `elegibility`) is silently ignored, not an error.
 
+**(Sprint 027)** `config.program_kind` (`"internship"` | `"program"`) and, for
+`program_listing` sources, `config.listing_urls`/`config.site_url` (the identical shape
+`listing_html` already uses) are new conventional `config` keys, read only by the two
+new adapters — same untyped-dict status as every other adapter-specific `config` key.
+`config.opportunity_type` is an additional, optional override for a `program_kind =
+"program"` source whose type is known a priori (e.g. the SD Foundation Scholarship's
+`"Funding Opportunities"`) rather than left to the LLM extraction call's own
+classification.
+
 ## 6. Open Questions / Known Limitations
 
 - There is no schema validation for the contents of `config`, so a typo in a key an
```
