---
id: '007'
title: Redirect publish.project()'s per-partner projection to data/
status: in-progress
use-cases:
- SUC-029
depends-on: []
github-issue: ''
issue: stop-writing-to-stem-ecosystem-checkout.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Redirect publish.project()'s per-partner projection to data/

## Description

`export/publish.py`'s `project()` reads every partner's full
accumulated per-partner log (`export/partner_log.py`, stored under
`SCRAPE_CACHE_DIR`, never under `site_dir`) and projects a richer,
self-describing current/past split than the flat `opportunities.json`:
`{site_dir}/public/data/partners.json` plus per-partner
`partners/<slug>/events.json` and `partners/<slug>/past-events.json`.
This predates sprint 020's dual-write pattern by eleven sprints and was
never given an `own_data_dir` equivalent.

Redirect its write to `own_data_dir`, using the exact same
`{own_data_dir}/partners.json` + `{own_data_dir}/partners/<slug>/
{events,past-events}.json` shape it already writes today, just at a
different root. Its `site_dir` parameter **stays** — it still resolves
the default `partners_path` (the `partners.json` *read*, unaffected by
this ticket). See sprint.md's Design Rationale ("redirect ... to
`own_data_dir` rather than deleting it or moving its logic into
stem-ecosystem") for why this is the resolution, not the other two
options considered.

## Acceptance Criteria

- [ ] `project()` gains an `own_data_dir` parameter (default:
      `config.get_own_data_dir()`, matching every other export
      function's convention).
- [ ] `project()` writes `{own_data_dir}/partners.json` and, per
      partner, `{own_data_dir}/partners/<slug>/events.json` and
      `{own_data_dir}/partners/<slug>/past-events.json`. It never
      writes anywhere under `{site_dir}/...`.
- [ ] `project()`'s `site_dir` parameter is unchanged in role — still
      resolves the default `partners_path`
      (`{site_dir}/src/data/partners.json`) when `partners_path` is not
      given explicitly.
- [ ] `cli.py`'s existing call to `publish.project(site_dir=...,
      partners_path=...)` continues to resolve `partners_path` from
      `site_dir` exactly as today (unchanged read); no new
      `own_data_dir` argument is required at the call site if
      `project()`'s default already resolves correctly, but pass it
      explicitly if that's clearer.
- [ ] `own_data_dir` is created automatically if missing, matching every
      other export function's convention (`site_dir`'s `src/data` stays
      the one exception that must already exist, per `partners_path`'s
      read requirement).
- [ ] The existing `_to_opportunity()` field-tolerance behavior (a log
      line recorded before a field existed on `Opportunity` falls back
      to that field's dataclass default) is unchanged.
- [ ] `uv run pytest -q` is green.

## Implementation Plan

**Approach**: this function's *read* side (accumulated `.jsonl` log
under `SCRAPE_CACHE_DIR`, curated `partners.json` under `site_dir`) is
completely untouched by this ticket — only the *write* target moves.

1. `export/publish.py`: add `own_data_dir: str | Path | None = None` to
   `project()`'s signature; resolve
   `resolved_own_data_dir = Path(own_data_dir) if own_data_dir is not
   None else get_own_data_dir()` (import `get_own_data_dir` alongside
   the existing `get_site_dir`/`get_scrape_cache_dir` imports).
2. Change every write below `data_dir = resolved_site_dir / "public" /
   "data"` to instead target `resolved_own_data_dir` directly (no
   `public`/`data` subpath — `own_data_dir` writes are flat, matching
   every other sprint-020 export module's convention: `{own_data_dir}/
   partners.json`, `{own_data_dir}/partners/<slug>/events.json`,
   `{own_data_dir}/partners/<slug>/past-events.json`).
3. Update the `if not resolved_site_dir.is_dir(): raise ...` guard —
   this was checking `site_dir` because it used to be the write target;
   now that `site_dir` is read-only (via `partners_path`), reconsider
   whether this guard belongs on `resolved_own_data_dir`'s writability
   instead (mirroring every other export function's "own_data_dir is
   created if missing, never a hard precondition" convention), while
   keeping some form of loud failure if `partners_path` itself can't be
   read.
4. Update the module's docstring (the "build-time projection into the
   published `public/data/` tree" framing) to describe writing into
   partner-scrape's own `data/` tree for stem-ecosystem (or any
   consumer) to pull from at its own build time, instead.

**Files to modify**: `export/publish.py`.

**Testing plan**: update `tests/test_export_publish.py` to pass an
explicit `tmp_path` as `own_data_dir` (matching this project's hermetic
convention) and assert the published `partners.json`/per-partner files
land there, never under the `tmp_path` passed as `site_dir`. Keep every
existing assertion about the *read* side (accumulated log collapsing,
current/past split, field-tolerance) unchanged — only the write-location
assertions change. Update `tests/test_cli.py`'s and
`tests/test_cli_teams.py`'s `publish.project(...)` wiring tests (they
currently assert `publish.project` is called correctly, not its own
behavior) to reflect the new `own_data_dir`-aware call, if the call
site changes at all. Run
`uv run pytest tests/test_export_publish.py tests/test_cli.py -q`.

**Documentation updates**: `export/publish.py`'s module docstring (see
step 4 above); its "Self-describing, not just correct" section's
framing of the consumer no longer needs "no other data source" phrased
around `stem-ecosystem` specifically.
