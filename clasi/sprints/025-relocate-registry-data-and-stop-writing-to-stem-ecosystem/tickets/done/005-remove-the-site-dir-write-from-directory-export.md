---
id: '005'
title: Remove the site_dir write from Directory export
status: done
use-cases:
- SUC-029
depends-on: []
github-issue: ''
issue: stop-writing-to-stem-ecosystem-checkout.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove the site_dir write from Directory export

## Description

`directory/export.py`'s `export_directory()` currently writes
`places.json` (and, when given, `clubs.json`) into three targets each:
`{site_dir}/src/data/`, `{site_dir}/public/data/`, and `own_data_dir`.
Remove both `{site_dir}/...` writes for each file — `own_data_dir`
becomes the sole target.

Unlike Teams (ticket 004), `directory/pipeline.py`'s `run_directory()`
**keeps** its `site_dir` parameter: `_check_related_partner_references()`
reads `{site_dir}/src/data/partners.json` for the
`related_partner_id` join-integrity check, a real, independent use that
has nothing to do with `export_directory()`'s write. Only stop
forwarding `site_dir` into `export_directory()`.

## Acceptance Criteria

- [x] `export_directory()` no longer accepts a `site_dir` parameter and
      never writes `places.json`/`clubs.json` under `{site_dir}/...`
      (neither `src/data/` nor `public/data/`, for either file). Its
      `own_data_dir` writes are unchanged in shape and ordering
      (`places.json` before `clubs.json`).
- [x] `run_directory()` (`directory/pipeline.py`) keeps its `site_dir`
      parameter, still used for `_check_related_partner_references()`'s
      `partners.json` read; it stops passing `site_dir` into its
      `export_directory()` call.
- [x] The `directory` CLI subcommand's `--site-dir` flag is unchanged
      (it still controls the `related_partner_id` read).
- [x] The "Two hard invariants" regression test in
      `tests/directory/test_export.py` (asserting `opportunities.json`/
      `scrape-meta.json`/`teams.json` are byte-identical before/after a
      `directory` run) still passes — untouched by this ticket.
- [x] `uv run pytest -q` is green.

## Implementation Plan

**Approach**: same mechanical pattern as tickets 003/004, but stop one
level earlier — `run_directory()` keeps `site_dir` because it has an
independent, real reason to (the read), unlike `run_teams()`.

1. `directory/export.py`: remove `export_directory()`'s `site_dir`
   parameter and every `resolved_site_dir`-based write block for both
   `places.json` and `clubs.json` (`src/data/` and `public/data/`,
   both files). Keep both `own_data_dir` writes and their existing
   ordering (`places.json`'s three targets fully succeed before
   `clubs.json` is touched — now just one target instead of three, but
   the same ordering principle). Update the "three write targets are
   not symmetric" docstring section.
2. `directory/pipeline.py`: in `run_directory()`'s call to
   `export_directory(places, clubs=clubs, site_dir=site_dir,
   dry_run=dry_run)`, drop `site_dir=site_dir`. Leave
   `run_directory()`'s own `site_dir` parameter and
   `_check_related_partner_references(places, site_dir=site_dir)` call
   untouched.

**Files to modify**: `directory/export.py`; `directory/pipeline.py`.

**Testing plan**: update `tests/directory/test_export.py` to drop
`site_dir=tmp_path` from `export_directory()` calls and invert any
assertion that a `{site_dir}/...` file was written. Update
`tests/directory/test_pipeline.py`/`tests/test_cli_directory.py` only
where they assert on `export_directory()`'s own write targets — leave
the `related_partner_id`/`partners.json`-read tests untouched, since
that behavior doesn't change. Run
`uv run pytest tests/directory/ tests/test_cli_directory.py -q`.

**Documentation updates**: `directory/export.py`'s module docstring
(the "three write targets" framing becomes "one write target"; keep the
`places.json`-before-`clubs.json` ordering note, since it still applies
with one target instead of three).
