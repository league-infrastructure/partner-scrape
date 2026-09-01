---
id: '006'
title: Publish places.json/clubs.json into data/ from export_directory()
status: done
use-cases:
- SUC-019
depends-on:
- '002'
github-issue: ''
issue: 60-publish-pipeline-output-in-well-known-data-directory.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Publish places.json/clubs.json into data/ from export_directory()

## Description

Extend `directory/export.py`'s `export_directory()` with a third write
path for both `places.json` and (when `clubs is not None`) `clubs.json`,
alongside its existing two `SITE_DIR` paths (`src/data`, `public/data`).
Add the same `own_data_dir: str | Path | None = None` keyword-only
parameter (default via `config.get_own_data_dir()`) used in tickets
003-005. Preserve this module's existing ordering contract exactly,
extended: `places.json`'s `src/data` write, then its `public/data`
write, then (new) its own-repo write, all complete before `clubs.json`
is touched at all; and — new — `clubs.json`'s own-repo write happens
only after its own `src/data`/`public/data` writes succeed, matching
"a `clubs.json` failure never leaves `places.json` half written, and a
`places.json` failure raises before `clubs.json` is ever touched."
Directory auto-created if missing, skipped entirely under `dry_run`.
Independent of tickets 003-005/007; depends only on ticket 002.

## Acceptance Criteria

- [x] `export_directory(places, ..., own_data_dir=<tmp_path>)` writes
      `places.json` into `own_data_dir`, byte-identical to the
      `SITE_DIR` copies.
- [x] `export_directory(places, ..., clubs=[...], own_data_dir=<tmp_path>)`
      additionally writes `clubs.json` into `own_data_dir`,
      byte-identical to the `SITE_DIR` copies.
- [x] `clubs=None` (the default) still means `clubs.json` is untouched
      at all three locations, including `own_data_dir` — unchanged
      ticket-007-era contract, extended consistently.
- [x] Omitting `own_data_dir` resolves via `config.get_own_data_dir()`.
- [x] `dry_run=True` writes to none of the locations.
- [x] A missing `own_data_dir` is created automatically, never raises.
- [x] Ordering: `places.json`'s three writes (site `src/data`, site
      `public/data`, own-repo) complete before any `clubs.json` write is
      attempted; a `places.json` write failure at any of its three
      targets prevents `clubs.json` from being touched.
- [x] The "two hard invariants" this module documents (never touches
      `opportunities.json`/`scrape-meta.json`/`teams.json`) still hold,
      remaining covered by `tests/directory/test_export.py`'s existing
      `TestHardInvariants`.
- [x] Every existing test in `tests/directory/test_export.py` continues
      to pass unmodified.
- [x] `export_directory()`'s docstrings are updated to describe the new
      third path and its place in the existing ordering contract.

## Implementation Plan

**Approach**: mirror this module's own existing `public/data` blocks
(one for `places.json`, one for `clubs.json`) for the new
`own_data_dir` blocks, appended after each respective `public/data`
write succeeds, from the already-built `serialized`/`serialized_clubs`
strings — no re-serialization.

**Files to modify**:
- `partner_scrape/directory/export.py` (`export_directory()`, module
  docstring)
- `tests/directory/test_export.py` (new test class)

**Files to create**: none.

## Testing

- **Existing tests to run**: `uv run pytest tests/directory/ -q`, then
  the full suite.
- **New tests to write**: a test class mirroring ticket 003's
  `TestOwnDataDirPublish` shape, scoped to `places.json`/`clubs.json`,
  including the `clubs=None` no-write case and the places-before-clubs
  ordering guarantee at the new own-repo target.
- **Verification command**: `uv run pytest -q`
