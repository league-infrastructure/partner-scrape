---
source_file: normalize-DESIGN.md
source_hash: 327f35a4ee1b5837c7d1619ae8c60b65ea75709faaf7d7878584fbb4b1cdfbdb
---
# Diff: normalize-DESIGN.md

Comparison of the sprint overlay copy of `normalize-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- normalize-DESIGN.md (pristine)
+++ normalize-DESIGN.md (current)
@@ -68,6 +68,20 @@
   Lever) emit aware ones. Mixing them makes `min()`/`max()` in collapse and dedup raise
   and crashes the entire run. Coercing in one place means no single adapter's
   tz-awareness can break the pipeline; removing it reintroduces a whole-run crash.
+- **(Sprint 012) A naive datetime's export offset is resolved per-date, not
+  hard-coded.** `_iso()` previously appended a constant `_TZ_OFFSET = "-07:00"`
+  (Pacific Daylight Time) to every naive datetime, which was wrong for the
+  roughly four months a year (early November - mid-March) San Diego is on
+  Pacific Standard Time (`-08:00`) — a real correctness bug, not a display
+  nicety, since the offset is part of the published ISO 8601 string every
+  downstream consumer (the site's calendar view, any external agent reading
+  `public/data/`) parses. `_iso()` now localizes each naive datetime through
+  `zoneinfo.ZoneInfo("America/Los_Angeles")` and reads the resulting offset
+  back off it, so `-07:00`/`-08:00` falls out of which side of the DST
+  boundary the date lands on, correct for any date including future years
+  (IANA's tzdata, not a hand-maintained table, tracks DST rule changes). An
+  already-aware datetime's own offset is still left untouched — this rule is
+  unchanged.
 - **`kind="internship"` events bypass both collapse and dedup.** Both stages' identity
   assumptions (same title in the same window is a recurrence; same title+date+venue is
   the same event) are wrong for job postings, where near-identical titles are genuinely
@@ -137,6 +151,30 @@
 fallback keeps defaulting ambiguous titles to `"Out-of-school Programs"`, which is the
 safer failure mode during an LLM outage.
 
+**The DST-transition fold convention (sprint 012).** `zoneinfo`-based
+localization is unambiguous everywhere except the two hours a year the
+local clock itself is ambiguous or nonexistent: the repeated 1am-2am
+hour when clocks fall back in November, and the skipped 2am-3am hour
+when clocks spring forward in March. Python's `fold` attribute
+disambiguates the first case (`fold=0` is the pre-transition,
+earlier-UTC occurrence; `fold=1` is the post-transition,
+later-UTC occurrence) and `zoneinfo` already applies a documented
+convention for the second (a nonexistent local time is treated as if
+the transition had not yet happened, i.e. resolved to the pre-transition
+offset). `_iso()` adopts `fold`'s own default (`fold=0`, since no
+adapter this project has ever produces a `datetime` with `fold` set
+explicitly) rather than inventing a second convention on top of it —
+every naive datetime in this pipeline already carries `fold=0` by
+construction (the dataclass default), so the *practical* behavior is:
+an ambiguous November timestamp resolves to its earlier (Daylight Time,
+`-07:00`) occurrence, and a nonexistent March timestamp resolves to the
+pre-transition (`-08:00`) offset `zoneinfo` itself picks. Both are
+edge cases affecting at most one calendar hour, twice a year, for
+events whose adapters extract only a date+time, never a UTC instant —
+the residual ambiguity (which of two real clock readings a "1:30am"
+event meant) is a source-data limitation this fix does not attempt to
+resolve beyond picking one documented, tested, consistent answer.
+
 **Why `Opportunity.slug`'s algorithm changed (sprint 009).** The previous algorithm
 (`org[:40]_title[:60]_date`, all truncated) existed only to be unique within one export
 snapshot, and `export/writer.py` already carries a defensive collision pass because
@@ -192,8 +230,13 @@
   describing the same event with materially different titles will not merge; two genuinely
   different events sharing a title, date, and venue will.
 - The timezone convention is "naive San Diego wall clock", enforced by coercion rather
-  than by carrying a real timezone. `_TZ_OFFSET = "-07:00"` is a hard-coded literal, so
-  exports are wrong across the DST boundary.
+  than by carrying a real timezone through the pipeline. **(Resolved, sprint 012)**
+  The export-time offset is no longer a hard-coded literal — `_iso()` resolves it per
+  datetime via `zoneinfo.ZoneInfo("America/Los_Angeles")`, correct across the DST
+  boundary in both directions (see Design, above, for the fold convention on the two
+  transition-hour edge cases). The underlying convention itself (coerce to naive at
+  ingestion, localize only at export) is unchanged — only the previously-wrong constant
+  is fixed.
 - Keyword taxonomy rules were ported from an exploration script and spot-checked, not
   validated against a labelled set. Where the LLM and the keyword rules disagree, no
   measurement exists of which is right.
```
