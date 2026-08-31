---
id: '001'
title: Publish teams.json into the public data contract
status: open
use-cases: [SUC-001]
depends-on: []
github-issue: ''
issue: 42-publish-teams-json-and-llms-mention.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Publish teams.json into the public data contract

## Description

`partner_scrape/teams/export.py::export_teams()` currently writes the
finished `{"meta": ..., "teams": [...]}` payload to exactly one location,
`{site_dir}/src/data/teams.json` — a build-time Astro input, not a
publicly fetchable file. Teach `export_teams()` a second write target:
`{site_dir}/public/data/teams.json`, the identical payload, written in
the same call.

This is the sprint's write-location decision (see `sprint.md`'s Design
Rationale): the second write lives inside `teams/export.py` itself,
never inside `export/publish.py` or any other `export/` module, so
`teams/` and `export/` remain structurally independent (no new import
either direction). `mirror.py` needs no change — it already recursively
copies the whole `public/data/` tree into extra site checkouts, so the
new file rides that unchanged.

Unlike the existing `src/data` write (which assumes its directory
already exists and raises if not), the new `public/data` write must
create its target directory if missing
(`Path.mkdir(parents=True, exist_ok=True)`) before writing — a fresh
`site/` checkout is not guaranteed to have a `public/data/` directory
yet (it's created by `export/publish.py::project()`, which may not have
run there before a `teams` run does).

`completes_issue: false` is set on this ticket because ticket 002 also
addresses issue 42 (the documentation half); issue 42 should archive
only once both tickets are done.

## Acceptance Criteria

- [ ] `export_teams()` writes the same payload to both
      `{site_dir}/src/data/teams.json` and
      `{site_dir}/public/data/teams.json` on a normal (non-`dry_run`)
      call — byte-identical content, one JSON serialization, two writes.
- [ ] `public/data/` is created (`mkdir(parents=True, exist_ok=True)`)
      if it does not already exist under `site_dir`; `src/data/`'s
      existing "must already exist" contract is unchanged.
- [ ] `dry_run=True` writes neither file (matching the existing
      `src/data/teams.json` contract, extended to the new path).
- [ ] An unwritable `public/data` target (e.g. occupied by a file, or a
      read-only parent) raises `RuntimeError` with a message identifying
      the path — matching `export_teams()`'s existing fail-loud contract
      for `src/data`. Confirm the existing `src/data` failure path is
      unaffected by this change (i.e. a `src/data` failure still raises
      before or independently of any `public/data` write attempt — pick
      one explicit ordering and document it in the docstring).
- [ ] The two existing hard-invariant regression tests in
      `tests/teams/test_export.py` (byte-identical `opportunities.json`/
      `scrape-meta.json` before/after a `teams` run) still pass unchanged
      — this ticket must never touch those files.
- [ ] `export_teams()`'s module/function docstring is updated to describe
      the second write target and the directory-creation asymmetry
      between `src/data` and `public/data`.
- [ ] Full test suite green (`uv run pytest`).

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/test_export.py`
  (full module) and the full suite (`uv run pytest`) to confirm no
  regression elsewhere (e.g. `tests/test_cli_teams.py`,
  `tests/teams/test_pipeline.py`).
- **New tests to write** (in `tests/teams/test_export.py`, alongside the
  existing fixture-based tests):
  - `public/data/teams.json` is written and its parsed content equals
    `src/data/teams.json`'s parsed content, over the existing 152-team
    (or equivalent) fixture.
  - `public/data/` is created when absent from a fresh `tmp_path`-based
    `site_dir` fixture.
  - `dry_run=True` leaves neither `src/data/teams.json` nor
    `public/data/teams.json` on disk.
  - An unwritable `public/data` path (e.g. a file created at that exact
    path before the call) raises `RuntimeError` and does not silently
    skip.
- **Verification command**: `uv run pytest`
