---
id: '002'
title: Yield observability package
status: done
use-cases:
- SUC-017
- SUC-018
depends-on:
- '001'
github-issue: ''
issue: 08-source-yield-observability.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Yield observability package

## Description

New package `partner_scrape/observability/`, implementing issue 08's
per-source yield computation, alerting, and rendering on top of ticket
001's `Reporter` hook:

- `yield_report.py` — `SourceYield` (one source's this-run `found`,
  `dated`, `new`, `dropped` counts, delta vs. previous run, and alert
  state) and `YieldReport` (all sources' `SourceYield`s + a generated
  timestamp). `found = len(events)`, `dated = ` count of `events` with
  `event.start is not None` — both derived here from the raw `Event`
  list `record_source` receives, not computed by `pipeline.py`. `new`/
  `dropped` are computed from the final `Opportunity` list's `.sources`
  field (matched by slug against the previous snapshot's per-source slug
  sets) — the post-dedup, post-enrichment, site-visible units, which is
  a different (and equally real) signal than raw per-source `found`.
  Alert logic: zero-yield fires when the previous snapshot's `found` for
  that source was `> 0` and this run's is `0`; cliff fires on a
  configurable proportional drop (default: `> 50%`) with previous
  `found > 0`. Neither fires when the source has no previous-snapshot
  entry (first-ever run for that source) — an expected baseline, not an
  error.
- `render.py` — `render_text(report) -> str`: a per-source line (found,
  delta, dated/new/dropped, alert marker) plus alert lines listed
  *before* the per-source detail, so an operator scanning a CI job log
  sees any zero-yield/cliff sources without reading every line.
- `snapshot.py` — `load_snapshot(path) -> dict` (empty/baseline dict,
  not an error, when `path` doesn't exist — the expected "first run
  ever" shape) and `save_snapshot(path, report)` (writes each source's
  latest `found` count and opportunity-slug set as JSON — the minimum
  needed for next run's delta, not an append-only history).
- `reporter.py` — `YieldReporter`, the concrete class passed as
  `pipeline.run(reporter=...)`. Collects each `record_source(...)` call
  and the one `record_opportunities(...)` call, then exposes
  `.report(previous_snapshot) -> YieldReport` for the caller (ticket 003's
  `cli.py`) to invoke once `run()` returns. Satisfies ticket 001's
  `Reporter` protocol **structurally** — it must not import
  `partner_scrape.pipeline` at all, matching the verified precedent that
  `enrich.enricher.LLMEnricher` satisfies `pipeline.Enricher` the same
  way, with zero import-time coupling.

The whole package must be pure/hermetic: no network, no dependency on
`cli.py`, `export/`, `registry/`, or `adapters/`. `snapshot.py`'s I/O
takes a plain `path` parameter (no `Config`/env-var coupling), so tests
use `tmp_path` directly.

## Acceptance Criteria

- [x] `SourceYield`/`YieldReport` computed correctly for found/dated/new/
      dropped against a known previous snapshot.
- [x] Zero-yield alert fires exactly when previous `found > 0` and this
      run's `found == 0`; does not fire when there is no previous
      snapshot entry for that source.
- [x] Cliff alert fires on a drop past the configured threshold and does
      not fire below it; threshold is a named constant, not a magic
      number inline.
- [x] A source reported with `error` set (adapter raised) is
      distinguishable in the resulting `SourceYield` from a source that
      ran cleanly and genuinely found zero events.
- [x] `render_text(report)` lists any zero-yield/cliff alerts before the
      per-source detail lines.
- [x] `load_snapshot(path)` on a missing file returns an empty baseline,
      not an exception; `save_snapshot`/`load_snapshot` round-trip
      correctly through a `tmp_path` file.
- [x] `YieldReporter` contains no `import partner_scrape.pipeline`
      (or `from partner_scrape import pipeline`) anywhere in the
      `observability` package — verified by grep, not just review.
- [x] `observability/` has no import of `cli`, `export`, `registry`, or
      `adapters`.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite) — this ticket
  adds a new package with no existing call sites yet, so the bar is "no
  import-time or collection-time breakage."
- **New tests to write**:
  - `tests/test_observability_yield_report.py` — pure unit tests
    (`tmp_path` only where a path is genuinely needed) for found/dated/
    new/dropped computation against a known previous snapshot; zero-yield
    alert firing and not firing; cliff alert firing at/above threshold
    and not below it; a first-ever run (no previous snapshot) producing
    no alerts for any source.
  - `tests/test_observability_render.py` — `render_text()` alert-before-
    detail ordering, and a no-alert run's plain per-source output.
  - `tests/test_observability_snapshot.py` — missing-file baseline,
    save/load round-trip via `tmp_path`.
  - Extend `tests/test_pipeline_e2e.py` (building on ticket 001's spy-
    Reporter test) with a real `YieldReporter`: run `pipeline.run()`
    twice over the same `e2e_registry` fixtures, second run with one
    source's fixture `Fetcher` responses swapped to empty/removed, and
    assert the second run's `YieldReport` flags that source zero-yield.
- **Verification command**: `uv run pytest`
