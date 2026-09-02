---
source_file: export-DESIGN.md
source_hash: 2518b77b3d4b270edc6d355c753422c5f1a2201a75316854957ce6d01a868b1c
---
# Diff: export-DESIGN.md

Comparison of the sprint overlay copy of `export-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- export-DESIGN.md (pristine)
+++ export-DESIGN.md (current)
@@ -115,7 +115,14 @@
   so a new field would have no real producer yet; reusing `end` is not speculative — it
   extends an already-shipped convention (sprint 006) to one more already-shipped type
   value rather than inventing a second one. See `normalize/DESIGN.md`'s matching sprint
-  015 addendum.
+  015 addendum. **(Sprint 027, issue 28 item 4)** `DEADLINE_FIRST_TYPES` gains a third
+  member, `"Funding Opportunities"` — the SD Foundation Community Scholarship's own
+  type — so this exact currency/sort rule now also applies to it, with **zero code
+  change in this module**: `is_current_or_upcoming`/`_export_sort_key` already branch on
+  `opportunity_type in DEADLINE_FIRST_TYPES`, a set they import from `normalize.run`
+  rather than hardcoding, which is precisely what makes a third member a
+  `normalize/run.py`-only change. See `normalize/DESIGN.md`'s sprint 027 addendum for
+  why the set gained a member instead of `Opportunity` gaining a `kind` field.
 - **`export/` re-derives nothing.** No field mapping, no taxonomy, no dedup. Its inputs
   arrive finished from `normalize/`. Adding a derivation here would apply it after
   deduplication chose a winner, silently diverging from what the rest of the pipeline
```
