# Observability

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## 1. Purpose

`observability/` answers "did this run actually work?" for each of ~100 sources
individually. A scrape that completes successfully while three sources silently stopped
yielding anything is the characteristic failure of this system — nothing raises, the
export is written, and the site quietly loses those organizations. This subsystem owns
per-source yield accounting, run-over-run comparison, and the alerting thresholds that
turn a silent regression into a visible one. It is a subsystem because that accounting
must be computable from data alone, with no knowledge of the pipeline that produced it,
so it can be tested hermetically.

## 2. Orientation

Four modules in a clean data-in / data-out chain:

- `reporter.py` · `YieldReporter` — the collector. It satisfies `pipeline.Reporter`
  structurally: `record_source(source_id, org_name, events, error=None)` is called once
  per source (on both the success and failure branches of `pipeline.run()`'s per-source
  try/except), and `record_opportunities(opportunities)` once after normalization.
  `.report(previous_snapshot)` produces the finished `YieldReport`.
- `yield_report.py` — the pure computation. `compute_yield_report(source_records,
  opportunities, previous_snapshot)` turns raw per-source `Event` lists plus the final
  `Opportunity` list into one `SourceYield` per source: `found`, `dated`, `new`,
  `dropped`, `slugs`, `previous_found`, `delta`, `error`, `zero_yield`, `cliff`.
- `render.py` · `render_text(report) -> str` — plain-text rendering for the console.
- `snapshot.py` · `load_snapshot(path)` / `save_snapshot(path, report)` — persistence of
  the run's per-source slug sets and counts to `yield-history.json`, which becomes the
  next run's `previous_snapshot`.

`cli.py` wires it: load the previous snapshot, construct a `YieldReporter`, pass it as
`pipeline.run(reporter=...)`, then print the rendered report and save the new snapshot.

## 3. Constraints and Invariants

- **This package imports nothing from `pipeline.py` — not even `pipeline.Reporter`.**
  `YieldReporter` satisfies the Protocol structurally. Importing it would create an
  `observability → pipeline` edge running backwards against the codebase's dependency
  direction, and would make this package unloadable without pulling in the entire
  pipeline import graph. The same precedent holds for `enrich.enricher.LLMEnricher` and
  `pipeline.Enricher`.
- **It also imports nothing from `cli.py`, `export/`, `registry/`, or `adapters/`.**
  Opportunities arrive as `list[Any]` and are read via `getattr(..., "slug")` /
  `getattr(..., "sources")`, mirroring `pipeline.Reporter.record_opportunities`'s own
  signature — so this package stays decoupled from every module `pipeline.py` is itself
  decoupled from.
- **`yield_report.py` performs no I/O and holds no state.** It is data in, data out. That
  is precisely what makes threshold logic testable without constructing a pipeline run.
- **`found`/`dated` are derived here, not computed by `pipeline.py`.** The pipeline hands
  over raw `Event` lists; counting is this subsystem's job. Moving counting upstream would
  put reporting logic in the orchestrator, which is exactly what its "must not become a
  god component" constraint forbids.
- **A reporter failure must never break a run.** `pipeline.run()` defaults to a no-op
  reporter and the CLI's `--no-report` restores that. Observability is a lens on the run,
  not a participant in it.
- **`--dry-run` writes no snapshot.** `yield-history.json` is site-dir-adjacent output and
  follows the same "nothing written" promise as the export.
- **Deliberate non-goal — no remediation.** This subsystem reports; it does not disable
  sources, retry them, or alter the export. Acting on an alert is a human decision.

## 4. Design

**The four counts, and why each exists.**
`found` is every `Event` the adapter returned; `dated` is the subset with a usable date
(the ones that can survive `export/`'s current-or-upcoming filter); `new` and `dropped`
are computed against the previous snapshot's per-source slug set, from the *final*
`Opportunity` list's `.sources` attribution. Together they localize a regression:
`found` collapsing means discovery or fetching broke; `found` steady but `dated`
collapsing means extraction broke; both steady but `dropped` spiking means the relevance
gate or the date filter changed behavior.

**Two alert conditions.** `zero_yield` — a source that returned nothing at all — and
`cliff` — a source whose `found` dropped by more than `CLIFF_DROP_THRESHOLD` (50%)
against the previous run. Zero-yield catches outright breakage; the cliff threshold
catches the more insidious case of a site changing its markup so that most, but not all,
records stop parsing. `SourceYield.has_alert()` and `YieldReport.alerts()` expose them.

**Snapshot content.** The snapshot persists per-source counts *and* the set of
opportunity slugs that source contributed. Slugs are what make `new`/`dropped` meaningful
— a count comparison alone cannot distinguish "five records replaced five others" from
"nothing changed".

**Why attribution comes from `Opportunity.sources`.** After cross-source dedup a single
`Opportunity` may be credited to several organizations. `sources` is the union
`normalize/dedup.py` builds, and it is the only place that attribution survives; the raw
`Event` list cannot supply it because dedup has already happened.

**Errors are carried, not raised.** `SourceRecord.error` holds the exception
`pipeline.run()` caught for a failed source, so the report distinguishes "this source
raised" from "this source returned zero records", which are very different diagnoses.

## 5. Interfaces

### Exposes
- **`YieldReporter()`** with **`.record_source(source_id, org_name, events,
  error=None)`**, **`.record_opportunities(opportunities)`**, and
  **`.report(previous_snapshot=None, *, now=None) -> YieldReport`**. Structurally
  satisfies `pipeline.Reporter`; the first two methods are what `pipeline.run()` calls.
- **`compute_yield_report(source_records, opportunities, previous_snapshot=None, *,
  now=None) -> YieldReport`** — the pure computation, usable standalone.
- **`SourceRecord`**, **`SourceYield`** (with `.has_alert()`), **`YieldReport`** (with
  `.alerts()`), **`CLIFF_DROP_THRESHOLD`** (0.5).
- **`render_text(report) -> str`** — console rendering, alert lines first.
- **`load_snapshot(path) -> dict`** (returns `{}` for a missing file) and
  **`save_snapshot(path, report)`**.

### Consumes
- **`Event` (from `model.py`)** — read-only, for counting and date presence. See the root
  `partner_scrape/DESIGN.md`.
- Opportunities are consumed *structurally* as `list[Any]` via `getattr` — deliberately
  not an import of `normalize.run.Opportunity`. See the constraint above.

## 6. Open Questions / Known Limitations

- The report is printed to the console and the snapshot is written to a JSON file. There
  is no alerting channel — a zero-yield source in a scheduled run is only noticed by
  someone reading the workflow log.
- Thresholds are global constants. A source that legitimately fluctuates (a seasonal camp
  provider) alerts as a cliff every off-season, and there is no per-source override.
- The snapshot holds one previous run, not a history, so a slow multi-run decay never
  trips the cliff threshold.
- Nothing tracks enrichment quality — how many records fell back to keyword taxonomy
  because the LLM call failed — even though that is a directly observable degradation.
- `yield-history.json` lives beside the site's data files, which makes it easy to find
  but means it is per-checkout state that `export/mirror.py` deliberately refuses to copy.
