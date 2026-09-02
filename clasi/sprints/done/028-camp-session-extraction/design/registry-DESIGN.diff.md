---
source_file: registry-DESIGN.md
source_hash: 87683327f400cfce4ec10870ea311aabe71dd637c39a6c615b18ff62e1c7272f
---
# Diff: registry-DESIGN.md

Comparison of the sprint overlay copy of `registry-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- registry-DESIGN.md (pristine)
+++ registry-DESIGN.md (current)
@@ -82,6 +82,11 @@
 this module has no dependency on. This sprint is a pure exercise of "onboarding is a
 data edit," at the granularity of ~18 new source files (roughly 15 individual program
 pages, 2 listing sources, 1 scholarship).
+
+**(Sprint 028)** Two more `adapter_type` values, `activenet_camps` and `campbrain`, plus
+roughly 15-20 new `program_page_multi` camp-marketing-page sources — see §5b's own sprint
+028 addendum for the full data-shape write-up. Same "no registry code change" story as
+sprint 027's addition above: every new value is dispatched entirely inside `adapters/`.
 
 ## 2. Orientation
 
@@ -226,6 +231,27 @@
 every key above: no `schema.py`/`loader.py` change, dispatch and interpretation happen
 entirely inside `adapters/`/`discovery/`, which this module still has no dependency on.
 
+**(Sprint 028)** Two more `adapter_type` values, `activenet_camps` and `campbrain`
+(`adapters/DESIGN.md`'s own sprint 028 section) — the two camp-registration platform
+adapters. Both reuse `program_page`'s existing `config.url`/`config.program_kind`/
+`config.opportunity_type` shape verbatim (one registered per-organization listing
+endpoint, `program_kind = "program"`, `opportunity_type = "Camps"`); no new conventional
+`config` key was needed for either, since a camp-platform source is, from this module's
+point of view, indistinguishable in shape from a `program_page`/`program_page_multi`
+source — same untyped `config` dict, same "no schema validation for the contents of
+`config`" limitation (§6) applying identically. Every marketing-page camp source
+registered this sprint (San Diego Zoo's per-program pages, Living Coast, Coastal Roots
+Farm, Elementary Institute of Science, SD Model Railroad Museum, Camp Invention, CMOD,
+Southwestern College Y.E.S., Birch's newsroom page, Fleet) is a plain `program_page_multi`
+entry with `config.opportunity_type = "Camps"` — zero registry code change, a pure
+"onboarding is a data edit" exercise at the granularity of roughly 15-20 new source files
+(San Diego Zoo and Camp Invention each contribute multiple individually-registered
+per-program pages). Camp Galileo SD is deliberately not one of them (commercial-chain
+scope exclusion — see `sprint.md`'s Scope and `adapters/DESIGN.md`'s Design Rationale);
+Air & Space Museum and Helen Woodward are registered only as `activenet_camps` sources,
+not also as `program_page_multi` marketing-page sources, for the same
+dual-registration-avoidance reason.
+
 ## 6. Open Questions / Known Limitations
 
 - There is no schema validation for the contents of `config`, so a typo in a key an
@@ -252,3 +278,11 @@
   mutually consistent — the §3 "no schema validation for the contents of `config`"
   limitation extends to this kind of cross-field consistency too, and a similar
   mismatch could recur silently for any other source.
+- **(Sprint 028)** Nothing in `registry/` itself prevents a future edit from
+  re-introducing the exact dual-registration this sprint deliberately avoided by
+  convention (Air & Space Museum/Helen Woodward registered only via `activenet_camps`,
+  never also via a `program_page_multi` marketing-page entry) — the same "no cross-field/
+  cross-file consistency check" gap the sprint 014 entry above already names, applied to
+  "the same organization registered under two source files." Not solved here; caught only
+  by author discipline and code review, same as the sprint 027 COSMOS/OPTIMUS/ENLACE risk
+  this mirrors.
```
