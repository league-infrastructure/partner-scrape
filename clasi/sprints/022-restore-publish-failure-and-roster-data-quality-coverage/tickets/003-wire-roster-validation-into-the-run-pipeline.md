---
id: '003'
title: Wire roster validation into the run pipeline
status: open
use-cases:
- SUC-025
depends-on:
- '002'
github-issue: ''
issue: 48-pipeline-level-roster-data-quality-validation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wire roster validation into the run pipeline

## Description

Wire ticket 002's `validate_roster.validate_roster()` and
`find_unresolved_active_sources()` into `partner_scrape/pipeline.py`'s
`run()`, at the one call site sprint.md's Architecture and Design
Rationale identify as correct: **immediately after
`resolved_partners_path` is computed** (currently around the point where
`source_org_names = {source.source_id: source.org_name for source in
sources}` is built, shortly before `normalize_run(...)` is called) —
**before** that path is used by `normalize_run()` or
`partner_log.record()`.

Deliberately **not** in `cli.py`. Read `cli.py`'s own module docstring
before touching it: "a thin `argparse` wrapper ... this module owns flag
parsing and console output only; every real decision ... belongs to
`pipeline.run()` and the modules it calls." Roster validation is exactly
that kind of decision — it belongs in `pipeline.py`, not `cli.py`. This
ticket should not need to touch `cli.py` at all. (`cli.py`'s own
separate, later call to `publish.project()` reads the identical file via
the identical `args.site_dir`/`get_site_dir()` resolution — once
`pipeline.run()` validates and passes, that later read is already safe;
if `pipeline.run()` raises, `main()` never reaches the
`publish.project()` call. No independent validation is needed there.)

**Implementation shape:**

1. At the call site, read the raw partner list:
   `partners = json.loads(resolved_partners_path.read_text(encoding=
   "utf-8"))` (do not reuse `normalize.partners.load_partners()`'s
   `partners_by_norm` for this call — see ticket 002 / sprint.md's
   Design Rationale on why the content checks need the raw list). Call
   `validate_roster.validate_roster(partners)`. Let
   `RosterValidationError` propagate uncaught — this is a deliberate,
   fatal failure for a structural data problem, not a per-source
   isolated error (contrast with `_run_one_source`'s own
   try/except-and-continue convention, which this is **not**).
2. Separately, build `partners_by_norm` (either via
   `normalize.partners.load_partners(resolved_partners_path)` — a second
   independent read of the same small file, accepted per sprint.md's
   Migration Concerns — or by adapting the already-loaded `partners`
   list in memory if that avoids the extra read cleanly; either is
   acceptable, prefer whichever keeps the change smaller) and call
   `validate_roster.find_unresolved_active_sources(sources,
   partners_by_norm)`. `sources` is already in scope at this point in
   `run()` (loaded at the top of the function, already used to build
   `source_org_names`). If the returned list is non-empty, log it via
   `logger.warning(...)` — name every unresolved `org_name` in the
   message — and continue; never raise for this case.
3. This is unconditional (matches every other computation at this point
   in `run()`, which already runs regardless of `dry_run` — do not add a
   `dry_run` exemption; validating a would-be-written export payload
   before it's computed is exactly as valuable as validating a written
   one).

## Acceptance Criteria

- [ ] `pipeline.run()` calls `validate_roster.validate_roster()` on the
      raw partner list, immediately after `resolved_partners_path` is
      computed and before `normalize_run()`/`partner_log.record()` are
      called.
- [ ] A `RosterValidationError` from that call propagates uncaught out
      of `run()` — no output (`opportunities.json`, the per-partner
      `.jsonl` log, etc.) is written for a run whose roster fails
      validation.
- [ ] `pipeline.run()` calls `validate_roster.find_unresolved_active_
      sources()` and logs a warning (never raises) listing any
      unresolved `org_name`s, without aborting the run.
- [ ] Both calls run regardless of `--dry-run` (no exemption added).
- [ ] `cli.py` is unmodified by this ticket.
- [ ] **Required pre-close live validation**: run `partner-scrape run
      --dry-run -v --site-dir ../stem-ecosystem` (or the resolved
      default `--site-dir` if this machine's sibling checkout has moved)
      against the real sibling `stem-ecosystem` checkout, confirm it
      completes without raising, and record in this ticket's Notes the
      actual unresolved-source count reported (sprint.md's planning-time
      check found 9 of 93; confirm whether that has changed by execution
      time — do not assume it is still exactly 9).

## Testing

- **Existing tests to run**: `uv run pytest tests/test_pipeline_e2e.py
  tests/test_pipeline_e2e_ads.py tests/test_pipeline_e2e_companies.py
  tests/test_pipeline_e2e_enrichment.py` (every existing e2e fixture's
  `partners.json` must still pass the new validation — if any existing
  fixture fails, that fixture needs a fix, not a validation exemption),
  then the full suite.
- **New tests to write**: extend `tests/test_pipeline_e2e.py` (or add a
  sibling e2e file if that keeps the existing file's focus clean — use
  your judgment) with, using its existing `--site-dir`-pointed-at-
  `tmp_path` fixture-roster convention:
  - A bad-roster fixture (one row at the bare-California centroid, or
    any other single bad-data case — one is enough to prove the wiring;
    ticket 002 already proves every check fires in isolation) that makes
    `pipeline.run()` raise `RosterValidationError`, and asserts nothing
    was written to `opportunities.json`/the partner log as a result.
  - An unresolved-active-source fixture (a registry source whose
    `org_name` has no roster match) that completes the run normally and
    logs a warning (`caplog`), never raising.
  - A clean-roster fixture proving the run is unaffected (identical
    behavior to before this ticket).
- **Verification command**: `uv run pytest`, plus the required pre-close
  live-run command above (record its actual output in this ticket's
  Notes before moving it to done).
