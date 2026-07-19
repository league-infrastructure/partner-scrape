---
id: '001'
title: 'Headless Fetcher: PlaywrightFetcher as an optional, injectable Fetcher'
status: done
use-cases:
- SUC-015
depends-on: []
github-issue: ''
issue: 10-js-rendered-site-support.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Headless Fetcher: PlaywrightFetcher as an optional, injectable Fetcher

## Description

Build `PlaywrightFetcher`, a new `Fetcher` implementation
(`partner_scrape/fetch/headless.py`) that retrieves a URL's fully
client-rendered HTML via a real headless browser, and drops into
`PoliteFetcher`'s existing `fetcher=` constructor parameter with zero
changes to `fetch/cache.py`, `fetch/robots.py`, or `fetch/throttle.py`
(see sprint.md's Architecture > Headless Fetcher, Design Rationale).

This ticket is entirely self-contained at the Fetch layer — it does not
wire headless selection into Pipeline or the Registry (ticket 005's job)
and does not touch any Adapter (headless fetching is adapter-agnostic by
design). It also does not register against a live Wix site; per
sprint.md's Scope, bulk Wix registration is a later operational
follow-up. This ticket proves the mechanism via fixtures.

**Critical constraint, non-negotiable**: `playwright` is declared as an
optional dependency group (`pyproject.toml`:
`[project.optional-dependencies] headless = ["playwright>=1.40"]`), NOT
a base dependency. The real `import playwright` call must be deferred
into the code path that constructs a real (non-injected) browser/page —
never at module import time — so that `partner_scrape.fetch` (and this
module specifically) imports cleanly, and this ticket's own unit tests
run, with `playwright` absent entirely. Tests inject a fixture
`page_factory` double; they must never trigger the real import.

## Acceptance Criteria

- [x] `PlaywrightFetcher` implements `Fetcher.get(url, headers=None) ->
      FetchResponse` (the existing protocol in `fetch/fetcher.py`, no
      changes to that protocol).
- [x] `PlaywrightFetcher.__init__` accepts an injectable `page_factory`
      (or equivalent seam) defaulting to a lazily-constructed real
      Playwright browser/page — the real `import playwright` happens
      only inside that default path, not at module level.
- [x] Given a fixture `page_factory` double that returns canned rendered
      HTML and a navigation response with a given status, `get()`
      returns a `FetchResponse` whose `body` is that HTML and whose
      `status` is taken from the real navigation response — not a
      hardcoded `200` (this matters: `PoliteFetcher`'s cache-write logic
      branches on `200 <= status < 300`, so a hardcoded status would
      silently break caching/error-handling parity with every other
      `Fetcher`).
- [x] `get()` applies a bounded wait (network-idle, with a fixed timeout
      constant — no per-source tuning this ticket, per sprint.md's Open
      Question 4) before reading rendered content.
- [x] `PoliteFetcher(fetcher=PlaywrightFetcher(...))` is exercised in a
      test through the same robots.txt / rate-limit / cache code path
      `UrllibFetcher` already is (reuse or closely mirror
      `test_fetch_cache.py`'s existing `PoliteFetcher` test pattern with
      the fixture `PlaywrightFetcher` substituted in) — zero changes
      required to `fetch/cache.py`, `fetch/robots.py`, or
      `fetch/throttle.py` to make this pass.
- [x] This module and its tests import and run with `playwright` fully
      uninstalled (verify by running this ticket's test file in an
      environment/venv without the `headless` optional group installed,
      or by asserting no `playwright` entry appears in
      `sys.modules` after running the fixture-backed tests).
- [x] `pyproject.toml` gains `[project.optional-dependencies] headless =
      ["playwright>=1.40"]`; the base `dependencies` list is unchanged.
- [ ] (Optional, if included) A real-browser smoke test exists, is
      decorated `@pytest.mark.skipif` (or equivalent) to skip unless an
      explicit environment variable (e.g. `RUN_BROWSER_SMOKE_TEST`) is
      set, and is excluded from the default `pytest` run.
      **Not included** — not listed in this ticket's own "New tests to
      write", and out of scope per the sprint's own precedent (bulk Wix
      registration, where a real browser would actually be exercised,
      is explicitly deferred to operational follow-up).
- [x] A source flagged for headless fetching when `playwright` isn't
      installed produces a clear, actionable error (names the missing
      optional dependency group) rather than a bare `ImportError` —
      verify with a unit test that forces the deferred-import path to
      fail.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_fetch_cache.py`
  (confirm `PoliteFetcher`'s existing behavior is unaffected).
- **New tests to write**: `tests/test_fetch_headless.py` — unit tests for
  `PlaywrightFetcher.get()` against a fixture `page_factory`/browser
  double (canned HTML + status, a non-200 navigation response, a
  timeout/error case), a `PoliteFetcher(fetcher=PlaywrightFetcher(...))`
  integration test reusing the existing cache/robots/throttle test
  pattern, a test asserting no real `playwright` import occurs when only
  the fixture double is used, and a test for the actionable-error path
  when the deferred import fails.
- **Verification command**: `uv run pytest` (must pass with `playwright`
  not installed in the environment running the default suite).
