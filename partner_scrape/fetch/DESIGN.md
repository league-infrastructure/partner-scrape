# Fetch

**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable

---

## 1. Purpose

`fetch/` is the only part of the system that talks to the network. It owns polite,
cache-aware retrieval of remote resources: robots.txt compliance, per-domain rate
limiting, on-disk conditional-GET caching, and the choice between a plain HTTP client and
a real headless browser. It is a subsystem because every one of those concerns is
cross-cutting — every adapter and every discovery strategy needs all of them, and none of
them should be re-implemented per caller. It owns *retrieval only*: it never interprets a
response body.

## 2. Orientation

The contract is `fetcher.py`'s `Fetcher` Protocol — one method,
`get(url, headers=None) -> FetchResponse`. Everything in the package either implements it
or composes implementations of it.

- `UrllibFetcher` — the real transport. Stdlib `urllib.request`, no third-party HTTP
  dependency.
- `PlaywrightFetcher` (`headless.py`) — the same contract, backed by a real headless
  browser, for sources whose event listings are client-rendered.
- `PoliteFetcher` (`cache.py`) — the orchestrator and the package's public entry point.
  It *wraps* an injected `Fetcher` and adds, in order: robots.txt check → per-domain
  throttle → on-disk cache lookup with conditional-GET headers → delegate → cache write.

Two supporting modules serve `PoliteFetcher`: `robots.py` (a `RobotFileParser` wrapper
that retrieves robots.txt through the *injected* `Fetcher` rather than opening its own
socket) and `throttle.py` (an in-memory `{domain: last_fetch_time}` map with per-domain
locks).

The cache is one JSON file per URL, domain-sharded:
`{SCRAPE_CACHE_DIR}/{domain}/{sha256(url)}.json`, holding
`{url, status, headers, body, fetched_at}`.

## 3. Constraints and Invariants

- **Nothing outside this package calls `urllib` or opens a socket.** Every remote read in
  the codebase goes through a `Fetcher`. That single seam is what makes the entire
  905-test suite hermetic — tests inject a fixture `Fetcher` and no test touches a real
  network.
- **`UrllibFetcher` returns `TRANSPORT_ERROR_STATUS` (0) on a transport failure; it does
  not raise.** Callers branch on status, uniformly, for both HTTP errors and connection
  failures. Changing this to raise would push try/except into every adapter's `fetch()`
  and every discovery loop — the isolation would then have to be re-established in a
  dozen places instead of being structural here.
- **`playwright` is an optional dependency and its import is deferred into
  `_default_page_factory`.** The import must never happen at module import time or in
  `__init__` — only on the first real `.get()` from a source actually flagged
  `fetch_strategy = "headless"`. The whole test suite runs with `playwright` fully
  uninstalled, and `pipeline.run()` constructs the default headless fetcher eagerly
  enough that an import-time dependency would break every run on machines without it.
- **`Throttle` must be thread-safe per domain and non-blocking across domains.** A single
  instance is shared across `pipeline.run()`'s source-level thread pool. Two concurrent
  `wait()` calls for the *same* domain must not interleave their check-sleep-write
  sequence (both would pass through without actually waiting); two calls for *different*
  domains must not block each other (that would defeat source-level concurrency
  entirely). A per-domain `threading.Lock` gives both — a single global lock would
  serialize the whole pipeline.
- **Politeness is enforced per domain, never per run.** This is what makes source-level
  concurrency safe: eight sources at once is eight different domains, each still limited
  to its own `rate_limit_seconds`.
- **`robots.py` retrieves robots.txt through the injected `Fetcher`, not
  `RobotFileParser.read()`.** The stdlib method opens its own socket, which would make
  the robots check the one unmockable network call in the system.
- **Deliberate non-goal — no response interpretation.** This package returns bodies as
  strings. Parsing JSON, HTML, or iCal is the caller's job. A helper here that "just
  decodes the JSON" would start the drift toward per-vendor knowledge living in the
  transport layer.
- **`SCRAPE_CACHE_DIR` has no default and must be set.** The cache can reach tens of GB
  and is deliberately kept off the repo volume; `config.get_scrape_cache_dir()` raises
  rather than guessing.

## 4. Design

**Composition over inheritance.** `PoliteFetcher` is not a subclass of `UrllibFetcher`;
it takes a `Fetcher` in its constructor. That is what lets the same politeness, throttle,
and cache stack sit in front of *either* transport — `pipeline.run()` builds the headless
path as `PoliteFetcher(fetcher=PlaywrightFetcher())`, structurally identical to the
static path, so a headless source gets robots checking and rate limiting for free.

**Cache format chosen for debuggability.** One human-readable JSON file per URL, rather
than a database or a packed store, because the operational need this cache actually
serves is "why did this source return nothing yesterday?" — answerable by opening a file.
Domain sharding keeps directory sizes manageable across ~100 sources.

**Conditional GET.** `conditional_headers(entry)` builds `If-None-Match` /
`If-Modified-Since` from a cached entry's `ETag`/`Last-Modified`. A 304 response reuses
the cached body and only `touch_fetch_timestamp` is written, so an unchanged page costs
one cheap round trip rather than a full body transfer.

**Injectable clock and sleep.** `Throttle` takes both as constructor parameters so tests
can assert "at least N seconds between fetches to the same domain" without any real
wall-clock wait.

**Why `PlaywrightFetcher` implements the same Protocol rather than being a special
case.** It drops into `PoliteFetcher`'s existing `fetcher=` parameter with zero changes to
`PoliteFetcher`, `robots.py`, or `throttle.py`. The consequence is that no adapter and no
discovery module ever learns that headless fetching exists — `pipeline.py` is the only
module in the codebase that constructs it, selected per source from
`acquisition_policy.fetch_strategy`.

**Testing the headless path without the dependency.** `PlaywrightFetcher` takes a
`page_factory` callable. Tests inject a fixture page; production omits it and gets
`_default_page_factory`, which performs the deferred import. This is the same DI pattern
`Fetcher` and `LLMClient` use, applied one level deeper — here the *dependency itself*,
not just the network call, must be avoidable.

## 5. Interfaces

### Exposes
- **`Fetcher` Protocol** — `get(url, headers=None) -> FetchResponse`. The seam every
  other subsystem depends on.
- **`FetchResponse`** — `url`, `status`, `headers`, `body`, `fetched_at`. `status == 0`
  means transport failure.
- **`PoliteFetcher(cache_dir=None, fetcher=None, throttle=None, user_agent=...,
  clock=...)`** with `.get(url, rate_limit_seconds=1.0, respect_robots=True,
  headers=None)` — the production entry point. Raises `RobotsDisallowed` when robots.txt
  forbids the URL; otherwise returns a `FetchResponse` (possibly cache-sourced, possibly
  status 0).
- **`UrllibFetcher(user_agent=..., timeout=30.0)`** — the default real transport.
- **`PlaywrightFetcher(page_factory=None)`** — headless transport, same contract. Raises
  `PlaywrightNotInstalledError` if the optional dependency is missing at first real use.
- **`Throttle(clock=..., sleep=...)`** with `.wait(domain, rate_limit_seconds)` — shared,
  thread-safe, per-domain.
- **`is_allowed(url, fetcher, user_agent) -> bool`**, **`RobotsDisallowed`** — robots
  checking, usable standalone (`discovery.hub_scan` calls it directly).
- **`cache_path`, `conditional_headers`, `sanitize_url`, `DEFAULT_USER_AGENT`,
  `DEFAULT_RATE_LIMIT_SECONDS`, `NETWORK_IDLE_TIMEOUT_MS`** — supporting surface.

### Consumes
- **`config.get_scrape_cache_dir()` (from `config.py`)** — the cache root. The only
  configuration this package reads, and it reads it through the one module permitted to
  touch `os.environ`.

Nothing else. This package depends on no other subsystem — it is the bottom of the
dependency graph.

## 6. Open Questions / Known Limitations

- The cache has no eviction policy. It grows without bound and is pruned by hand.
- `PoliteFetcher` has no retry/backoff. A transient 5xx or timeout is a status-0 or
  non-200 response for that run, recovered only on the next scheduled run.
- `Throttle` state is in-memory and per-process. Two concurrent `partner-scrape`
  processes would not coordinate their politeness against the same domain.
- Robots.txt results are not cached across calls within a run beyond whatever the
  response cache happens to hold, so a source with many URLs may re-check more often than
  strictly necessary.
- `scrapy` and `w3lib` remain declared dependencies in `pyproject.toml` but the fetch
  path is stdlib `urllib`; the leftover declarations should be audited.
