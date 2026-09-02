---
source_file: observability-DESIGN.md
source_hash: ed4e6a6f36de09366f5761892faa0e7360caaf5f04bba6bdacd03ea85d58bf57
---
# Diff: observability-DESIGN.md

Comparison of the sprint overlay copy of `observability-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- observability-DESIGN.md (pristine)
+++ observability-DESIGN.md (current)
@@ -14,6 +14,15 @@
 turn a silent regression into a visible one. It is a subsystem because that accounting
 must be computable from data alone, with no knowledge of the pipeline that produced it,
 so it can be tested hermetically.
+
+**(Sprint 033)** This subsystem gains a second accounting dimension alongside per-source
+yield: per-*region* opportunity counts (South Bay, East County, North County Coastal,
+North County Inland, Central San Diego, unclassified), answering "is the site's regional
+coverage silently regressing" the same way per-source yield already answers "is this
+source silently breaking" — issue 34's own framing ("regressions are visible ... the same
+way per-source yield is"). No new module, no new mechanism: `RegionYield` mirrors
+`SourceYield`'s shape, computed by the same `yield_report.py`, persisted by the same
+`snapshot.py`, rendered by the same `render.py`. See §4.
 
 ## 2. Orientation
 
@@ -35,6 +44,13 @@
 
 `cli.py` wires it: load the previous snapshot, construct a `YieldReporter`, pass it as
 `pipeline.run(reporter=...)`, then print the rendered report and save the new snapshot.
+
+**(Sprint 033)** `compute_yield_report` additionally derives one `RegionYield` per known
+region (plus one `"unclassified"` bucket) from the final `Opportunity` list's `.region`
+attribute (`getattr`, no new import — same duck-typing convention as `.slug`/`.sources`),
+and `YieldReport` gains a `.regions: list[RegionYield]` field alongside its existing
+`.sources`. `render_text` gains a "Regional coverage" section. `snapshot.py` persists this
+run's region counts under one reserved key so the next run can compute a delta — see §4.
 
 ## 3. Constraints and Invariants
 
@@ -94,6 +110,32 @@
 `pipeline.run()` caught for a failed source, so the report distinguishes "this source
 raised" from "this source returned zero records", which are very different diagnoses.
 
+**(Sprint 033) Why `RegionYield` mirrors `SourceYield` instead of a new, lighter shape.**
+Region counting is genuinely simpler than source yield — there is no adapter-level "raw
+`Event`s" to distinguish from "dated", only a count of the final, already-deduplicated
+`Opportunity` list bucketed by `.region`, so `RegionYield` has no `found`/`dated` split,
+just `count`, `previous_count`, `delta`, and a `zero` flag (a region that had opportunities
+last run and has none now — the direct analogue of `zero_yield`, at region granularity).
+Reusing `SourceYield`'s field *names* where the concept is the same (`previous_count`/
+`delta` mirror `previous_found`/`delta`) rather than inventing parallel vocabulary keeps
+`render.py`'s two sections reading the same way. Rejected alternative: computing region
+counts as a side-table outside `YieldReport` (e.g. a bare `dict[str, int]`) — rejected
+because it would have no delta/first-run-baseline handling of its own, duplicating
+`_compute_source_yield`'s already-solved "no previous entry means first-ever run, not a
+regression" logic a second time with a lesser shape.
+
+**(Sprint 033) Why the reserved snapshot key is `"__regions__"`, not a nested
+restructuring.** `snapshot.py`'s persisted JSON is a flat object keyed by `source_id`.
+Nesting the whole file into `{"sources": {...}, "regions": {...}}` would be a breaking
+shape change for any snapshot file already on disk from a pre-sprint-033 run (an in-flight
+production `yield-history.json`) — `load_snapshot`'s current flat-dict reads would need to
+change too. Adding one more flat top-level key, `"__regions__"` (double-underscore-wrapped
+so it cannot collide with a real `source_id`, which is always a bare TOML-filename-derived
+slug with no underscore-wrapping convention), keeps every existing per-source entry's
+lookup (`previous_snapshot.get(record.source_id)`) unchanged and lets an old snapshot file
+with no such key read as "no previous region baseline" — the same, already-tested
+first-run behavior an unseen source already gets.
+
 ## 5. Interfaces
 
 ### Exposes
@@ -105,15 +147,24 @@
   now=None) -> YieldReport`** — the pure computation, usable standalone.
 - **`SourceRecord`**, **`SourceYield`** (with `.has_alert()`), **`YieldReport`** (with
   `.alerts()`), **`CLIFF_DROP_THRESHOLD`** (0.5).
-- **`render_text(report) -> str`** — console rendering, alert lines first.
+- **`RegionYield`** (sprint 033) — `region`, `count`, `previous_count`, `delta`, `zero`.
+  **`YieldReport.regions -> list[RegionYield]`** (sprint 033), alongside the existing
+  `.sources`.
+- **`render_text(report) -> str`** — console rendering, alert lines first; sprint 033 adds
+  a "Regional coverage" section after the per-source detail.
 - **`load_snapshot(path) -> dict`** (returns `{}` for a missing file) and
-  **`save_snapshot(path, report)`**.
+  **`save_snapshot(path, report)`** — sprint 033: `save_snapshot` additionally writes this
+  run's region counts under the reserved `"__regions__"` key; `load_snapshot` is unchanged
+  (it already returns whatever top-level keys are present).
 
 ### Consumes
 - **`Event` (from `model.py`)** — read-only, for counting and date presence. See the root
   `partner_scrape/DESIGN.md`.
 - Opportunities are consumed *structurally* as `list[Any]` via `getattr` — deliberately
-  not an import of `normalize.run.Opportunity`. See the constraint above.
+  not an import of `normalize.run.Opportunity`. See the constraint above. **(Sprint 033)**
+  Region counting reads one more attribute the same way: `getattr(opportunity, "region",
+  "")` — still no import of `normalize.run.Opportunity`, still decoupled per the
+  constraint above.
 
 ## 6. Open Questions / Known Limitations
 
@@ -128,3 +179,15 @@
   because the LLM call failed — even though that is a directly observable degradation.
 - `yield-history.json` lives beside the site's data files, which makes it easy to find
   but means it is per-checkout state that `export/mirror.py` deliberately refuses to copy.
+- **(Sprint 033)** No `cliff`-style percentage-drop alert exists for regions, only a
+  `zero` flag (a region that had opportunities last run and has none this run). Regional
+  counts are small (single digits for several regions per issue 34's own numbers), where a
+  percentage-drop threshold is noisy — a drop from 2 to 1 is a 50% "cliff" by the
+  per-source formula but not a meaningful regression signal at this scale. Not built this
+  sprint; worth revisiting if regional counts grow enough for a percentage threshold to
+  become meaningful.
+- **(Sprint 033)** The `"__regions__"` reserved key is a convention, not schema-enforced —
+  nothing prevents a hypothetical future source literally named `__regions__` from
+  colliding with it. Accepted risk: source IDs are derived from registry TOML filenames
+  (`registry/schema.py`), and no existing or plausible future filename uses this
+  convention.
```
