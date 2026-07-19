---
id: '003'
title: CLI wiring for yield reporting
status: done
use-cases:
- SUC-017
- SUC-018
depends-on:
- '002'
github-issue: ''
issue: 08-source-yield-observability.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# CLI wiring for yield reporting

## Description

Wire ticket 002's `YieldReporter` into `partner_scrape/cli.py` as the
default, observable path — the same role `cli.py` already plays for
`LLMEnricher`:

- New `--yield-history PATH` flag, defaulting to
  `{site_dir}/src/data/yield-history.json` (resolved the same way
  `--site-dir` already resolves against `Config.get_site_dir()`).
- New `--no-report` flag (mirrors `--no-enrich`'s shape/purpose): skips
  constructing a `YieldReporter` entirely, so `run()` behaves exactly as
  it does today (`reporter=None`) — an escape hatch for tests and any
  local usage that wants the pre-sprint-004 behavior unchanged.
- Default behavior (neither flag overridden): before calling `run()`,
  load the previous snapshot via `load_snapshot(yield_history_path)`;
  construct `YieldReporter()`; pass `reporter=` into `run()`. After
  `run()` returns, call `.report(previous_snapshot)`, print
  `render_text(report)` to stdout *after* the existing
  `"partner-scrape: wrote N opportunities..."` line (additive, not a
  replacement), and `save_snapshot(yield_history_path, report)`.
- Confirm, without new code, two things this ticket's acceptance
  criteria depend on already being true: (a) `export_opportunities()`'s
  current/upcoming filter already excludes past events from every run's
  output — already covered by `tests/test_pipeline_e2e.py`'s existing
  past-vs-upcoming fixture assertion (`coastalrootsfarm.toml`'s one past
  + one upcoming event); (b)
  `stem-ecosystem/src/components/Footer.astro` already renders
  `scrape-meta.json`'s `last_updated` as the visible "last updated"
  stamp — verified by reading the file during sprint planning, no site-
  repo change is in scope. Record these two confirmations in this
  ticket's notes rather than re-testing behavior sprint 001 already
  covers.

Files to modify: `partner_scrape/cli.py` only.

## Acceptance Criteria

- [x] `--yield-history PATH` flag exists, defaulting to
      `{site_dir}/src/data/yield-history.json`.
- [x] `--no-report` flag skips `YieldReporter` construction entirely;
      `run()` is called exactly as it was before this ticket (i.e.
      `reporter` omitted/`None`) when it is passed.
- [x] Default (no flags) run: loads the previous snapshot (or an empty
      baseline if the file is absent), passes `reporter=YieldReporter()`
      into `run()`, prints `render_text(...)` to stdout after the
      existing summary line, and saves the new snapshot.
- [x] Existing `cli.py` flags, their defaults, and the existing
      `"partner-scrape: wrote N opportunities..."` print are byte-for-
      byte unchanged.
- [x] Ticket notes confirm (a) past-event pruning is already covered by
      existing `export`/pipeline-e2e test coverage and (b) the "last
      updated" stamp already flows to `stem-ecosystem`'s `Footer.astro`
      — both cited by file/test name, not re-implemented.

## Notes

- **(a) Past-event pruning**, confirmed without new code: `export.
  export_opportunities()`'s current/upcoming filter already excludes
  past events from every run's output. Covered by
  `tests/test_pipeline_e2e.py::TestWalkingSkeletonEndToEnd::
  test_upcoming_filter_excludes_the_past_event`, which asserts
  `coastalrootsfarm.toml`'s past fixture event ("Spring Planting Day")
  is absent from `run()`'s payload while its upcoming event survives
  (see also `test_exactly_two_opportunities_survive_dedup_collapse_and_
  the_upcoming_filter` in the same class). This test was already
  passing before this ticket and remains unmodified.
- **(b) "Last updated" stamp**, confirmed without new code: `stem-
  ecosystem/src/components/Footer.astro` already reads
  `scrape-meta.json` (`import scrapeMeta from '../data/scrape-meta.
  json'`) and renders `scrapeMeta.last_updated` as the visible
  `Last updated: {lastUpdated}` footer line. Verified by reading the
  file directly (`../stem-ecosystem/src/components/Footer.astro`) during
  this ticket's implementation; no site-repo change is in scope or was
  made.
- **Hermeticity fix beyond the ticket's literal test list**: this
  ticket's default CLI wiring resolves `--yield-history`'s default path
  via `Config.get_site_dir()` *before* calling `run()`, unconditionally
  inside `cli.main()` itself -- unlike `--site-dir`, whose resolution
  lives inside `pipeline.run()` and is never reached once
  `tests/test_cli.py` monkeypatches `cli.run`. Left as originally
  written, every existing `tests/test_cli.py` test that omits
  `--site-dir` would have resolved against the real sibling
  `../stem-ecosystem` checkout (confirmed to exist on the implementing
  machine) and, on a default (non-`--no-report`, non-`--dry-run`) run,
  written a real `yield-history.json` into it -- directly violating this
  ticket's own "NO writes to real ../stem-ecosystem" testing constraint.
  Fixed by pinning `SITE_DIR` to `tmp_path` in `tests/test_cli.py`'s
  existing autouse `_cache_dir` fixture (alongside its existing
  `SCRAPE_CACHE_DIR` pin), so every test in the file -- old and new --
  stays hermetic. This required a small, mechanical edit to one existing
  test's assertions (`test_defaults_pass_none_through_to_pipeline_run`,
  `TestArgumentWiring`): it now pops the new `"reporter"` kwarg before
  its strict dict-equality check, exactly the same pattern the test
  already used for `"enrichers"`, and asserts the popped value is a
  `YieldReporter` instance. No other existing test body changed; all 421
  pre-existing tests plus this ticket's new ones pass.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_cli.py
  tests/test_pipeline_e2e.py` — must pass unmodified.
- **New tests to write**: extend `tests/test_cli.py` with
  `--yield-history`/`--no-report` coverage, using `tmp_path` for both
  `--site-dir` and `--yield-history`, the fixture `--registry-dir`, and
  `--no-enrich` (so no `ANTHROPIC_API_KEY` is needed). Assert the
  rendered report text appears in captured stdout by default, and does
  not when `--no-report` is passed; assert `yield-history.json` is
  written at the expected path after a default run.
- **Verification command**: `uv run pytest`
