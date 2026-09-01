---
id: '002'
title: Add credential_failures to teams.json's meta payload
status: done
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

- [x] `teams/export.py`'s `_build_meta()` accepts a new
      `credential_failures: list[str] | None` parameter (or
      equivalent), defaulting to `None`/empty, and writes a
      `"credential_failures"` key into its returned dict: the sorted,
      de-duplicated list of league codes passed in (`[]` when none).
- [x] `export_teams()` accepts a new `credential_failures` parameter
      (default `()`), threading it into its `_build_meta()` call.
      Every existing call site that omits it keeps working unchanged.
- [x] `run_teams()` passes its per-run credential-failure league list
      (collected in ticket 001) into `export_teams()`'s new parameter.
- [x] `teams.json`'s `meta.credential_failures` is present and correct
      on: a credential-failure fixture run (lists the affected
      league(s)), and a clean fixture run (`[]`) — both in
      `dry_run=True` and real-write paths (all three write targets:
      `src/data/teams.json`, `public/data/teams.json`,
      `own_data_dir/teams.json`).
- [x] `teams/export.py`'s module docstring's documented JSON contract
      example is updated to show the new `credential_failures` key.
- [x] `teams/DESIGN.md`'s relevant sections (the "load-bearing in
      production" note about per-source failure isolation, if it still
      reads as fully current) are updated or annotated to reflect that
      an active alert/payload signal now exists alongside the
      per-source log line.
- [x] Full existing test suite (`uv run pytest`) stays green, including
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

## Notes

Implementation: `_build_meta()` (`partner_scrape/teams/export.py`) gained
`credential_failures: list[str] | None = None`, writing
`"credential_failures": sorted(set(credential_failures)) if
credential_failures else []` — always present, sorted, de-duplicated.
`export_teams()` gained `credential_failures: Iterable[str] = ()`,
passed straight into its `_build_meta(team_list, list(credential_failures))`
call (`Iterable`, not `list`, so a generator/tuple works too, matching
the existing `teams: Iterable[Team]` parameter's own convention).
`run_teams()`'s final `return` now reads:

```python
return export_teams(
    teams,
    site_dir=site_dir,
    dry_run=dry_run,
    credential_failures=[league for _, _, league, _ in credential_failures],
)
```

reusing ticket 001's own `credential_failures: list[tuple[source_id,
adapter_type, league, message]]` local variable — no new collection
needed. Module docstrings updated in both `export.py` (JSON contract
example, `_build_meta()`'s and `export_teams()`'s own docstrings) and
`pipeline.py` (a new paragraph after ticket 001's, plus a note in
`run_teams()`'s own docstring). `teams/DESIGN.md`'s "load-bearing in
production" bullet (Sec. 6, Open Questions/Known Limitations) is
annotated in place with a "**Sprint 023**" addendum describing both
tickets' two-layer (log + payload) alerting; the doc's top-of-file
"Last reviewed" header was left untouched, matching this file's own
established convention of not bumping that header on every touching
ticket (sprints 016/018/019/021 all touched `DESIGN.md`'s body without
moving it either).

**AC bullet 4 (all three write targets)**: rather than writing three
redundant read-back tests, the new pipeline-level tests read back only
`src/data/teams.json` (matching
`test_missing_tba_key_writes_a_valid_teams_json_to_disk`'s existing
convention exactly) and rely on the pre-existing, unmodified
`TestPublicDataPublish`/`TestOwnDataDirPublish` regression tests in
`tests/teams/test_export.py`, which already prove all three write
targets are byte-identical copies of the same `serialized` string for
*any* payload — a guarantee this ticket's change doesn't touch (the new
key is computed once, inside `_build_meta()`, before that string is
ever produced). Verified this reasoning still holds after the change:
full suite green, byte-identity tests unaffected.

**Test-hermeticity fix in `TestTbaFailureIsolation`**: extending those
tests with an exact `credential_failures == ["FRC"]` assertion exposed
a latent gap — none of that class's tests set `ROBOTEVENTS_KEY`, so
whether `"VEX"` also appeared depended on whatever the ambient
environment happened to have set (this session has neither key set, so
it wasn't caught until the new assertion made it visible). Fixed by
adding `monkeypatch.setenv("ROBOTEVENTS_KEY", "fixture-test-key")` to
each of that class's four exact-value tests (mirroring
`TestRobotEventsFailureIsolation`'s own existing convention of setting
`TBA_KEY` to isolate its target failure) — RobotEvents then raises a
plain `KeyError` from the fixture Fetcher (an unregistered probe URL),
not `config.CredentialError`, so it's isolated as an ordinary failure
and never contributes a spurious `"VEX"`, regardless of the real
ambient `ROBOTEVENTS_KEY` state. No fixture data/response registration
needed, and `total`/`by_league` assertions are unaffected (RobotEvents
still contributes zero teams either way).

New tests added: `tests/teams/test_export.py`'s
`TestCredentialFailuresMeta` (5 tests: sort/dedupe, omitted-default,
empty-list, `export_teams()` threading, `export_teams()` omitted);
`tests/teams/test_pipeline.py` extends
`TestTbaFailureIsolation`/`TestRobotEventsFailureIsolation` (credential_failures
assertions on the existing missing-key/401 dry-run tests, the existing
missing-key real-write tests, plus two new real-write tests for the
401 cases — `test_tba_401_writes_a_valid_teams_json_to_disk` and
`test_robotevents_401_writes_a_valid_teams_json_to_disk`) and adds a
new `TestCredentialFailuresMeta` class (2 tests: a fully-successful
dry-run and real-write run, both asserting `credential_failures == []`,
reusing `TestRobotEventsIntegration`'s all-three-keyed-sources-succeed
fixture).

**Test results**: `uv run pytest tests/teams/test_export.py
tests/teams/test_pipeline.py -q` → 89 passed. Full suite `uv run
pytest -q` → 1965 passed, 0 failed, 0 regressions.

**Live run** (continuing ticket 001's recorded live run, same
credential state: `TBA_KEY`/`ROBOTEVENTS_KEY` both genuinely unset this
session, `dotconfig load` not attempted per instructions). Since the
CLI's own stdout only prints a team count, not the full `meta` dict, a
small script (`run_teams(fetcher=PoliteFetcher(), dry_run=True)`,
otherwise identical to `cli.py`'s `_run_teams()` handler) was used to
print `payload["meta"]` directly — no disk writes anywhere
(`dry_run=True`), so no throwaway `--site-dir`/`--own-data-dir` was
needed. Invoked as:

```
SCRAPE_CACHE_DIR=/Volumes/Cache/stem-ecosystem uv run python <script>
```

(`SCRAPE_CACHE_DIR` required only because sponsor/description
extraction's caches default to it — unrelated to this ticket, same as
ticket 001's own invocation.) Observed output:

```json
{
  "generated": "2026-09-01T03:51:54Z",
  "total": 200,
  "by_league": {"FLL": 48, "FTC": 152},
  "out_of_region": 6,
  "by_location_precision": {"city": 104, "zip": 7, "school": 85, "none": 4},
  "credential_failures": ["FRC", "VEX"]
}
```

Matches the ticket's own expectation exactly — `credential_failures ==
["FRC", "VEX"]`, sorted, one entry per credentialed source that failed
this run (TBA/FRC, RobotEvents/VEX), consistent with ticket 001's own
recorded aggregate-warning live run.
