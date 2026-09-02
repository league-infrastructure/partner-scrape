---
id: "004"
title: "Fetcher gains POST support for Workday's CXS API"
status: open
use-cases: [SUC-057]
depends-on: []
github-issue: ""
issue: 31-ats-adapters-workday-neogov-smartrecruiters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fetcher gains POST support for Workday's CXS API

## Description

Foundation ticket for ticket 005 (Workday adapter). Extend
`partner_scrape/fetch/fetcher.py`'s `Fetcher` Protocol with a second
method, `post(url, body, headers=None) -> FetchResponse`, alongside
the existing `get()`. Implement it on `UrllibFetcher` (real transport)
and `PoliteFetcher` (robots + throttle composition, deliberately no
on-disk caching). This is this codebase's first non-`GET` network
call — see `design/fetch-DESIGN.md`'s sprint 031 section for the full
Design Rationale (why extend the Protocol rather than have
`workday.py` open its own `urllib` call; why POST responses are not
cached).

This ticket contains no adapter-specific logic — it is purely the
`fetch/` subsystem's new capability, testable and mergeable
independently of Workday's own field-mapping/classification code
(ticket 005).

## Acceptance Criteria

- [ ] `Fetcher` Protocol (`fetch/fetcher.py`) gains
      `post(url: str, body: dict, headers: dict[str, str] | None =
      None) -> FetchResponse`.
- [ ] `UrllibFetcher.post()` sends `body` JSON-encoded
      (`Content-Type: application/json`), reusing `get()`'s exact
      transport-error handling: an `HTTPError` normalizes into a
      `FetchResponse` with that status; a connection-level failure
      (`OSError`/`http.client.HTTPException`/`UnicodeError`) returns
      `TRANSPORT_ERROR_STATUS` rather than raising.
- [ ] `PoliteFetcher.post()` (`fetch/cache.py`) applies the same
      robots.txt check and per-domain `Throttle.wait()` call `get()`
      already applies, then delegates to `self.fetcher.post(...)`.
- [ ] `PoliteFetcher.post()` never reads from or writes to the on-disk
      response cache — confirmed by a test asserting no cache file is
      created for a POST call, and that two POSTs to the same URL with
      different bodies both reach the underlying `Fetcher` (never
      served from a stale cached entry).
- [ ] `get()`'s signature, behavior, and every existing caller/test
      double are unaffected — no existing `Fetcher` double is required
      to implement `post()` unless its own test exercises it.
- [ ] Hermetic unit tests only — no live network call.
- [ ] Full test suite (2316+ baseline) stays green.

## Implementation Plan

**Approach**: Add `post()` to the `Fetcher` Protocol in
`fetch/fetcher.py` right alongside `get()`. `UrllibFetcher.post()`
builds an `urllib.request.Request(sanitize_url(url), data=json.dumps(
body).encode("utf-8"), headers={"Content-Type": "application/json",
"User-Agent": self.user_agent, **(headers or {})}, method="POST")` and
reuses the exact try/except structure `get()` already has (do not
duplicate logic differently — extract a small shared helper only if it
turns out cleaner than two parallel methods; either is acceptable,
prefer whichever keeps the diff smallest). `PoliteFetcher.post()`
composes `is_allowed()`/`self.throttle.wait()` exactly like `get()`
but skips `read_cache_entry`/`conditional_headers`/`write_cache_entry`
entirely (see `design/fetch-DESIGN.md`'s Design Rationale for why).

**Files to create/modify**:
- `partner_scrape/fetch/fetcher.py` (`Fetcher` Protocol, `UrllibFetcher`)
- `partner_scrape/fetch/cache.py` (`PoliteFetcher`)
- `partner_scrape/fetch/__init__.py` — no export change expected
  (`Fetcher`/`UrllibFetcher`/`PoliteFetcher` are already exported;
  confirm no new symbol needs adding)
- `tests/test_fetch_fetcher.py` (or equivalent existing file) — new
  `post()` tests for `UrllibFetcher`
- `tests/test_fetch_cache.py` (or equivalent existing file) — new
  `post()` tests for `PoliteFetcher`

**Testing plan**:
- **Existing tests to run**: `uv run pytest` (full suite — confirm
  every existing `Fetcher` test double and every `get()`-based test
  still passes unchanged).
- **New tests to write**: `UrllibFetcher.post()` sends the right
  method/headers/body against a fixture HTTP handler or mocked
  `urlopen`; `PoliteFetcher.post()` respects `respect_robots`/
  `rate_limit_seconds` identically to `get()`; `PoliteFetcher.post()`
  never touches the on-disk cache (two same-URL, different-body POSTs
  both reach the underlying fetcher; no cache file appears under a
  `tmp_path` cache dir).
- **Verification command**: `uv run pytest`

**Documentation updates**: None beyond this ticket's own Notes — the
design write-up already lives in this sprint's `design/fetch-DESIGN.md`
overlay, applied to the canonical `fetch/DESIGN.md` at sprint close.
