---
source_file: registry-DESIGN.md
source_hash: 2c87de1b592fb6650eda8b221e3458c82d36a15a68223de7b782e04f224efb03
---
# Diff: registry-DESIGN.md

Comparison of the sprint overlay copy of `registry-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- registry-DESIGN.md (pristine)
+++ registry-DESIGN.md (current)
@@ -1,6 +1,6 @@
 # Registry
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable
 
 ---
 
@@ -14,13 +14,21 @@
 loaders that turn them into typed objects, and it owns the *physical separation* between
 catalogs that must never be confused with one another.
 
+**(Sprint 014)** This sprint is squarely an exercise of that "onboarding is a data
+edit" design point, at higher volume than any prior sprint: roughly 33 existing
+`sources/` entries get a triage disposition (fixed / re-typed / flagged headless /
+disabled-with-reason), two known mis-registrations are corrected
+(`sd-river-park-foundation`'s `adapter_type`, `sandiego-gov`'s `org_name`/`site_url`
+mismatch), and roughly 20 new entries are added against already-existing adapters. No
+schema, loader, or catalog-separation change is needed for any of it — see §6.
+
 ## 2. Orientation
 
 Four data directories, three schema/loader pairs:
 
 | Directory | Schema | Loader | Contents |
 |---|---|---|---|
-| `sources/` | `schema.SourceConfig` | `loader.load_sources` / `load_active_sources` | 101 organizations |
+| `sources/` | `schema.SourceConfig` | `loader.load_sources` / `load_active_sources` | ~101 organizations before sprint 014; ~120 after |
 | `hubs/` | `hub_schema.HubConfig` | `hub_schema.load_hubs` | curated lead-generation hubs |
 | `ads/` | `export.ads.AdConfig` | `export.ads.load_ad_configs` | hand-authored ad slots |
 | `candidates/` | `candidates.CandidateStub` | `candidates.list_candidates` | discovered orgs awaiting human promotion |
@@ -141,4 +149,17 @@
 - Promotion from a candidate stub to a live source is entirely manual and undocumented
   beyond the stub's own fields — there is no checklist for choosing an `adapter_type`.
 - Disabled sources accumulate. Nothing reports how many entries are `enabled = false` or
-  why.
+  why. **(Sprint 014, partial)** The "or why" half is now addressed by convention, not
+  tooling: this sprint's triage ticket disables sources with an inline reason comment
+  (`enabled = false  # disabled: <reason>`, e.g. `olivewood-gardens.toml`'s existing
+  precedent), so a human reading the file always sees why. The "how many, in aggregate"
+  half — a report or count across the catalog — is still unbuilt; this remains a real
+  gap for a future sprint, not resolved here.
+- **(Sprint 014)** `source_id` correctness (the constraint in §3: it's the join key for
+  four separate subsystems) was violated in the wild before this sprint —
+  `sandiego-gov.toml`'s `org_name` named an entirely different organization than its
+  `site_url`. This sprint's triage ticket corrects it, but the registry itself still has
+  no automated check that `org_name` and `site_url` (or any other field pair) are
+  mutually consistent — the §3 "no schema validation for the contents of `config`"
+  limitation extends to this kind of cross-field consistency too, and a similar
+  mismatch could recur silently for any other source.
```
