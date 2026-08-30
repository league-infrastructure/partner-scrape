---
source_file: normalize-DESIGN.md
source_hash: 9ad0a4c618ba416b2fdad4e4c28044de3ced0124f0fa223dc2291de2ee4005c3
---
# Diff: normalize-DESIGN.md

Comparison of the sprint overlay copy of `normalize-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- normalize-DESIGN.md (pristine)
+++ normalize-DESIGN.md (current)
@@ -1,6 +1,6 @@
 # Normalize
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable
 
 ---
 
@@ -14,6 +14,15 @@
 `Event.field_provenance`'s per-field confidence, which no other stage has access to and
 which does not survive the mapping to `Opportunity`. It also owns the `Opportunity` shape
 itself — the boundary type between the scraper's world and the site's schema.
+
+**(Sprint 014)** No code in this subsystem changes this sprint. It is included in this
+sprint's design overlay because two of its existing, already-tested behaviors are
+exercised at meaningfully higher volume and get an explicit sprint-time decision
+recorded against them, not a new mechanism: the cross-source dedup that §3's
+collapse-then-dedup ordering constraint governs, now matched against a park-wide
+institutional calendar (Balboa Park) for the first time; and the no-partner-match display
+path in `partners.py`, now hit by roughly 20 newly-registered sources, several without a
+`partners.json` entry. See §6.
 
 ## 2. Orientation
 
@@ -228,7 +237,24 @@
 
 - Cross-source identity is `normalized_title + date + normalized_venue`. Two orgs
   describing the same event with materially different titles will not merge; two genuinely
-  different events sharing a title, date, and venue will.
+  different events sharing a title, date, and venue will. **(Sprint 014)** Registering
+  Balboa Park's park-wide TEC calendar alongside the individual institutions it covers
+  (Fleet, Nat, and others already scraped directly) exercises exactly this limitation for
+  the first time at meaningful scale: an event Balboa Park titles generically (e.g. "Member
+  Preview Night") and the hosting institution titles specifically will not merge, and will
+  publish as two `Opportunity` records for one real event. This is accepted, not fixed, this
+  sprint — no new dedup mechanism is introduced; a stronger cross-source identity (e.g.
+  venue-plus-date-only, or a fuzzy title match) is deferred to a future sprint if the
+  duplication turns out to be material in practice.
+- **(Sprint 014)** `partners.py`'s `find_partner` no-match behavior (keep the org name,
+  leave `partner_id` unset — already the tested, non-fatal path) is now exercised by
+  design, not just as an edge case: several of this sprint's ~20 newly-registered sources
+  (issue 25) have no corresponding `partners.json` entry, and expanding the roster to
+  cover them is explicitly out of this sprint's scope (issue 32's job). Those
+  organizations' `Opportunity` records display with a bare org name and no logo/partner
+  link until issue 32 (or a later sprint) adds them to the roster. This is a deliberate,
+  accepted product decision for this sprint, not a defect — see `sprint.md`'s Scope and
+  SUC-007.
 - The timezone convention is "naive San Diego wall clock", enforced by coercion rather
   than by carrying a real timezone through the pipeline. **(Resolved, sprint 012)**
   The export-time offset is no longer a hard-coded literal — `_iso()` resolves it per
```
