---
id: '005'
title: Publish teams.json into data/ from export_teams()
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

# Publish teams.json into data/ from export_teams()

## Description

Extend `teams/export.py`'s `export_teams()` with a third write path,
alongside its existing two (`{site_dir}/src/data/teams.json` and
`{site_dir}/public/data/teams.json`, sprint 017's "one publish, two
paths"). Add the same `own_data_dir: str | Path | None = None`
keyword-only parameter (default via `config.get_own_data_dir()`) used in
tickets 003/004, writing the identical serialized `teams.json` payload
into `own_data_dir / "teams.json"` — unconditional, skipped under
`dry_run`, directory auto-created if missing. The `src/data` write must
still be attempted (and its `RuntimeError` propagate) before either the
`public/data` or the new own-repo write is attempted, matching this
module's existing "ordering: `src/data` first, its failure propagates
before any other target is touched" contract — extend that ordering to
put the new own-repo write last, after both existing `SITE_DIR` writes
succeed. Independent of tickets 003/004/006/007; depends only on ticket
002.

## Acceptance Criteria

- [ ] `export_teams(..., own_data_dir=<tmp_path>)` writes `teams.json`
      into `own_data_dir`, byte-identical to the `SITE_DIR` copies.
- [ ] Omitting `own_data_dir` resolves via `config.get_own_data_dir()`.
- [ ] `dry_run=True` writes to none of the three locations (unchanged
      for the first two, extended to the third).
- [ ] A missing `own_data_dir` is created automatically, never raises.
- [ ] Write ordering: a `src/data` failure still propagates before
      `public/data` or `own_data_dir` is touched; a `public/data`
      failure still propagates before `own_data_dir` is touched (new:
      the own-repo write is always last).
- [ ] The "two hard invariants" this module documents (never touches
      `opportunities.json`/`scrape-meta.json`) still hold and remain
      covered by `tests/teams/test_export.py`'s existing
      `TestHardInvariants`.
- [ ] Every existing test in `tests/teams/test_export.py` continues to
      pass unmodified.
- [ ] `export_teams()`'s docstrings (including its "two write targets
      are not symmetric" section) are updated to describe the new third
      path and its ordering.

## Implementation Plan

**Approach**: mirror this module's own existing `public/data` block
(the precedent this whole sprint is extending) for the new
`own_data_dir` block — same `mkdir(parents=True, exist_ok=True)` +
write-with-`RuntimeError`-on-`OSError` shape, appended after the
existing `public/data` write succeeds, from the same `serialized`
string already built once in this function.

**Files to modify**:
- `partner_scrape/teams/export.py` (`export_teams()`, module docstring)
- `tests/teams/test_export.py` (new test class)

**Files to create**: none.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/ -q`, then the
  full suite.
- **New tests to write**: a test class mirroring ticket 003's
  `TestOwnDataDirPublish` shape, scoped to `teams.json`, plus a
  write-ordering test (own_data_dir untouched when `src/data` or
  `public/data` fails).
- **Verification command**: `uv run pytest -q`
