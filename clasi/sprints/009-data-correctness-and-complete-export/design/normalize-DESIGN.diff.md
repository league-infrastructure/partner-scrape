---
source_file: normalize-DESIGN.md
source_hash: 40ab0e221345c7f7697603b39762b13eb610f08edf6478f926e14dd22d451f5b
---
# Diff: normalize-DESIGN.md

Comparison of the sprint overlay copy of `normalize-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- normalize-DESIGN.md (pristine)
+++ normalize-DESIGN.md (current)
@@ -30,7 +30,10 @@
    best-scoring record, unioning the contributing `sources`.
 5. **Map each survivor to an `Opportunity`** — derive taxonomy tags (`taxonomy.py`), join
    against the site's partner roster (`partners.py`), build a slug, resolve an image
-   filename via the injected `image_resolver`.
+   filename via the injected `image_resolver`. Sprint 009: the slug is now a stable
+   cross-run identity (unique link, else title+date — see Design below), not a
+   within-this-export display key, because `export/partner_log.py` needs the same slug
+   across separate runs to recognize "same event" for its append-only log.
 
 `instance.py` holds `Instance` — internal bookkeeping (`event`, `sources`,
 `repeat_count`, `last_seen`) threaded between stages 3, 4 and 5. `taxonomy.py` is a pure
@@ -75,6 +78,19 @@
 - **`taxonomy.py` functions take plain text and values, never an `Event`.** Building the
   input blob from an `Event` is `run.py`'s job (`build_taxonomy_text`). Passing an `Event`
   in would couple a pure, trivially-testable rule layer to the record shape.
+- **`opportunity_type` selection follows the same LLM-wins-when-present pattern as every
+  other classification field** (sprint 009): `_to_opportunity` uses `event.opportunity_type`
+  when `"opportunity_type" in event.field_provenance` (enrichment ran, LLM or fallback),
+  else `classify_opportunity_type(event.title)` directly (enrichment skipped entirely,
+  e.g. `--no-enrich`) — mirroring `cost_range`/`areas_of_interest`/`age_grade_level`/
+  `time_of_day` exactly. Internships remain forced to `WORK_BASED_LEARNING_TYPE` by `kind`,
+  unconditionally, checked before either branch.
+- **The event slug is now a cross-run identity, not a within-export display key**
+  (sprint 009). Previously `Opportunity.slug` existed only to be unique *within one export
+  snapshot* (`org[:40]_title[:60]_date`); it is now also how `export/partner_log.py`
+  recognizes "the same event as last run" across separate pipeline invocations, so its
+  algorithm changed to the rule `export/DESIGN.md`'s `partner_log.py` needs — see Design
+  below. Both uses are still served by one field; there is no second slug concept.
 
 ## 4. Design
 
@@ -113,7 +129,30 @@
 `AREA_KEYWORDS` / `AGE_KEYWORDS` / cost / time-of-day rules into pure functions.
 `derive_time_of_day` is the one deliberate reimplementation: it reads `Event.start`'s
 real `datetime` rather than re-parsing a text time string. These rules are also the
-fail-open fallback `enrich/` uses when the LLM is unavailable.
+fail-open fallback `enrich/` uses when the LLM is unavailable. Sprint 009 adds
+`classify_opportunity_type` to that same fail-open role (see `enrich/DESIGN.md`) without
+changing its rules: no `"Funding Opportunities"` keyword rule is added, preserving the
+existing, deliberate false-positive rationale documented on
+`OPPORTUNITY_TYPE_KEYWORDS` — only the LLM path can produce that value; the keyword
+fallback keeps defaulting ambiguous titles to `"Out-of-school Programs"`, which is the
+safer failure mode during an LLM outage.
+
+**Why `Opportunity.slug`'s algorithm changed (sprint 009).** The previous algorithm
+(`org[:40]_title[:60]_date`, all truncated) existed only to be unique within one export
+snapshot, and `export/writer.py` already carries a defensive collision pass because
+truncation could still collide — a known, documented limitation. Issue 15 needs something
+stronger: an identity that survives *across* runs, so the new per-partner append-only log
+(`export/partner_log.py`) can tell "this is the same event, possibly updated" from "this
+is a new event." The new rule — `slugify(link)` when a per-event link exists, else
+`slugify(title) + date` — is a *different property* (cross-run stability, not just
+within-run uniqueness) than the old one, so reworking `Opportunity.slug` in place (rather
+than adding a second field) keeps exactly one slug concept instead of two. The org/partner
+prefix is dropped because slugs are now computed and stored *inside* a partner-scoped
+directory (`export/partner_log.py`'s `<partner-slug>/opportunities.jsonl`) — the partner
+is already implied by where the slug lives, so encoding it into the string itself would be
+redundant. `export/writer.py`'s existing `_dedupe_slugs` defensive pass is unchanged and
+still backstops the flat, cross-partner legacy export against the rarer
+title+date collision case.
 
 ## 5. Interfaces
 
@@ -128,7 +167,8 @@
 - **`taxonomy.derive_areas_of_interest`, `classify_opportunity_type`,
   `derive_age_grade_level`, `map_cost`, `derive_time_of_day`, `build_taxonomy_text`,
   `tag_by_keywords`** — pure classification rules, also consumed by `enrich/` as its
-  fallback.
+  fallback (sprint 009: `classify_opportunity_type` joins this fallback role, unchanged
+  rules).
 - **`partners.normalize_org_name`** — pure string normalization, also consumed by
   `discovery.hub_scan` for candidate dedup.
 - **`partners.load_partners` / `find_partner`** — read-only partner roster lookup.
@@ -136,6 +176,10 @@
 ### Consumes
 - **`Event`, `Provenance`, `normalize_title` (from `model.py`)** — the input record and
   its shared title-normalization rule. See the root `partner_scrape/DESIGN.md`.
+- **`model.slugify`** (sprint 009) — the shared text-to-slug primitive `_to_opportunity`
+  now uses to build `Opportunity.slug`, promoted to `model.py` because
+  `export/partner_log.py` needs the identical function for partner slugs. See the root
+  `partner_scrape/DESIGN.md`.
 - **The site's `partners.json`** — read-only, at a path the caller supplies (defaulting to
   `{site_dir}/src/data/partners.json`).
 - **An `image_resolver` callable** — supplied by `pipeline.run()`, backed by
@@ -153,9 +197,17 @@
 - Keyword taxonomy rules were ported from an exploration script and spot-checked, not
   validated against a labelled set. Where the LLM and the keyword rules disagree, no
   measurement exists of which is right.
-- Slug construction truncates, so distinct records can still collide;
-  `export/writer.py` carries a defensive uniqueness pass to catch that. The collision is
-  better fixed here.
+- **(Resolved, sprint 009, with a narrower residual case.)** Slug construction no longer
+  truncates and no longer collides within a partner's own directory except in one
+  documented edge case: the link-based branch assumes a per-event link is unique to that
+  event, not shared by several events on one listing page. If a source's adapter surfaces
+  the *listing* page URL as `link` for every event on it (rather than a per-event detail
+  URL), those events will collide on the same slug — matching issue 15's own "Known
+  trade-off" framing for the title+date fallback, now also possible (rarer) via the link
+  branch. Not solved speculatively this sprint; `export/DESIGN.md`'s Open Questions
+  tracks it as something to watch once real per-partner logs accumulate.
+  `export/writer.py`'s defensive `_dedupe_slugs` pass remains as the backstop for the flat,
+  cross-partner legacy export.
 - Several `Opportunity` fields the site schema defines (`specific_attention`,
   `financial_support`, `ngss_aligned`, the contact fields) are populated only from
   `taxonomy_defaults` in the registry, if at all. Nothing derives them.
```
