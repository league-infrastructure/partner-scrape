---
id: '001'
title: Add CredentialError and an aggregate credential-failure alert to run_teams()
status: in-progress
use-cases:
- SUC-027
depends-on: []
github-issue: ''
issue: 62-missing-source-credential-degrades-silently-past-cli-exit-code.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add CredentialError and an aggregate credential-failure alert to run_teams()

## Description

`teams/pipeline.py`'s `run_teams()` isolates every per-source failure
the same way — logged at ERROR with a traceback, then skipped, run
continues (ticket 011-002/011-003/016-005's design). That is the right
response to a transient failure (a bad page, a flaky network blip),
but a missing/invalid `TBA_KEY`/`ROBOTEVENTS_KEY` is structural: it
will recur on every run until an operator fixes it, and today it is
indistinguishable, in both the log and `teams.json`, from a one-off
scrape hiccup or a genuine empty result (issue 62).

Verified against the current code: `config.get_tba_api_key()`/
`get_robotevents_api_key()` raise a bare `RuntimeError` when the env
var is unset, and `TBASource.discover()`/`VexTeamSource.discover()`
each raise a bare `RuntimeError` for a 401 *and* for every other probe
failure (non-200 status, unparseable JSON, an invalid page count) —
all indistinguishable by exception type today, only by message text.
This ticket adds a dedicated `CredentialError(RuntimeError)` so the
credential-specific cases can be caught and reported distinctly,
without touching the non-credential raise sites.

See sprint.md's Architecture (Design Rationale: "a dedicated
`CredentialError` type, not message-substring matching"; "mirror
`zero_yield`'s shape, do not import `observability/`") for the full
reasoning behind this approach.

## Acceptance Criteria

- [ ] `partner_scrape/config.py` defines `CredentialError(RuntimeError)`
      — a plain marker subclass, no new behavior.
- [ ] `config.get_tba_api_key()` and `config.get_robotevents_api_key()`
      raise `CredentialError` (not bare `RuntimeError`) when their env
      var is unset/empty — message text unchanged.
- [ ] `teams/sources/tba.py`'s `TBASource.discover()` raises
      `config.CredentialError` (not `RuntimeError`) specifically for
      the `response.status == 401` branch — message text unchanged.
      Every other raise in `discover()` (non-200 non-401, unparseable
      JSON, invalid `max_team_page`) stays plain `RuntimeError`.
- [ ] `teams/sources/robotevents.py`'s `VexTeamSource.discover()` gets
      the identical treatment for its own 401 branch, and only that
      branch.
- [ ] `teams/pipeline.py` adds a private `_SOURCE_LEAGUES: dict[str,
      str]` lookup (`adapter_type -> League`: `{"ftcscout": "FTC",
      "tba": "FRC", "static_roster": "FLL", "robotevents": "VEX"}`),
      matching `_TEAM_SOURCES`'s existing "private lookup local to the
      one caller that needs it" convention — not a new public registry.
- [ ] `run_teams()`'s per-source loop catches `CredentialError`
      *before* the existing `except Exception` branch, logs the same
      per-source ERROR + traceback it does today (unchanged message),
      and additionally records `(source_id, adapter_type, league,
      str(exc))` for this failure before `continue`-ing.
- [ ] After the per-source loop completes, if any credential failures
      were recorded, `run_teams()` logs exactly one aggregate
      `logger.warning` (never more than one call, matching
      `_check_sunset_seasons()`'s existing convention) naming every
      affected league and source. No such warning is logged when no
      credential failures occurred.
- [ ] `_check_sunset_seasons()` is untouched — no interaction with the
      new alert logic.
- [ ] `run_teams()`'s own module/function docstring gains one
      paragraph narrating this addition, matching the file's existing
      per-sprint/per-ticket docstring convention (see the many prior
      examples already in that docstring).
- [ ] `config.py`'s and each source's own docstrings are updated where
      they currently describe the raised exception as `RuntimeError`
      for the credential-specific cases.
- [ ] Full existing test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/test_pipeline.py
  tests/teams/test_sources_tba.py tests/teams/test_sources_robotevents.py
  tests/test_config.py` (or the project's equivalent config test file,
  if present) plus the full suite (`uv run pytest`) to confirm no
  regressions — `CredentialError is-a RuntimeError`, so every existing
  `except RuntimeError`/`except Exception` assertion should keep
  passing unmodified.
- **New tests to write** (hermetic, fixture-driven, no real
  network/API calls — matching this project's established
  `tests/teams/test_pipeline.py` convention):
  - Extend `TestTbaFailureIsolation` and `TestRobotEventsFailureIsolation`
    (`tests/teams/test_pipeline.py`) with `caplog`-based assertions:
    the missing-key case and the 401 case for each of TBA/RobotEvents
    (4 scenarios total) each produce exactly one aggregate warning
    naming the correct league.
  - A companion test proving a source that completes with a genuine
    empty result (no exception) does not produce the aggregate
    warning.
  - A companion test proving a source raising a plain, non-credential
    `RuntimeError` (reuse/adapt the existing "erroring source" fixture
    near `test_unrecognized_adapter_type_does_not_raise_and_yields_
    zero_teams`) does not produce the aggregate warning — proving the
    new alert is specific to `CredentialError`, not a broadened
    catch-all.
  - A unit test on `config.get_tba_api_key()`/`get_robotevents_api_key()`
    asserting the raised exception is `CredentialError` (not just any
    `RuntimeError`).
  - A unit test on each source's `discover()` asserting the 401 branch
    specifically raises `CredentialError`, and that its other raise
    branches (non-200 non-401, bad JSON, bad page count) still raise
    plain `RuntimeError`.
- **Live run** (required before sprint close, not a substitute for the
  above): run the real `teams` command against this machine's current
  `.env` and record the actual log output (whether or not the new
  aggregate warning fires, given real current credential state) as
  supplementary evidence, per this project's sprints 020-022
  live-verification convention.
- **Verification command**: `uv run pytest`
