---
id: '003'
title: 'Fetch and Cache layer: polite HTTP, robots.txt, rate limiting, conditional
  GET'
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
issue: 01-aggregator-engine-foundation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fetch and Cache layer: polite HTTP, robots.txt, rate limiting, conditional GET

## Description

Build the Fetch & Cache module (sprint architecture): polite,
cache-aware retrieval of remote resources. This is infrastructure —
it retrieves and caches raw responses; it does not interpret them
(that's the Adapter Framework's job in ticket 004).

Scope:
- A `Fetcher` protocol (`get(url, headers=None) -> FetchResponse`) with
  a stdlib-based default implementation (`urllib.request` +
  `urllib.robotparser`) — zero new dependency, matching
  `dev/fetch_tec_api.py`'s proven approach (see sprint.md Design
  Rationale for why Scrapy was dropped in favor of this).
- Robots.txt check: before any fetch, confirm the URL is allowed for
  this bot's user-agent; refuse (raise or return a clear
  disallowed-result) if not.
- Per-domain rate limiting: a minimum delay between requests to the
  same domain, read from the source's `acquisition_policy` (registry,
  ticket 002) with a sane default when unset.
- On-disk cache under `Config.SCRAPE_CACHE_DIR`: store raw response
  body, status, headers (etag/last-modified), and fetch timestamp,
  keyed by URL (e.g. domain-sharded directory + hash of the full URL).
- Conditional GET: on a repeat fetch, send `If-None-Match` /
  `If-Modified-Since` from the cached headers; on a `304`, reuse the
  cached body and just bump the fetch timestamp — no re-download, no
  re-store of the body.
- The `Fetcher` must be injectable (constructor/parameter), so tests can
  substitute a fixture-backed fake that returns canned responses —
  no real sockets in any test, ever, per this sprint's test strategy.

## Acceptance Criteria

- [x] A URL disallowed by the target's robots.txt is never fetched (the
      fetch call raises or returns a clear "disallowed" result before
      any request is issued).
- [x] A first fetch of a URL stores the response body + headers +
      timestamp in the on-disk cache under `SCRAPE_CACHE_DIR`.
- [x] A second fetch of the same, unchanged URL sends
      `If-None-Match`/`If-Modified-Since` derived from the cached
      headers.
- [x] Given a fixture `Fetcher` that returns `304 Not Modified` on the
      second call, the cached body is returned and is not re-written to
      disk (only the fetch timestamp updates).
- [x] Per-domain rate limiting enforces at least the configured minimum
      delay between two fetches to the same domain (verified with a
      fake clock/injected sleep, not a real wall-clock wait in tests).
- [x] All of the above is exercised via an injected fixture `Fetcher` —
      no test in this ticket opens a real network socket.

## Implementation Plan

### Approach

Define `Fetcher` as a `typing.Protocol` with one method; ship
`UrllibFetcher` as the real implementation and a
`FixtureFetcher(responses: dict[str, FetchResponse])` in `tests/` (not
shipped in `partner_scrape/`) for tests. Cache key = a stable hash
(e.g. `sha256`) of the normalized URL; store under
`{SCRAPE_CACHE_DIR}/{domain}/{hash}.json` as one JSON file containing
`{url, status, headers, body, fetched_at}` — simple enough to inspect by
hand, which matters for debugging a live source later. Rate limiting:
a small in-memory `{domain: last_fetch_time}` map plus an injectable
clock/sleep function so tests don't actually sleep.

### Files to Create/Modify

- `partner_scrape/fetch/__init__.py`
- `partner_scrape/fetch/fetcher.py` (`Fetcher` protocol,
  `UrllibFetcher`, `FetchResponse`)
- `partner_scrape/fetch/cache.py` (cache read/write, conditional-GET
  header construction)
- `partner_scrape/fetch/robots.py` (robots.txt check wrapper)
- `partner_scrape/fetch/throttle.py` (per-domain rate limiter)
- `tests/test_fetch_cache.py`
- `tests/fixtures/fetch/` (canned response bodies/headers used by the
  in-test `FixtureFetcher`)

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (tickets 001-002's suites).
- **New tests to write**: `tests/test_fetch_cache.py` covering
  robots.txt refusal, first-fetch cache write, conditional-GET header
  construction on a repeat fetch, 304-reuse-without-rewrite, and rate
  limiting with an injected fake clock.
- **Verification command**: `uv run pytest`
