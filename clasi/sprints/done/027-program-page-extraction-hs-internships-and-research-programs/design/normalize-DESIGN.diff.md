---
source_file: normalize-DESIGN.md
source_hash: 336bdac611d43761296acdf028de8452c84612f9bffc32457d1e19eed8350b7c
---
# Diff: normalize-DESIGN.md

Comparison of the sprint overlay copy of `normalize-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- normalize-DESIGN.md (pristine)
+++ normalize-DESIGN.md (current)
@@ -24,6 +24,14 @@
 path in `partners.py`, now hit by roughly 20 newly-registered sources, several without a
 `partners.json` entry. See §6.
 
+**(Sprint 027)** No new mechanism is added to this subsystem's collapse/dedup/mapping
+pipeline — every change generalizes an existing, already-tested special case (the
+`kind="internship"` bypass; the `WORK_BASED_LEARNING_TYPE`/`DEADLINE_FIRST_TYPES`
+availability-and-currency rule) to also cover the new `kind="program"` records the
+program-page extraction adapters emit (`adapters/DESIGN.md`), plus one small, additive
+data-flow completion (`eligibility` gains a second, per-record source). See §4 for the
+four specific changes and their rationale.
+
 ## 2. Orientation
 
 One entry point: `run.run(events, partners_path, source_org_names=None,
@@ -31,7 +39,9 @@
 executes in a fixed order:
 
 1. **Coerce datetimes.** Any timezone-aware `start`/`end` is made naive, in one place.
-2. **Split internships out.** `kind="internship"` events bypass both dedup stages.
+2. **Split curated-kind events out.** `kind in PROGRAM_EXTRACTION_KINDS` events
+   (sprint 027: `"internship"` or `"program"`; previously `"internship"` only) bypass
+   both dedup stages.
 3. **`collapse_recurring(events, today)`** (`collapse.py`) — group by
    `(source_id, normalized_title)` and fold each group into one `Instance` spanning
    first-to-last date, carrying a repeat count.
@@ -92,10 +102,12 @@
   (IANA's tzdata, not a hand-maintained table, tracks DST rule changes). An
   already-aware datetime's own offset is still left untouched — this rule is
   unchanged.
-- **`kind="internship"` events bypass both collapse and dedup.** Both stages' identity
+- **`kind in PROGRAM_EXTRACTION_KINDS` events bypass both collapse and dedup.**
+  (Sprint 027: generalized from `kind="internship"` alone.) Both stages' identity
   assumptions (same title in the same window is a recurrence; same title+date+venue is
   the same event) are wrong for job postings, where near-identical titles are genuinely
-  distinct openings.
+  distinct openings — and equally wrong for distinct programs that happen to share
+  similar titling (e.g. two different institutions' own "Summer Research Internship").
 - **Deliberate non-goal — no date filtering.** Whether a record is current or upcoming is
   `export/`'s judgment. `run()` returns everything that survived deduplication, dated or
   not.
@@ -109,6 +121,16 @@
   e.g. `--no-enrich`) — mirroring `cost_range`/`areas_of_interest`/`age_grade_level`/
   `time_of_day` exactly. Internships remain forced to `WORK_BASED_LEARNING_TYPE` by `kind`,
   unconditionally, checked before either branch.
+- **(Sprint 027) `eligibility` resolution now checks `Event.field_provenance` before
+  falling back to `taxonomy_defaults`.** `_to_opportunity()` prefers
+  `event.eligibility` when `"eligibility" in event.field_provenance` (set via
+  `Event.set(...)` by the program-page extraction adapters, one independent value per
+  record), else falls back to `source_taxonomy_defaults`' per-*source* default exactly
+  as sprint 015 ticket 008 shipped it — the same field_provenance-presence precedence
+  pattern already used for `areas_of_interest`/`age_grade_level`/`cost_range`/
+  `time_of_day`/`opportunity_type`, extended to a fifth field. This is additive: a
+  source relying purely on `taxonomy_defaults.eligibility` (every pre-sprint-027
+  source) is unaffected, since none of them ever call `Event.set("eligibility", ...)`.
 - **The event slug is now a cross-run identity, not a within-export display key**
   (sprint 009). Previously `Opportunity.slug` existed only to be unique *within one export
   snapshot* (`org[:40]_title[:60]_date`); it is now also how `export/partner_log.py`
@@ -170,6 +192,41 @@
 is not speculative in the same way: it extends sprint 006's already-shipped
 `WORK_BASED_LEARNING_TYPE` convention to one more already-shipped `opportunity_type`
 value (`"Competitions"`, added ticket 006 this sprint), not a new mechanism.
+
+**(Sprint 027, issue 28 item 4) `DEADLINE_FIRST_TYPES` gains a third member,
+`"Funding Opportunities"`, and `_internship_availability` gains a third text state.**
+Two independent, additive changes, both reusing the sprint 015 ticket 007 mechanism
+rather than inventing a new one:
+
+1. *`DEADLINE_FIRST_TYPES` extension.* The SD Foundation Community Scholarship
+   (`kind="program"`, `opportunity_type="Funding Opportunities"`, SUC-035) needs the
+   same date_end-based currency/sort/availability rule `Work-based Learning`/
+   `Competitions` already get. Rather than making `export/writer.py`'s currency check
+   `kind`-aware (which would require threading `Event.kind` through to `Opportunity` —
+   an `Opportunity` schema change this sprint's own Scope explicitly rules out, since
+   `Opportunity` has no `kind` field and none is added here), the mechanism stays
+   exactly as sprint 015 designed it: a global, `opportunity_type`-keyed policy. Adding
+   `"Funding Opportunities"` to it is scoped narrowly, the same way `"Competitions"` was
+   added before it — see this sprint's Design Rationale for why a blanket addition of
+   every `opportunity_type` this sprint's mechanism might ever use (e.g. `"Camps"`,
+   `"Out-of-school Programs"`) was rejected.
+2. *`_internship_availability`'s new "not yet open" branch.* Previously two states
+   ("Apply by <date>" when `event.end` is set, "Rolling — apply anytime" otherwise);
+   now three, checked in this order: if `event.start` is set and in the future, "Opens
+   ~<date>" (a program whose application window is known but not yet open); else the
+   original two-state logic, unchanged. This directly implements issue 28's closed-
+   window handling choice (see this sprint's Design Rationale for why "opens ~X" was
+   chosen over withholding a not-yet-open record entirely) — a **closed** window (an
+   `end` date already in the past) is handled by the pre-existing, unchanged
+   `is_current_or_upcoming()` currency filter in `export/writer.py`: it drops the
+   record from export outright, requiring no new state here at all. Only the
+   **not-yet-open** case is new, and it is display text only — `is_current_or_upcoming()`
+   already keeps such a record current (a future `date_start` easily clears the sprint
+   020 `_DEADLINE_FIRST_STALE_POSTING_DAYS` staleness check; see `export/DESIGN.md`).
+   This function now needs `today` to compare against `event.start`, threaded as a new
+   parameter into `_to_opportunity()` (previously `today`-unaware) from `run()`'s
+   existing `today = today or date.today()` — every existing caller/test that omits
+   `today` gets `date.today()`, unchanged from before this parameter existed.
 
 **Taxonomy is keyword rules, not ML.** `taxonomy.py` ports the pre-existing script's
 `AREA_KEYWORDS` / `AGE_KEYWORDS` / cost / time-of-day rules into pure functions.
@@ -285,8 +342,15 @@
   point. Mutates input `Event`s' `start`/`end` in place (tz coercion). Never raises for an
   unmatched partner or an undated record. `image_resolver=None` leaves `image_src` empty
   with zero network access. **(Sprint 015 ticket 008)** `source_taxonomy_defaults=None`
-  leaves `Opportunity.eligibility` at its `""` default for every record — see Design,
-  below.
+  leaves `Opportunity.eligibility` at its `""` default for every record unless an
+  `Event`-level value is set — see Design, below. **(Sprint 027)** `today` is now also
+  read by `_to_opportunity()`'s availability derivation (the new "Opens ~<date>" state),
+  not only by `collapse_recurring()` — no signature change, `run()` already accepted and
+  resolved `today` before this sprint.
+- **`model.PROGRAM_EXTRACTION_KINDS`** (sprint 027, re-exported here for convenience
+  alongside `WORK_BASED_LEARNING_TYPE`/`DEADLINE_FIRST_TYPES` since callers that need one
+  of these three constants typically need the others) — the shared `{"internship",
+  "program"}` kind set; see the root `partner_scrape/DESIGN.md`.
 - **`Opportunity`** — the boundary dataclass between scraper and site. `sources` is
   internal bookkeeping and is not part of the site schema.
 - **`taxonomy.derive_areas_of_interest`, `classify_opportunity_type`,
@@ -403,3 +467,15 @@
   `taxonomy_defaults.eligibility` via `source_taxonomy_defaults` (see Design, above). The
   other four fields' stub status is unchanged and is now an explicit, documented Out of
   Scope decision for this ticket, not an open question.
+- **(Sprint 027)** `Opportunity` still has no `kind` field, by deliberate scope decision
+  (this sprint's Scope explicitly excludes any `Opportunity`/taxonomy schema change).
+  This is what forces `DEADLINE_FIRST_TYPES` extension (rather than a `kind`-aware
+  export-layer check) as the mechanism for making a new curated record deadline-first at
+  the export layer (see Design, above) — every future `kind="program"` registration
+  (sprints 029/030) that needs export-layer deadline-first treatment will need its own
+  `opportunity_type` added to `DEADLINE_FIRST_TYPES`, the same way this sprint added
+  `"Funding Opportunities"`. If a future sprint needs many more such values, or values
+  that legitimately also appear on non-curated calendar records (making a blanket
+  `opportunity_type`-level addition unsafe — see Design's rejected-alternative note),
+  revisiting whether `Opportunity` should carry `kind` after all is the natural next
+  escalation; not needed at this sprint's scale (one new member).
```
