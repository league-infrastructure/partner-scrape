---
id: '003'
title: Publish opportunities.json/scrape-meta.json into data/ from export_opportunities()
status: done
use-cases:
- SUC-019
depends-on:
- '001'
- '002'
github-issue: ''
issue: 60-publish-pipeline-output-in-well-known-data-directory.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Publish opportunities.json/scrape-meta.json into data/ from export_opportunities()

## Description

Extend `export/writer.py`'s `export_opportunities()` to additionally
write its already-computed `opportunities.json`/`scrape-meta.json`
payload into partner-scrape's own `data/` directory
(`config.get_own_data_dir()`), unconditionally, alongside its existing
`SITE_DIR` write — one more path from the same payload and the same
`_now_iso()` timestamp already computed in this function call, so the
two copies can never drift (sprint.md Design Rationale: "extend each
export module's own function with a third write path"). This is a
production-scope ticket; depends on ticket 002 for `get_own_data_dir()`
and is sequenced after ticket 001 since both touch `export/writer.py`
(no functional dependency between the two, but both edit the same file
— avoid concurrent edits).

Add a new keyword-only parameter `own_data_dir: str | Path | None =
None` to `export_opportunities()`, defaulting to
`config.get_own_data_dir()` when omitted — mirroring exactly how
`site_dir` already defaults via `config.get_site_dir()`. Tests must
always pass an explicit `tmp_path`-backed value here, never rely on the
default (matching every existing `site_dir` test's own convention in
this file).

Unlike `SITE_DIR`'s `src/data` (which still fails loudly if missing —
unchanged), the own-repo `data/` directory must be created automatically
if it doesn't exist (`Path.mkdir(parents=True, exist_ok=True)`) — this
sprint deletes the only two files `data/` currently tracks (ticket 002),
so a fresh clone may have no `data/` at all. This mirrors how
`public/data/` is already handled in `teams/export.py`/`directory/export.py`
(created if missing, unlike the fail-loudly `src/data`).

`dry_run=True` must skip this write too, matching the existing
"nothing written" contract.

## Acceptance Criteria

- [x] `export_opportunities(..., own_data_dir=<tmp_path>)` writes
      `opportunities.json` and `scrape-meta.json` into `own_data_dir`,
      byte-identical in content to the `SITE_DIR` copies (same payload,
      same timestamp).
- [x] Omitting `own_data_dir` resolves via `config.get_own_data_dir()`
      (verified the same way this file's existing
      `test_omitted_site_dir_resolves_via_config_get_site_dir` test
      verifies `site_dir`'s own default — monkeypatch the config
      function, don't touch the real repo `data/`).
- [x] `dry_run=True` writes nothing to `own_data_dir` (nor `site_dir`,
      unchanged).
- [x] A missing `own_data_dir` is created automatically
      (`mkdir(parents=True, exist_ok=True)`), never raises.
- [x] Every existing `TestCurrentUpcomingFilter`,
      `TestDSTBoundaryPartitioning`, `TestInternshipCurrentUpcomingFilter`,
      `TestDeadlineFirstCurrentUpcomingFilterGeneralization`,
      `TestExportSortOrder`, `TestSlugDedup`, `TestSiteSchemaShape`,
      `TestScrapeMeta`, `TestDryRun`, `TestTargetDirIsolation`,
      `TestSiteDirErrors` test continues to pass unmodified (this
      ticket is additive to `export_opportunities()`'s signature and
      behavior, not a replacement of any existing path).
- [x] `export_opportunities()`'s module/function docstrings are updated
      to describe the new third write path.

## Implementation Plan

**Approach**: mirror `teams/export.py`'s existing "second write path"
code shape (its `public/data/` block) as closely as possible for
consistency, applied to `export_opportunities()`'s existing single
`data_dir` write block. Resolve `resolved_own_data_dir` the same way
`resolved_site_dir` is resolved (`Path(own_data_dir) if own_data_dir is
not None else get_own_data_dir()`), immediately after the existing
`resolved_site_dir` resolution. After the existing `SITE_DIR` write
succeeds, `mkdir(parents=True, exist_ok=True)` the own-data directory
and write both files there from the same `payload`/timestamp values
already in scope — no re-serialization, no second `_now_iso()` call.

**Files to modify**:
- `partner_scrape/export/writer.py` (`export_opportunities()`, module
  docstring)
- `tests/test_export.py` (new test class, see Testing)

**Files to create**: none.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_export.py -q`,
  then the full suite.
- **New tests to write**: a new `TestOwnDataDirPublish` class in
  `tests/test_export.py`, covering: write happens and matches `SITE_DIR`
  content; default resolution via `config.get_own_data_dir()`
  (monkeypatched); `dry_run` skip; auto-creation of a missing directory.
  Mirror the existing `TestTargetDirIsolation`/`TestDryRun` classes'
  structure and naming conventions.
- **Verification command**: `uv run pytest -q`
