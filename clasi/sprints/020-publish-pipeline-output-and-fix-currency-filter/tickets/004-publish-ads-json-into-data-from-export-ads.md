---
id: '004'
title: Publish ads.json into data/ from export_ads()
status: in-progress
use-cases:
- SUC-019
depends-on:
- '002'
github-issue: ''
issue: 60-publish-pipeline-output-in-well-known-data-directory.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Publish ads.json into data/ from export_ads()

## Description

Extend `export/ads.py`'s `export_ads()` the same way ticket 003 extends
`export_opportunities()`: a new keyword-only `own_data_dir: str | Path |
None = None` parameter (default via `config.get_own_data_dir()`), an
additional unconditional write of the already-computed `ads.json`
payload into it, skipped under `dry_run`, directory auto-created if
missing (`mkdir(parents=True, exist_ok=True)`) — same rationale as
ticket 003 (this sprint just deleted `data/`'s only two tracked files).
Independent of tickets 003/005/006/007 (each touches a different file);
depends only on ticket 002 for `get_own_data_dir()`.

## Acceptance Criteria

- [x] `export_ads(..., own_data_dir=<tmp_path>)` writes `ads.json` into
      `own_data_dir`, byte-identical to the `SITE_DIR` copy.
- [x] Omitting `own_data_dir` resolves via `config.get_own_data_dir()`.
- [x] `dry_run=True` writes nothing to `own_data_dir`.
- [x] A missing `own_data_dir` is created automatically, never raises.
- [x] Every existing test exercising `export_ads()` continues to pass
      unmodified.
- [x] `export_ads()`'s docstrings are updated to describe the new third
      write path.

## Implementation Plan

**Approach**: identical shape to ticket 003's change, applied to
`export_ads()`'s existing single `data_dir` write block — resolve
`resolved_own_data_dir`, `mkdir(parents=True, exist_ok=True)`, write the
same already-serialized payload a second time after the existing
`SITE_DIR` write succeeds.

**Files to modify**:
- `partner_scrape/export/ads.py` (`export_ads()`, module docstring)
- The test file covering `export_ads()` (locate via `grep -rl
  "export_ads" tests/` — likely `tests/test_export_ads.py`; add the new
  test class there).

**Files to create**: none.

## Testing

- **Existing tests to run**: the located `export_ads()` test file, then
  the full suite.
- **New tests to write**: a test class mirroring ticket 003's
  `TestOwnDataDirPublish` shape, scoped to `ads.json`: write happens and
  matches `SITE_DIR` content, default resolution, `dry_run` skip,
  auto-creation of a missing directory.
- **Verification command**: `uv run pytest -q`
