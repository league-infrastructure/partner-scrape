---
id: '002'
title: Teams pipeline export and CLI subcommand
status: open
use-cases:
- SUC-001
depends-on:
- '001'
github-issue: ''
issue: robot-teams-scrape-locate-and-publish-san-diego-first-teams.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Teams pipeline export and CLI subcommand

## Description

Wire ticket 001's `Team`/FTCScout source into a runnable, publishable
end-to-end path: `teams.pipeline.run_teams()` sequences acquisition →
export; `teams.export` writes `teams.json`; a new `partner-scrape teams`
CLI subcommand invokes it; `export/mirror.py` propagates `teams.json`
to extra checkouts. Completes the issue's increment 1 ("Model +
FTCScout + export + subcommand") — after this ticket, `teams.json`
with 152 FTC teams is a real, buildable artifact. Completes SUC-001.

## Acceptance Criteria

- [ ] `partner_scrape/teams/pipeline.py` defines `run_teams(*,
      source=None, site_dir=None, dry_run=False) -> dict`, sequencing
      the configured `TeamSource`(s) → `teams.export.export_teams(...)`.
      `source` restricts to one named source (`"ftcscout"` for now).
- [ ] `partner_scrape/teams/export.py` defines
      `export_teams(teams, site_dir=None, *, dry_run=False) -> dict`,
      writing `{site_dir}/src/data/teams.json` with a `meta` envelope
      (`generated` timestamp, per-league counts, out-of-region count)
      and a `teams` array. **Never** writes or touches
      `opportunities.json` or `scrape-meta.json` — tested explicitly
      (hard invariant).
- [ ] `export_teams` performs no field re-derivation (matches
      `export/writer.py`'s "filter, serialize, write" discipline) and
      raises on an unwritable `site_dir`, matching
      `export_opportunities`'s loud-failure contract.
- [ ] `partner_scrape/cli.py` gains a `teams` subcommand:
      `partner-scrape teams [--dry-run] [--source ftcscout] [--site-dir
      DIR] [--no-mirror] [-v]`, calling `run_teams(...)` and, unless
      `--no-mirror` or `--dry-run`, `export.mirror_site_data`. The
      existing `run`/`discover-candidates` subcommands are unmodified —
      tested by re-running their existing test suites unchanged.
- [ ] `export/mirror.py`'s `MIRRORED_DATA_FILES` gains `"teams.json"`.
- [ ] `partner-scrape teams --dry-run -v` against ticket 001's fixture
      reports 152 FTC teams with no network access and no disk write.
- [ ] `teams.json` is written to `{site_dir}/src/data/` on a real
      (non-dry-run) invocation and mirrored to every configured
      checkout on the next `mirror_site_data` call.
- [ ] A test asserts no key or value in the written `teams.json`
      matches an email-address pattern.
- [ ] A test asserts `opportunities.json`/`scrape-meta.json` are
      byte-identical before and after a `teams` run.

## Implementation Plan

**Approach**: `pipeline.py` is intentionally thin — orchestration only,
mirroring `partner_scrape/pipeline.py`'s own "sequencing, not business
logic" discipline. `export.py` should read like a scoped-down
`export/writer.py`: no current/upcoming filter (teams are undated), no
slug-uniqueness pass needed yet (`team_id` is already unique by
construction), but the same "serialize exactly the published field set,
write, done" shape. Add the `teams` subcommand to `cli.py` as a new
`argparse` subparser alongside `run`/`discover-candidates`, not a flag
on `run` — a future TBA credential failure (ticket 003) must never sit
inside `run`'s process/exit code. Extend `export/mirror.py`'s
`MIRRORED_DATA_FILES` tuple by one entry; do not touch its copy logic.

**Files to create**:
- `partner_scrape/teams/pipeline.py`
- `partner_scrape/teams/export.py`
- `tests/fixtures/teams/` additions as needed for CLI/export-level
  fixtures (distinct from ticket 001's source-level fixture)

**Files to modify**:
- `partner_scrape/cli.py` — add the `teams` subcommand.
- `partner_scrape/export/mirror.py` — add `"teams.json"` to
  `MIRRORED_DATA_FILES`.
- `partner_scrape/teams/DESIGN.md` — extend ticket 001's draft with
  `pipeline.py`/`export.py`'s actual shape and the CLI subcommand.

## Documentation

Extend `partner_scrape/teams/DESIGN.md` (created in ticket 001) to
cover `pipeline.py`, `export.py`, and the `teams` CLI subcommand —
refreshed against the actual code, not the pre-code draft. Also add
one sentence to `partner_scrape/DESIGN.md`'s `cli.py` bullet if the
final subcommand signature differs from what the sprint's `design/`
overlay anticipated (`clasi/sprints/011-robot-teams/design/DESIGN.md`)
— that overlay is applied to the canonical doc at sprint close, so it
should describe what was actually built.

## Testing

- **Existing tests to run**: `uv run pytest` (confirms `run`/
  `discover-candidates` and the whole opportunities pipeline are
  unaffected).
- **New tests to write**:
  - `tests/teams/test_pipeline.py` — `run_teams()` against a fixture
    source, dry-run and real-write paths.
  - `tests/teams/test_export.py` — `export_teams()` writes correct
    JSON shape; email-pattern guard; `opportunities.json`/
    `scrape-meta.json` untouched guard.
  - `tests/test_cli_teams.py` (or extend the existing CLI test module)
    — the `teams` subcommand's argument parsing and dry-run/verbose
    behavior.
  - Extend the existing mirror test module to cover `teams.json` in
    `MIRRORED_DATA_FILES`.
- **Verification command**: `uv run pytest tests/teams/ && uv run
  pytest && partner-scrape teams --dry-run -v`
