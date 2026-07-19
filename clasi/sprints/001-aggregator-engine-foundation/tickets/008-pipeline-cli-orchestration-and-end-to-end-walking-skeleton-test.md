---
id: 008
title: Pipeline/CLI orchestration and end-to-end walking-skeleton test
status: done
use-cases:
- SUC-008
depends-on:
- '002'
- '004'
- '005'
- '006'
- '007'
github-issue: ''
issue:
- 01-aggregator-engine-foundation.md
- 02-adapter-framework-structured-apis.md
- 05-normalize-dedup-site-export.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Pipeline/CLI orchestration and end-to-end walking-skeleton test

## Description

Wire every module built in tickets 001-007 into one runnable command
(sprint architecture: Pipeline/CLI) and prove it end-to-end with a
fixture-only test. This ticket is what turns seven separately-tested
modules into the "runnable, tested, end-to-end aggregator engine" the
sprint goal asks for — it is the last ticket specifically because
everything else must exist first.

Scope:
- `partner_scrape/pipeline.py`: `run(registry_dir, site_dir, enrichers=
  ())` — enumerates Registry sources (ticket 002), dispatches each to
  its adapter via the ticket 004/005 dispatch registry, collects
  `Event`s, applies the (currently empty) `enrichers` list to the
  collected Events (sprint architecture's Deferred Seam — an `Enricher`
  protocol with zero implementations shipped this sprint; sprint 2's
  LLM enrichment, issue 04, drops in as one more list entry, no
  Pipeline rework required), hands the result to `normalize.run()`
  (ticket 006), then to `export.writer` (ticket 007).
- **Per-source error isolation**: if one source's adapter raises, log
  it and continue with the remaining sources — the run must never
  produce zero output because one source is broken. This is the
  Pipeline-level isolation distinct from ticket 004's per-*record*
  isolation within a single adapter run.
- `partner_scrape/cli.py`: a small CLI entry point (argparse) exposing
  `registry-dir`, `site-dir`, `--dry-run` flags, calling
  `pipeline.run()`. Add a `pyproject.toml` console-script entry point
  (e.g. `partner-scrape = "partner_scrape.cli:main"`).
- End-to-end test: a small, fixture-only registry (2-3 sources, at
  least one deliberately pointing at a broken/malformed fixture) run
  through the real `pipeline.run()` with a fixture `Fetcher` injected,
  asserting a valid `opportunities.json`/`scrape-meta.json` pair lands
  in a temp directory, and that the broken source's failure didn't
  prevent the others' data from being exported.
- README: add a short "Running the engine" section once there's
  something runnable to document (this is the first ticket where that's
  true).

## Acceptance Criteria

- [x] `pipeline.run(registry_dir, site_dir)` executes the full chain:
      Registry → Adapter dispatch → (empty) enrichers → Normalize →
      Export, using the real modules from tickets 002-007.
- [x] `enrichers` defaults to an empty tuple/list; passing a custom
      enricher (a trivial identity function, for the test) is applied
      to the Event stream before normalization — proving the hook is
      real, not just declared.
- [x] One source's adapter raising an exception is logged and does not
      stop the run; the other sources' data still reaches the final
      export.
- [x] An end-to-end test using a fixture-only registry (2-3 sources,
      one intentionally broken) and a fixture `Fetcher` produces a
      valid `opportunities.json` + `scrape-meta.json` pair in a
      `tmp_path`-based site-dir stand-in.
- [x] The full test suite (`uv run pytest`, all tickets) passes with no
      network access and no `ANTHROPIC_API_KEY` usage — confirmed by
      running it with `SCRAPE_CACHE_DIR` pointed at an empty temp
      directory and no outbound-network capability.
- [x] `partner-scrape` (or equivalent) is runnable as a console script
      per `pyproject.toml`'s entry point.
- [x] `README.md` gains a short section describing how to run the
      engine (registry dir, site dir, dry-run).

## Implementation Plan

### Approach

`pipeline.run()` should read as a short, linear sequence of calls into
the modules already built — if it grows business logic of its own
beyond sequencing + error isolation, that's a sign a responsibility
leaked out of its owning module and belongs there instead (this is the
"Pipeline/CLI must not become a god component" check the sprint
architecture's self-review flagged and pre-justified; keep it true in
code, not just in the diagram). Define the `Enricher` protocol
(`Protocol` with `def enrich(events: list[Event]) -> list[Event]`) in
`pipeline.py` itself (it's a one-method interface with zero
implementations this sprint — doesn't warrant its own module yet).
Per-source error isolation: wrap each source's `adapter.run(source)`
call in its own try/except inside the enumeration loop, not around the
whole batch.

### Files to Create/Modify

- `partner_scrape/pipeline.py`
- `partner_scrape/cli.py`
- `pyproject.toml` — add the `partner-scrape` console-script entry
  point.
- `README.md` — "Running the engine" section.
- `tests/test_pipeline_e2e.py`
- `tests/fixtures/e2e_registry/` (2-3 TOML source files: at least one
  valid `tec_rest` pointing at a fixture response, one deliberately
  broken — e.g. `adapter_type` set but the fixture `Fetcher` has no
  matching canned response, forcing a real failure path)

### Documentation Updates

`README.md` gains the "Running the engine" section described above —
the first ticket in this sprint where there is something concrete to
document.

## Testing

- **Existing tests to run**: `uv run pytest` (the full suite from
  tickets 001-007 — this ticket must not regress any of them).
- **New tests to write**: `tests/test_pipeline_e2e.py` per the
  acceptance criteria above — the walking-skeleton proof for the whole
  sprint.
- **Verification command**: `uv run pytest` (run once with
  `SCRAPE_CACHE_DIR` pointed at an empty temp directory to confirm no
  hidden dependency on real cached data)
