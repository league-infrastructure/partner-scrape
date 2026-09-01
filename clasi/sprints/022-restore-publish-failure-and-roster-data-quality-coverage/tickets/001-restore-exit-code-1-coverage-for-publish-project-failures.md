---
id: '001'
title: Restore exit-code-1 coverage for publish.project() failures
status: in-progress
use-cases:
- SUC-024
depends-on: []
github-issue: ''
issue: 47-restore-publish-failure-exit-code-coverage.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Restore exit-code-1 coverage for publish.project() failures

## Description

Sprint 019 ticket 001 deleted
`tests/test_cli.py::test_mirror_still_runs_when_publish_project_raises`
for the right reason — the `MIRROR_SITE_DIRS` mechanism it exercised is
gone. But that one test also incidentally covered a distinct, still-live
property from sprint 018 ticket 010: `cli.py`'s `main()` returns exit
code 1 (not 0), and logs the failure via `logger.exception(...)`, when
`publish.project()` raises. Reading `partner_scrape/cli.py` (lines
569–617) confirms this behavior is fully intact today; no other test in
`tests/test_cli.py` covers it — `TestPublishWiring.
test_exit_code_stays_zero_when_publish_project_succeeds` only proves the
*success* path stays 0.

Add one small, focused test restoring this coverage, with no
mirror-related assertions (that framing no longer applies).

**Where to add it**: `tests/test_cli.py`'s existing `TestPublishWiring`
class (the class already covers `publish.project()`'s wiring — this is
one more case in the same class, not a new one). Follow that class's
existing pattern exactly: `monkeypatch.setattr(cli, "run", lambda
**kwargs: [])` (or a small non-empty payload — doesn't matter which)
and `monkeypatch.setattr(cli.publish, "project", <a function that
raises>)`. The module-level `_cache_dir` autouse fixture already stubs
`cli.publish.project` to a no-op success by default (see its own
docstring: "`TestPublishWiring` below un-stubs it to test the wiring
itself") — this new test does the same un-stubbing `TestPublishWiring`'s
other tests already do, just raising instead of returning a payload.

Use `caplog` (this project's established convention — see
`tests/test_adapters_base.py`, `tests/test_adapters_ical.py`) to assert
the failure was actually logged, not just that the exit code changed.
`cli.py`'s logger is `logging.getLogger("partner_scrape.cli")`
(`__name__`-derived) — set `caplog.at_level(logging.ERROR,
logger="partner_scrape.cli")` (or a broader level covering `ERROR`;
`logger.exception()` logs at `ERROR`) around the `cli.main(...)` call
and assert on `caplog.text` or `caplog.records`.

## Acceptance Criteria

- [x] A new test in `tests/test_cli.py`'s `TestPublishWiring` class
      monkeypatches `cli.run` to a stub and `cli.publish.project` to
      raise an exception.
- [x] The test asserts `cli.main(...)` (a non-`--dry-run` invocation,
      since `publish.project()` is skipped entirely under `--dry-run`)
      returns exit code `1`.
- [x] The test asserts (via `caplog`) that the failure was logged —
      at minimum, that a log record at `ERROR` level was emitted by
      `partner_scrape.cli` during the call.
- [x] The test contains no assertion referencing `MIRROR_SITE_DIRS` or
      any other mirror-mechanism concept — that framing is gone and
      must not be reintroduced.
- [x] No production code in `partner_scrape/cli.py` changes — this
      ticket is test-only; the behavior it covers already exists.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_cli.py` (full
  file — confirm no existing `TestPublishWiring` test regresses), then
  the full suite (`uv run pytest`) before calling this ticket done.
- **New tests to write**: exactly one test, as described above — restore
  the exit-code-1 + logged-error coverage `test_mirror_still_runs_when_
  publish_project_raises` used to provide, without its mirror framing.
- **Verification command**: `uv run pytest`
