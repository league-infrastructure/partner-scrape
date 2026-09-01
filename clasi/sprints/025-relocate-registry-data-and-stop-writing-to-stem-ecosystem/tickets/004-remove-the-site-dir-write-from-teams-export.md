---
id: '004'
title: Remove the site_dir write from Teams export
status: in-progress
use-cases:
- SUC-029
depends-on: []
github-issue: ''
issue: stop-writing-to-stem-ecosystem-checkout.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove the site_dir write from Teams export

## Description

`teams/export.py`'s `export_teams()` currently writes `teams.json` into
three targets: `{site_dir}/src/data/`, `{site_dir}/public/data/`, and
`own_data_dir`. Remove both `{site_dir}/...` writes — `own_data_dir`
becomes the sole target. `teams/pipeline.py`'s `run_teams()` only ever
used its own `site_dir` parameter to pass through to `export_teams()`
(confirmed during planning — no independent read anywhere in
`run_teams()`'s body), so it becomes fully dead once `export_teams()`
drops the parameter; remove it too, along with the `teams` CLI
subcommand's now-meaningless `--site-dir` flag.

## Acceptance Criteria

- [ ] `export_teams()` no longer accepts a `site_dir` parameter and
      never writes `teams.json` under `{site_dir}/...` (neither
      `src/data/` nor `public/data/`). Its `own_data_dir` write is
      unchanged in shape.
- [ ] `run_teams()` (`teams/pipeline.py`) no longer accepts a `site_dir`
      parameter.
- [ ] `cli.py`'s `teams` subcommand no longer defines a `--site-dir`
      flag, and `_run_teams()` no longer threads one through.
- [ ] The "Two hard invariants" regression test in
      `tests/teams/test_export.py` (asserting `opportunities.json`/
      `scrape-meta.json` are byte-identical before/after a `teams` run)
      still passes — untouched by this ticket.
- [ ] `uv run pytest -q` is green.

## Implementation Plan

**Approach**: mirror ticket 003's mechanical removal pattern, extended
one level further up the call chain (through `run_teams()` to the CLI)
since nothing downstream of `export_teams()`'s `site_dir` has any other
use for it.

1. `teams/export.py`: remove `export_teams()`'s `site_dir` parameter
   and both `resolved_site_dir`-based write blocks (`src/data/` and
   `public/data/`). Keep the `own_data_dir` write unchanged. Update the
   "three write targets are not symmetric" docstring section to
   describe the new single-target contract.
2. `teams/pipeline.py`: remove `run_teams()`'s `site_dir` parameter and
   its pass-through to `export_teams()`.
3. `cli.py`: remove the `teams` subcommand's `--site-dir`
   `add_argument(...)` call and `_run_teams()`'s
   `site_dir=args.site_dir` argument to `run_teams()`.

**Files to modify**: `teams/export.py`; `teams/pipeline.py`; `cli.py`.

**Testing plan**: update `tests/teams/test_export.py`,
`tests/teams/test_pipeline.py`, and `tests/test_cli_teams.py` to drop
`site_dir=tmp_path` fixture arguments and any assertion that a
`{site_dir}/...` file was written; where a test specifically existed to
prove the site_dir write happens, invert it to assert it does not. Run
`uv run pytest tests/teams/ tests/test_cli_teams.py -q`.

**Documentation updates**: `teams/export.py`'s module docstring (the
"one publish, three paths" framing becomes "one publish, one path").
