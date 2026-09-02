---
source_file: enrich-DESIGN.md
source_hash: d4296182afc414f275f9b22174ca62442a69365950bb1703dc68f1531fa97769
---
# Diff: enrich-DESIGN.md

Comparison of the sprint overlay copy of `enrich-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- enrich-DESIGN.md (pristine)
+++ enrich-DESIGN.md (current)
@@ -38,6 +38,15 @@
 `../stem-ecosystem` repo carries an identical hardcoded facet list in its own
 copy of that component and needs the same one-line edit on its own schedule —
 out of this ticket's write scope (a different repository).
+
+**(Sprint 027)** The pass-1 bypass (§2, §3) generalizes from a single hardcoded
+`event.kind == "internship"` check to `event.kind in model.PROGRAM_EXTRACTION_KINDS`
+(`{"internship", "program"}`) — a `kind="program"` `Event`, emitted by the new
+program-page extraction adapters (`adapters/DESIGN.md`), gets exactly the same
+zero-cost, zero-mutation skip an internship already gets. No other behavior in this
+module changes: the relevance-gate exemption below (`event.trusted`) is untouched and,
+for a bypassed `program`/`internship` `Event`, is simply never reached (the bypass
+happens before the gate runs at all).
 
 ## 2. Orientation
 
@@ -65,9 +74,10 @@
 
 `LLMEnricher.enrich(events)` runs in four passes:
 
-1. **Sequential** over the input in order: `kind="internship"` events bypass everything;
-   the rest get a cache lookup. Hits are applied immediately (no LLM call). Misses are
-   collected.
+1. **Sequential** over the input in order: `kind in PROGRAM_EXTRACTION_KINDS` events
+   (sprint 027: `"internship"` or `"program"`; previously `"internship"` only) bypass
+   everything; the rest get a cache lookup. Hits are applied immediately (no LLM call).
+   Misses are collected.
 2. **Concurrent**: every miss's `llm_client.enrich_event()` is submitted to a
    `ThreadPoolExecutor(max_workers=8)`.
 3. **Sequential apply**, back on the main thread, iterating misses in their *original*
@@ -103,16 +113,23 @@
   implementation would produce.** Concurrency changes only how fast the calls happen.
   `max_workers=1` must behave exactly like the original sequential code. Any change that
   makes output depend on completion order breaks reproducibility of a run.
-- **`kind="internship"` events bypass this subsystem entirely** — no cache lookup, no LLM
-  call, no field mutation. An internship arrives already classified and gated
-  deterministically by `adapters/ats_filters.py`, which is the correct classifier for
-  work-based-learning postings; this module's relevance prompt judges *learning
-  opportunities* (events and programs), a different content shape, so routing internships
-  through it at all — regardless of audience scope — would be applying the wrong
-  classifier, not a risk of misjudging one. (Before sprint 014 this bullet's stated risk
-  was specifically that the old K-12-only framing would misjudge job-posting text as
-  "adult-only" and drop it; that specific risk is moot now that the gate accepts any
-  audience, but the bypass itself is unchanged and independently justified.)
+- **`kind in PROGRAM_EXTRACTION_KINDS` events bypass this subsystem entirely** — no cache
+  lookup, no LLM call, no field mutation. An internship arrives already classified and
+  gated deterministically by `adapters/ats_filters.py`; **(sprint 027)** a `program`-kind
+  event arrives already classified by the new program-page LLM extraction call
+  (`adapters/DESIGN.md`) — a different, dedicated call against a program-specific schema,
+  not this module's generic recovery/classification prompt. Either way, this module's
+  relevance prompt judges *learning opportunities* (events and programs) from
+  partially-extracted, ambiguous source text; both bypassed kinds arrive already fully
+  and deliberately classified by a more specific upstream process, so routing them
+  through the generic prompt a second time would not just be redundant LLM spend — it
+  would let a generic classification silently overwrite a more specific one via the same
+  `Event.set()` field_provenance mechanism `normalize/`'s field_provenance-presence
+  precedence otherwise relies on to prefer the *first* real classification, not the
+  *last* one. (Before sprint 014 this bullet's stated risk was specifically that the old
+  K-12-only framing would misjudge job-posting text as "adult-only" and drop it; that
+  specific risk is moot now that the gate accepts any audience, but the bypass itself is
+  unchanged and independently justified.)
 - **`event.trusted` overrides the relevance gate.** First-party curated sources (the
   League's own classes via `adapters/leaguesync.py`) are still enriched and classified
   normally but must never be gate-dropped. Removing this makes the site's own operator
@@ -290,3 +307,14 @@
   vocabulary includes `"Funding Opportunities"`, which the keyword fallback still does not
   produce (see `normalize/DESIGN.md`) because a keyword rule for it was already shown to
   false-positive on unrelated text.
+- **(Sprint 027)** `PROGRAM_EXTRACTION_KINDS` is the explicit reuse surface named for
+  sprints 029 (competitions) and 030 (educator programs): a future source registered
+  with `program_kind = "program"` gets this module's full bypass with zero further
+  change here. Nothing currently prevents a future sprint from registering a `program`
+  kind whose content is *not* actually curated/pre-classified the way this sprint's
+  program pages are (e.g. a lower-trust or partially-automated source) and silently
+  losing the relevance gate and generic classification it might have needed — the
+  bypass is keyed on `kind` alone, not on any independent trust signal. Not a problem
+  for this sprint's own sources (each is a hand-registered, individually reviewed page
+  or listing), but worth a future sprint re-checking before extending `kind="program"`
+  to a less-curated source class.
```
