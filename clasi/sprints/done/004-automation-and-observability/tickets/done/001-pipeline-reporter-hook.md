---
id: '001'
title: Pipeline Reporter hook
status: done
use-cases:
- SUC-017
- SUC-018
depends-on: []
github-issue: ''
issue: 08-source-yield-observability.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Pipeline Reporter hook

## Description

Add a `Reporter` `Protocol` to `partner_scrape/pipeline.py`, structurally
parallel to the existing `Enricher` protocol, and one new optional
keyword parameter on `run()`: `reporter: Reporter | None = None`. This is
the foundation ticket for issue 08 (source-yield observability) — it
adds the extension point `pipeline.run()` calls into, with zero concrete
observability logic. No new package is created by this ticket; that is
ticket 002.

`Reporter` has two methods:
- `record_source(source_id, org_name, events, error=None)` — called once
  per active source, in the existing enumeration loop, for **both**
  branches of the existing per-source try/except: on success, `events`
  is the source's real `list[Event]` (`source_events`, unchanged from
  what the loop already produces) and `error` is `None`; on the
  adapter's isolated exception, `events` is `[]` and `error` is the
  caught exception. Pass the raw list, not a pre-computed count — a
  bare count cannot support the "dated" metric issue 08 asks for
  (events with a parsed `start`), and computing that count is
  Yield Tracking's job (ticket 002), not `pipeline.py`'s.
- `record_opportunities(opportunities)` — called exactly once, after
  `normalize_run()` produces the final `Opportunity` list and before
  `export_opportunities()` is called (i.e. while `.sources` is still
  present on each record — `export` strips it).

`run()`'s default `reporter` is a no-op, so every existing caller
(`cli.py`, `tests/test_pipeline_e2e*.py`) is unaffected without any
change on their part. `pipeline.py` must not import anything from a new
`observability` package or compute anything about deltas/alerts/text —
it only hands over facts it already has at the two points it already
visits them, mirroring the "must not become a god component" boundary
its own docstring already holds `Enricher` to.

Files to modify: `partner_scrape/pipeline.py` only (add `Reporter`
protocol, add the `reporter` parameter, add the two hook call sites).
No other module changes in this ticket.

## Acceptance Criteria

- [x] `Reporter` `Protocol` is defined in `pipeline.py` with
      `record_source(source_id, org_name, events, error=None)` and
      `record_opportunities(opportunities)`.
- [x] `run()` gains `reporter: Reporter | None = None`; every existing
      test in `tests/test_pipeline_e2e.py`,
      `tests/test_pipeline_e2e_enrichment.py`, and `tests/test_cli.py`
      passes unmodified.
- [x] `record_source` is called once per active source, in both the
      success and exception branches of the existing per-source loop —
      success passes the real `source_events` list; failure passes `[]`
      plus the caught exception.
- [x] `record_opportunities` is called exactly once, with the full
      `Opportunity` list `normalize_run()` produced (still carrying
      `.sources`), before `export_opportunities()` runs.
- [x] `run()`'s return value, existing parameters, and the `Enricher`
      protocol are byte-for-byte unchanged.
- [x] `pipeline.py` imports nothing from any new `observability` package
      — `Reporter` is satisfied structurally by whatever is passed in,
      exactly as `Enricher` already is by `LLMEnricher`.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_pipeline_e2e.py
  tests/test_pipeline_e2e_enrichment.py tests/test_cli.py` — must pass
  with zero modifications, proving the new parameter is truly additive.
- **New tests to write**: a spy `Reporter` double (a plain class
  recording every call it receives, no real computation) exercised via
  a real `pipeline.run()` call over the existing `tests/fixtures/
  e2e_registry/` fixtures (which include `brokensource.toml`, the
  deliberately-failing source). Assert: one `record_source` call per
  active source, with the right `events`/`error` per source (including
  `brokensource` getting `[]` + a real exception); exactly one
  `record_opportunities` call with the final `Opportunity` list
  (`.sources` still present) matching what the run actually produced.
  Add this to `tests/test_pipeline_e2e.py` (new test class) rather than
  a new file, following that file's existing fixture reuse.
- **Verification command**: `uv run pytest`
