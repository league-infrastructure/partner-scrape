---
id: '002'
title: Add credential_failures to teams.json's meta payload
status: in-progress
use-cases:
- SUC-027
depends-on:
- '001'
github-issue: ''
issue: 62-missing-source-credential-degrades-silently-past-cli-exit-code.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add credential_failures to teams.json's meta payload

## Description

Ticket 001 makes a credential failure loud in the run log. But the log
is only visible to whoever captures that specific run — `teams.json`
is the artifact that actually ships (three write targets, per
`export.py`'s own docstring) and gets read downstream (this is exactly
what the stem-ecosystem peer's cross-check, one of issue 62's two
rediscoveries, was doing). The existing passive signal
(`meta.by_league`'s absence of a failed league's key) requires a
consumer to already know to check for a missing key in a dict with no
declared complete key set — issue 62's own text calls this "a much
weaker guarantee than an active alert."

This ticket threads ticket 001's collected credential-failure league
list through `export_teams()` into `_build_meta()`, publishing an
explicit, always-present `credential_failures` key (sorted, unique
league codes; `[]` on a clean run) — see sprint.md's Architecture
(Design Rationale: "extend `_build_meta()`'s payload... proportionate
to the gap, unlike exit-code plumbing") for why this is the right size
of fix, and why a new exit code was deliberately *not* chosen instead.

## Acceptance Criteria

- [ ] `teams/export.py`'s `_build_meta()` accepts a new
      `credential_failures: list[str] | None` parameter (or
      equivalent), defaulting to `None`/empty, and writes a
      `"credential_failures"` key into its returned dict: the sorted,
      de-duplicated list of league codes passed in (`[]` when none).
- [ ] `export_teams()` accepts a new `credential_failures` parameter
      (default `()`), threading it into its `_build_meta()` call.
      Every existing call site that omits it keeps working unchanged.
- [ ] `run_teams()` passes its per-run credential-failure league list
      (collected in ticket 001) into `export_teams()`'s new parameter.
- [ ] `teams.json`'s `meta.credential_failures` is present and correct
      on: a credential-failure fixture run (lists the affected
      league(s)), and a clean fixture run (`[]`) — both in
      `dry_run=True` and real-write paths (all three write targets:
      `src/data/teams.json`, `public/data/teams.json`,
      `own_data_dir/teams.json`).
- [ ] `teams/export.py`'s module docstring's documented JSON contract
      example is updated to show the new `credential_failures` key.
- [ ] `teams/DESIGN.md`'s relevant sections (the "load-bearing in
      production" note about per-source failure isolation, if it still
      reads as fully current) are updated or annotated to reflect that
      an active alert/payload signal now exists alongside the
      per-source log line.
- [ ] Full existing test suite (`uv run pytest`) stays green, including
      any existing test asserting `teams.json`'s exact `meta` key set
      (update it to include the new key rather than leaving it
      failing).

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/test_export.py
  tests/teams/test_pipeline.py` plus the full suite (`uv run pytest`).
- **New tests to write** (hermetic, fixture-driven, no real
  network/API calls):
  - `tests/teams/test_export.py`: `_build_meta()`/`export_teams()`
    unit tests asserting `credential_failures` is correctly populated
    (sorted, de-duplicated) when passed a non-empty list, and is `[]`
    when omitted/empty.
  - `tests/teams/test_pipeline.py`: extend the same credential-failure
    fixture scenarios ticket 001 added `caplog` assertions for
    (TBA/RobotEvents, missing-key and 401 cases) with an additional
    assertion on `payload["meta"]["credential_failures"]`, both for
    `dry_run=True` and a real-write run (mirroring
    `test_missing_tba_key_writes_a_valid_teams_json_to_disk`'s
    existing pattern of reading the written file back off disk).
  - A clean-run test (no credential failures) asserting
    `meta["credential_failures"] == []`.
- **Live run** (required before sprint close, continuing ticket 001's
  recorded live run): confirm the real, current-credential-state run's
  `teams.json` carries the expected `meta.credential_failures` value
  (empty if this machine's credentials are currently valid; naming the
  affected league(s) otherwise) — recorded as supplementary evidence
  per this project's sprints 020-022 convention.
- **Verification command**: `uv run pytest`
