---
id: '003'
title: TBA source and cross league merge
status: open
use-cases:
- SUC-002
depends-on:
- '002'
github-issue: ''
issue: robot-teams-scrape-locate-and-publish-san-diego-first-teams.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# TBA source and cross league merge

## Description

Add the second live source — The Blue Alliance (FRC, 59 San Diego
teams, keyed) — and resolve cross-league organizational identity
between it and ticket 001's FTCScout teams. This is the issue's
increment 2. Adds `config.py`'s TBA credential accessors, the TBA
`TeamSource` implementation, and `merge.py`. Extends
`teams.pipeline.run_teams()` to run both sources and merge their
output before export. Implements SUC-002.

A hard requirement here, called out in `sprint.md`'s Migration
Concerns: `TBA_KEY` is not yet in the scheduled workflow's GitHub
Actions secrets. A TBA fetch failure (401, timeout, etc.) **must** be
isolated the same way `pipeline.run()` isolates a per-source failure —
logged and skipped, never raised — so a missing credential degrades to
FTC-only `teams.json` rather than failing the whole `teams` run.

## Acceptance Criteria

- [ ] `partner_scrape/config.py` gains `get_tba_api_key()` and
      `get_tba_url()`, reading `TBA_KEY`/`TBA_URL`, mirroring
      `get_leaguesync_api_key()`/`get_leaguesync_url()` exactly —
      including stripping surrounding quotes from the SOPS-decrypted
      secret. `config.py` remains the only module reading
      `os.environ`.
- [ ] `partner_scrape/teams/sources/tba.py` implements `TeamSource`
      against The Blue Alliance's `/api/v3/teams/{page}` (paginated,
      `X-TBA-Auth-Key` header via `config.get_tba_api_key()`), filtered
      to CA + San Diego cities, producing 59 `Team` objects with
      `league="FRC"` and (per the issue's measured coverage) school
      name (91%), ZIP (83%), and website (72%) where present.
- [ ] `partner_scrape/teams/registry/frc-sd.toml` registers the TBA
      source.
- [ ] `partner_scrape/teams/merge.py` links a `Team`'s
      `org_key`/`sibling_team_ids` by
      `normalize.partners.normalize_org_name`-normalized organization
      — **reused directly, not reimplemented**. A test fixture covering
      one of the seven known dual-program organizations (e.g. Canyon
      Crest Academy) confirms its FTC and FRC teams cross-reference via
      `sibling_team_ids`.
- [ ] `merge.py` never groups `Family/Community` or empty-organization
      teams into a shared `org_key` — tested explicitly with a
      multi-team `Family/Community` fixture.
- [ ] Team number collisions (e.g. 1622, which exists independently in
      both FTC and FRC) never cause a false merge — tested explicitly.
- [ ] `teams.pipeline.run_teams()` runs FTCScout and TBA, then
      `merge.py`, before export. A simulated `TBA_KEY`-missing or
      TBA-401 fixture run still publishes a 152-team, FTC-only
      `teams.json` (per-source isolation, not a whole-run failure).
- [ ] With TBA fixtures present, `teams.json` carries 59 FRC teams
      (211 total).

## Implementation Plan

**Approach**: `sources/tba.py` follows the same `TeamSource`
implementation shape as `sources/ftcscout.py` (ticket 001) — no shared
extraction code between the two (their payloads share almost no field
names), but the same protocol. Study
`partner_scrape/adapters/leaguesync.py`'s `_auth_headers()` pattern
(read the token fresh per call via `config.get_tba_api_key()`, never
cached on an adapter instance) for the TBA Bearer-style header. In
`pipeline.py`, wrap each source's acquisition in the same per-source
try/except isolation `partner_scrape/pipeline.py`'s
`ThreadPoolExecutor` loop already uses — log and skip on failure,
never let one source's exception abort the whole `run_teams()` call.
`merge.py` operates after both sources have run, before geocoding
(ticket 004) or export.

**Files to create**:
- `partner_scrape/teams/sources/tba.py`
- `partner_scrape/teams/merge.py`
- `partner_scrape/teams/registry/frc-sd.toml`

**Files to modify**:
- `partner_scrape/config.py` — add `get_tba_api_key()`/`get_tba_url()`.
- `partner_scrape/teams/pipeline.py` — add the TBA source and the
  merge step, each with its own failure isolation.
- `partner_scrape/teams/DESIGN.md` — extend with `merge.py`'s identity
  rule and the per-source isolation behavior.

## Documentation

Extend `partner_scrape/teams/DESIGN.md` (from tickets 001/002) with
`merge.py`'s design (why organization name, not team number — already
drafted in the sprint's `design/new-subsystem/teams-DESIGN.md`, verify
it against what you actually build) and the per-source failure
isolation this ticket adds to `pipeline.py`.

## Testing

- **Existing tests to run**: `uv run pytest`.
- **New tests to write**:
  - `tests/teams/test_sources_tba.py` — extraction against a canned TBA
    fixture (`tests/fixtures/teams/tba_teams.json`), CA/SD-city
    filtering, auth header construction.
  - `tests/teams/test_merge.py` — the dual-program organization case,
    the `Family/Community`-never-groups case, the team-number-collision
    case.
  - `tests/teams/test_pipeline.py` (extend ticket 002's) — the
    TBA-failure-isolation case (missing key, simulated 401) still
    yields a valid FTC-only export.
- **Verification command**: `uv run pytest tests/teams/ && uv run
  pytest`
