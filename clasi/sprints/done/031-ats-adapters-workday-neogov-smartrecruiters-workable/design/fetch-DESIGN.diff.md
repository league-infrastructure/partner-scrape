---
source_file: fetch-DESIGN.md
source_hash: 32491a78ae4473e0d74c768cca1df404a95059bdae7bd7f2a815345047af1511
---
# Diff: fetch-DESIGN.md

Comparison of the sprint overlay copy of `fetch-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- fetch-DESIGN.md (pristine)
+++ fetch-DESIGN.md (current)
@@ -1,8 +1,109 @@
 # Fetch
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 031 — `Fetcher.post()`) · **Status:** stable
 
 ---
+
+## Revision (2026-09-02 — sprint 031 POST support for Workday)
+
+Sprint 031 (ATS adapters: Workday, NEOGOV, SmartRecruiters, Workable)
+needs to call Workday's public `POST /wday/cxs/{tenant}/{site}/jobs`
+endpoint — the first non-`GET` request anywhere in this codebase.
+Every other structured-API adapter (`tec_rest`, `localist`,
+`greenhouse`, `lever`, `leaguesync`, `robotevents`, and this sprint's
+own `neogov`/`smartrecruiters`/`workable`) is a plain `GET`; Workday's
+public job-search endpoint genuinely requires a POST body (search
+text, pagination offset, facet filters) — there is no GET-based
+equivalent to fall back to.
+
+**Design decision: extend the `Fetcher` Protocol with a second method,
+`post()`, rather than let the Workday adapter open its own `urllib`
+call.**
+- *Decision*: `Fetcher.post(url, body, headers=None) -> FetchResponse`
+  joins `get()` as the Protocol's second method.
+  `UrllibFetcher.post()` implements it with `urllib.request.Request(
+  ..., data=json.dumps(body).encode("utf-8"), method="POST")` plus
+  `Content-Type: application/json`, reusing `get()`'s exact
+  transport-error handling (`HTTPError` → normalized `FetchResponse`;
+  `OSError`/`http.client.HTTPException`/`UnicodeError` →
+  `TRANSPORT_ERROR_STATUS`, never raised). `PoliteFetcher.post()`
+  composes the same robots-check and per-domain `Throttle.wait()` call
+  `get()` already applies, then delegates to
+  `self.fetcher.post(url, body, headers=merged_headers)` — see the next
+  Design Rationale for why it does *not* also compose the on-disk
+  cache.
+- *Context*: §1's own Purpose statement ("`fetch/` is the only part of
+  the system that talks to the network") and this project's global
+  convention #1 (`docs/design/design.md` §5: "every boundary to the
+  outside world is a `typing.Protocol` passed in as an argument")
+  together mean any new HTTP verb this codebase needs has to be added
+  to this seam, not worked around outside it.
+- *Alternatives considered*: (a) `workday.py` calls `urllib.request`
+  directly, bypassing `Fetcher` entirely, since it is (for now) the
+  only adapter that needs POST; (b) widen `get()`'s own signature with
+  an optional `method`/`body` pair instead of a distinct `post()`
+  method.
+- *Why this choice, over (a)*: this is exactly the "nothing outside
+  this package calls `urllib` or opens a socket" invariant §3 already
+  states, and the reason it exists — the whole 905+-test hermetic
+  suite depends on every remote read going through an injectable
+  `Fetcher`. An adapter that opens its own socket cannot be given a
+  fixture double, so `workday.py`'s own tests would need either a real
+  network call (forbidden by this project's test convention) or a
+  second, ad hoc mocking mechanism inconsistent with every other
+  adapter's test shape.
+- *Why this choice, over (b)*: `get(url, headers=None)`'s signature is
+  read and called by 26+ existing test doubles and every non-Workday
+  adapter/discovery call site. Overloading it with an optional `method`/
+  `body` pair would make every one of those call sites' meaning
+  ambiguous at a glance ("is this a GET with headers, or something
+  else?") for a capability only one adapter needs. A second, explicitly
+  named method costs one more line in the Protocol and reads as what it
+  is; every existing `get()` call site, and every existing test double
+  that implements only `get()`, is completely unaffected — structural
+  typing means a double with no `post()` remains a perfectly valid
+  `Fetcher` for any code that never calls `post()`.
+- *Consequences*: `Fetcher` is no longer a single-method Protocol —
+  future non-GET needs (if any) now have a home. Only `workday.py` and
+  its own tests need a `post()`-capable double; every other adapter's
+  existing fixture `Fetcher` is unaffected and needs no update.
+
+**Design Rationale: `PoliteFetcher.post()` does not read or write the
+on-disk cache.**
+- *Decision*: `PoliteFetcher.post()` applies the robots check and
+  per-domain throttle, exactly like `get()`, but skips
+  `read_cache_entry`/`conditional_headers`/`write_cache_entry`
+  entirely — every `post()` call reaches the network (or the injected
+  test double) every time.
+- *Context*: the existing cache is keyed by `sha256(url)` alone
+  (`cache.py`'s `_cache_key`). Workday's job-search results depend on
+  the POST body (search text, offset, facets), not just the URL — two
+  different pages of the same tenant's job list share one URL and
+  would collide under the current key, silently serving page 1's cached
+  body for every subsequent page's request.
+- *Alternatives considered*: (a) extend the cache key to
+  `sha256(url + json.dumps(body, sort_keys=True))`, giving POST the
+  same conditional-GET-style caching GET already gets; (b) cache POST
+  responses in a separate, body-aware cache keyed the same way.
+- *Why this choice*: at this sprint's traffic volume — four to six
+  Workday tenants, each queried for at most a handful of pages, once
+  per scheduled run — caching buys negligible benefit against real
+  implementation cost: (a) and (b) both need a body-hashing scheme,
+  and neither this cache's on-disk format nor `conditional_headers()`
+  (built for `ETag`/`Last-Modified`, HTTP concepts a POST search
+  response may not even return) obviously extends to a paginated
+  search body without a real design pass of its own. Building that
+  pass speculatively, for a handful of tenants that already sit
+  comfortably within `Throttle`'s existing per-domain rate limit, is
+  the same "solve it when there's evidence it's needed" standard this
+  doc's own §4 Design section and `registry/DESIGN.md`'s Design
+  Rationale entries already apply repeatedly (e.g. "no seasonal-recheck
+  subsystem").
+- *Consequences*: every Workday fetch is a live (or live-in-test-fixture)
+  round trip — slightly more network traffic than a cached GET source
+  gets, bounded by `Throttle`'s existing per-domain `rate_limit_seconds`.
+  Flagged as an Open Question below in case Workday's registered tenant
+  count grows enough to change this calculus.
 
 ## 1. Purpose
 
@@ -53,9 +154,12 @@
 
 ## 2. Orientation
 
-The contract is `fetcher.py`'s `Fetcher` Protocol — one method,
-`get(url, headers=None) -> FetchResponse`. Everything in the package either implements it
-or composes implementations of it.
+The contract is `fetcher.py`'s `Fetcher` Protocol — two methods,
+`get(url, headers=None) -> FetchResponse` and (sprint 031)
+`post(url, body, headers=None) -> FetchResponse`. Everything in the package either
+implements it or composes implementations of it. Every implementation before sprint 031
+had only `get()`; `post()` is additive and only `workday.py` (`adapters/DESIGN.md`)
+calls it.
 
 - `UrllibFetcher` — the real transport. Stdlib `urllib.request`, no third-party HTTP
   dependency.
@@ -227,16 +331,21 @@
 ## 5. Interfaces
 
 ### Exposes
-- **`Fetcher` Protocol** — `get(url, headers=None) -> FetchResponse`. The seam every
-  other subsystem depends on.
+- **`Fetcher` Protocol** — `get(url, headers=None) -> FetchResponse` and (sprint 031)
+  `post(url, body, headers=None) -> FetchResponse`. The seam every other subsystem
+  depends on.
 - **`FetchResponse`** — `url`, `status`, `headers`, `body`, `fetched_at`. `status == 0`
   means transport failure.
 - **`PoliteFetcher(cache_dir=None, fetcher=None, throttle=None, user_agent=...,
   clock=...)`** with `.get(url, rate_limit_seconds=1.0, respect_robots=True,
   headers=None)` — the production entry point. Raises `RobotsDisallowed` when robots.txt
   forbids the URL; otherwise returns a `FetchResponse` (possibly cache-sourced, possibly
-  status 0).
+  status 0). **(Sprint 031)** `.post(url, body, rate_limit_seconds=1.0,
+  respect_robots=True, headers=None)` — same robots/throttle composition, but never reads
+  or writes the on-disk cache (see Design Rationale above).
 - **`UrllibFetcher(user_agent=..., timeout=30.0)`** — the default real transport.
+  **(Sprint 031)** `.post(url, body, headers=None)` sends `body` JSON-encoded with
+  `Content-Type: application/json`, same transport-error handling as `.get()`.
 - **`PlaywrightFetcher(page_factory=None)`** — headless transport, same contract. Raises
   `PlaywrightNotInstalledError` if the optional dependency is missing at first real use.
   **(Sprint 014)** `.get()` now holds an instance-owned `threading.Lock` for its
@@ -341,3 +450,14 @@
   strictly necessary.
 - `scrapy` and `w3lib` remain declared dependencies in `pyproject.toml` but the fetch
   path is stdlib `urllib`; the leftover declarations should be audited.
+- **(Sprint 031)** `PoliteFetcher.post()` has no cache of any kind (Design Rationale
+  above) — if Workday's registered-tenant count grows meaningfully past this sprint's
+  four-to-six, or if a future non-Workday source also needs POST at higher volume, a
+  body-hash-aware cache extension should be designed then, with real traffic numbers
+  informing whether it is worth the complexity. Not built speculatively here.
+- **(Sprint 031)** Whether browser-like headers alone (no real browser, no TLS/JA3
+  fingerprint change) are sufficient to clear Workday's 403 on a plain `urllib` POST is
+  unconfirmed at architecture-authoring time — issue 31's own census only establishes
+  that a headerless plain request 403s. `adapters/DESIGN.md`'s own sprint 031 section
+  carries the live-verification finding and the enable/disable-with-reason fallback if
+  headers alone prove insufficient for a given tenant.
```
