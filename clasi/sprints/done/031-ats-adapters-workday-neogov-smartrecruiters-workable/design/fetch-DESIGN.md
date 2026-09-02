# Fetch

**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 031 — `Fetcher.post()`) · **Status:** stable

---

## Revision (2026-09-02 — sprint 031 POST support for Workday)

Sprint 031 (ATS adapters: Workday, NEOGOV, SmartRecruiters, Workable)
needs to call Workday's public `POST /wday/cxs/{tenant}/{site}/jobs`
endpoint — the first non-`GET` request anywhere in this codebase.
Every other structured-API adapter (`tec_rest`, `localist`,
`greenhouse`, `lever`, `leaguesync`, `robotevents`, and this sprint's
own `neogov`/`smartrecruiters`/`workable`) is a plain `GET`; Workday's
public job-search endpoint genuinely requires a POST body (search
text, pagination offset, facet filters) — there is no GET-based
equivalent to fall back to.

**Design decision: extend the `Fetcher` Protocol with a second method,
`post()`, rather than let the Workday adapter open its own `urllib`
call.**
- *Decision*: `Fetcher.post(url, body, headers=None) -> FetchResponse`
  joins `get()` as the Protocol's second method.
  `UrllibFetcher.post()` implements it with `urllib.request.Request(
  ..., data=json.dumps(body).encode("utf-8"), method="POST")` plus
  `Content-Type: application/json`, reusing `get()`'s exact
  transport-error handling (`HTTPError` → normalized `FetchResponse`;
  `OSError`/`http.client.HTTPException`/`UnicodeError` →
  `TRANSPORT_ERROR_STATUS`, never raised). `PoliteFetcher.post()`
  composes the same robots-check and per-domain `Throttle.wait()` call
  `get()` already applies, then delegates to
  `self.fetcher.post(url, body, headers=merged_headers)` — see the next
  Design Rationale for why it does *not* also compose the on-disk
  cache.
- *Context*: §1's own Purpose statement ("`fetch/` is the only part of
  the system that talks to the network") and this project's global
  convention #1 (`docs/design/design.md` §5: "every boundary to the
  outside world is a `typing.Protocol` passed in as an argument")
  together mean any new HTTP verb this codebase needs has to be added
  to this seam, not worked around outside it.
- *Alternatives considered*: (a) `workday.py` calls `urllib.request`
  directly, bypassing `Fetcher` entirely, since it is (for now) the
  only adapter that needs POST; (b) widen `get()`'s own signature with
  an optional `method`/`body` pair instead of a distinct `post()`
  method.
- *Why this choice, over (a)*: this is exactly the "nothing outside
  this package calls `urllib` or opens a socket" invariant §3 already
  states, and the reason it exists — the whole 905+-test hermetic
  suite depends on every remote read going through an injectable
  `Fetcher`. An adapter that opens its own socket cannot be given a
  fixture double, so `workday.py`'s own tests would need either a real
  network call (forbidden by this project's test convention) or a
  second, ad hoc mocking mechanism inconsistent with every other
  adapter's test shape.
- *Why this choice, over (b)*: `get(url, headers=None)`'s signature is
  read and called by 26+ existing test doubles and every non-Workday
  adapter/discovery call site. Overloading it with an optional `method`/
  `body` pair would make every one of those call sites' meaning
  ambiguous at a glance ("is this a GET with headers, or something
  else?") for a capability only one adapter needs. A second, explicitly
  named method costs one more line in the Protocol and reads as what it
  is; every existing `get()` call site, and every existing test double
  that implements only `get()`, is completely unaffected — structural
  typing means a double with no `post()` remains a perfectly valid
  `Fetcher` for any code that never calls `post()`.
- *Consequences*: `Fetcher` is no longer a single-method Protocol —
  future non-GET needs (if any) now have a home. Only `workday.py` and
  its own tests need a `post()`-capable double; every other adapter's
  existing fixture `Fetcher` is unaffected and needs no update.

**Design Rationale: `PoliteFetcher.post()` does not read or write the
on-disk cache.**
- *Decision*: `PoliteFetcher.post()` applies the robots check and
  per-domain throttle, exactly like `get()`, but skips
  `read_cache_entry`/`conditional_headers`/`write_cache_entry`
  entirely — every `post()` call reaches the network (or the injected
  test double) every time.
- *Context*: the existing cache is keyed by `sha256(url)` alone
  (`cache.py`'s `_cache_key`). Workday's job-search results depend on
  the POST body (search text, offset, facets), not just the URL — two
  different pages of the same tenant's job list share one URL and
  would collide under the current key, silently serving page 1's cached
  body for every subsequent page's request.
- *Alternatives considered*: (a) extend the cache key to
  `sha256(url + json.dumps(body, sort_keys=True))`, giving POST the
  same conditional-GET-style caching GET already gets; (b) cache POST
  responses in a separate, body-aware cache keyed the same way.
- *Why this choice*: at this sprint's traffic volume — four to six
  Workday tenants, each queried for at most a handful of pages, once
  per scheduled run — caching buys negligible benefit against real
  implementation cost: (a) and (b) both need a body-hashing scheme,
  and neither this cache's on-disk format nor `conditional_headers()`
  (built for `ETag`/`Last-Modified`, HTTP concepts a POST search
  response may not even return) obviously extends to a paginated
  search body without a real design pass of its own. Building that
  pass speculatively, for a handful of tenants that already sit
  comfortably within `Throttle`'s existing per-domain rate limit, is
  the same "solve it when there's evidence it's needed" standard this
  doc's own §4 Design section and `registry/DESIGN.md`'s Design
  Rationale entries already apply repeatedly (e.g. "no seasonal-recheck
  subsystem").
- *Consequences*: every Workday fetch is a live (or live-in-test-fixture)
  round trip — slightly more network traffic than a cached GET source
  gets, bounded by `Throttle`'s existing per-domain `rate_limit_seconds`.
  Flagged as an Open Question below in case Workday's registered tenant
  count grows enough to change this calculus.

## 1. Purpose

`fetch/` is the only part of the system that talks to the network. It owns polite,
cache-aware retrieval of remote resources: robots.txt compliance, per-domain rate
limiting, on-disk conditional-GET caching, and the choice between a plain HTTP client and
a real headless browser. It is a subsystem because every one of those concerns is
cross-cutting — every adapter and every discovery strategy needs all of them, and none of
them should be re-implemented per caller. It owns *retrieval only*: it never interprets a
response body.

**(Sprint 014)** `PlaywrightFetcher` gains an instance-owned lock, and — the
load-bearing half of the fix — `pipeline.py` now dispatches every `headless`-strategy
source through its own dedicated single-worker executor rather than the main 8-worker
one. Both were discovered necessary during this sprint's own architecture
self-review, not part of the sprint's original scope statement. See §3's new
constraint and §4's Design Rationale for why: today exactly one registered source
uses `fetch_strategy = "headless"`, so concurrent (and cross-thread) access to
`PlaywrightFetcher`'s single shared browser page has never been possible in
production; this sprint's ops-reactivation track (issue 23) flags roughly ten more
sources headless, which — under `pipeline.py`'s existing 8-worker source-level
concurrency — would make concurrent, multi-threaded headless dispatch a near-certainty
in a normal run if nothing changed.

**(Sprint 015)** `PlaywrightFetcher.get()` gains a second internal retrieval path:
a URL-extension heuristic (`_looks_like_raw_resource`) routes a raw, non-HTML target
(`.xml`, `.json`, `.csv`, `.rss`, `.atom`) through Playwright's `page.request`
(`APIRequestContext`) surface instead of `page.goto()` + `page.content()`. Root
cause, live-confirmed on 9 of the 10 headless-flagged sources (issue 37, sprint 014
ticket 003's triage): navigating to a bare `.xml` sitemap either returns Chromium's
own XML-viewer-wrapped markup instead of the real body, or aborts navigation outright
(`net::ERR_ABORTED`) — the method's external contract, and every other module's
unawareness that headless fetching exists, are both unchanged. See §4's Design
Rationale for the fuller account and §6 for why `.txt` is deliberately excluded.

**(Sprint 015 ticket 003)** `PoliteFetcher.get()`'s `rate_limit_seconds`/
`respect_robots` parameters are unchanged — both this method's signature and its
defaults — but every caller now actually supplies them. Before this ticket, every
`adapters/*.py` and `discovery/sitemap.py`/`discovery/listing.py` call site invoked
`fetcher.get(url)` with no override, so a source's `acquisition_policy` (parsed by
`registry/schema.py`) never reached this method despite this class's own docstring
describing exactly that design since before it was implemented (`leaguesync.toml`'s
`respect_robots = false` had no effect until this ticket). `adapters/base.py`'s new
`acquisition_kwargs(source)` helper is what each caller now spreads into this call
— see `adapters/DESIGN.md`. This package itself is unchanged: it still has no
dependency on the Registry, and still accepts these two values as plain per-call
parameters rather than reading a `SourceConfig` here.

## 2. Orientation

The contract is `fetcher.py`'s `Fetcher` Protocol — two methods,
`get(url, headers=None) -> FetchResponse` and (sprint 031)
`post(url, body, headers=None) -> FetchResponse`. Everything in the package either
implements it or composes implementations of it. Every implementation before sprint 031
had only `get()`; `post()` is additive and only `workday.py` (`adapters/DESIGN.md`)
calls it.

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
- **`PlaywrightFetcher.get()` must never run concurrently with itself, and — per
  Playwright's own documented sync-API constraint — should be driven from one
  consistent thread, not merely one call at a time from arbitrary threads**
  (sprint 014). A single Playwright sync-API `Page` (this class's `_page`, lazily
  built once and reused for every subsequent call — see §4) is not safe for
  concurrent navigation from multiple threads: two threads calling `.get()` at once
  could interleave `goto()`/`content()` calls on the *same* page object, at best
  raising, at worst silently returning one URL's rendered content attributed to a
  different URL's `FetchResponse` — a correctness bug, not just a crash, and exactly
  the kind of "shared mutable state without a clear owner" this project's own
  boundary principle warns against. Playwright's sync API additionally documents
  thread-affinity expectations beyond plain mutual exclusion (its internal sync/async
  bridge is built around being driven consistently), so a bare mutual-exclusion lock
  guarantees *no two calls overlap* but does not by itself guarantee *every call comes
  from the same thread* — a `ThreadPoolExecutor` does not otherwise promise that a
  given object is always touched by the same worker. `PlaywrightFetcher.get()` keeps
  an instance-owned lock as defense in depth (cheap, catches any future misuse), but
  the load-bearing guarantee — every call to a given shared instance originates from
  one consistent thread for a run's lifetime — is provided by *dispatch*, not by
  this class: see `partner_scrape/DESIGN.md`'s new sprint 014 concurrency convention
  for why `pipeline.py`, not `fetch/` or `PoliteFetcher`, is the correct owner of
  that guarantee (it is the only module that decides which worker thread a given
  source's work runs on).
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

**Why the primary fix is dispatch-level (`pipeline.py`'s dedicated single-worker
executor), with `PlaywrightFetcher`'s own lock as defense in depth, not the reverse**
(sprint 014). *Context:* `_LazyHeadlessFetcher` (`pipeline.py`) already holds a
lock, but it guards only the *one-time construction* of the shared headless
`Fetcher` (the double-checked-locking pattern its own docstring documents), not each
subsequent `.get()` call against every other — that lock is released the instant
construction finishes, long before any source's fetch happens. Separately, Playwright's
sync API's documented thread-affinity expectation means a `PlaywrightFetcher`-local
lock alone — sufficient to prevent overlapping calls — does not by itself guarantee
every call comes from the *same* thread, which a plain `ThreadPoolExecutor` does not
otherwise promise. *Alternatives considered:* fix this entirely inside
`PlaywrightFetcher` with a lock and stop there — rejected once the thread-affinity
requirement was identified: a lock can serialize timing but cannot control *which*
thread `pipeline.py`'s executor happens to hand a given task to; only the dispatcher
controls that. Fix it entirely in `pipeline.py` with no `fetch/`-side change at all —
rejected as leaving `PlaywrightFetcher` unprotected against any future caller that
does not route through `pipeline.py`'s careful dispatch (a test harness, a future
direct-use script), which would silently reintroduce the hazard outside this one
call site. *Why this choice:* the guarantee that matters (same-thread, non-overlapping
access to the shared page) can only be provided where the thread is chosen —
`pipeline.py`'s new dedicated single-worker executor for `headless`-strategy sources
(§2's `pipeline.py` bullet in `partner_scrape/DESIGN.md`) — while `PlaywrightFetcher`'s
own lock remains a correctly-scoped, cheap backstop consistent with `PoliteFetcher`'s
own precedent of locking only the specific resource that needs it (`_cache_lock`
guards the cache file, nothing else), not a claim that the lock alone is sufficient.
*Consequences:* headless-flagged sources now execute strictly one at a time, on one
consistent worker thread, for the run's duration — never concurrently with each
other, though still fully concurrently with static-strategy sources in the main pool
— an accepted throughput cost (see Open Questions), justified because headless
sources are a small minority of the registry (roughly 10-15 of ~120 after this
sprint) and correctness (never returning one URL's content under another URL's
`FetchResponse`, never risking a Playwright thread-affinity error) is non-negotiable
in a way a few extra seconds of wall-clock time is not.

**Testing the headless path without the dependency.** `PlaywrightFetcher` takes a
`page_factory` callable. Tests inject a fixture page; production omits it and gets
`_default_page_factory`, which performs the deferred import. This is the same DI pattern
`Fetcher` and `LLMClient` use, applied one level deeper — here the *dependency itself*,
not just the network call, must be avoidable.

**(Sprint 015) Fix the raw-resource bug entirely inside `fetch/headless.py`, as a
second internal path behind the same `Fetcher.get()` contract — not a second Fetcher,
not a `discovery`-side change.** *Context:* issue 37's two candidate fix shapes were
routing non-HTML URLs through the plain HTTP fetcher, or using Playwright's request API
for raw resources. *Alternatives considered:* give `pipeline.py` a second "raw" fetcher
threaded through `discovery.discover_changed_urls()` for non-HTML URLs — rejected: it
would break the "no adapter and no discovery module ever learns that headless fetching
exists" invariant this section already documents, for a fix that belongs entirely inside
one method. *Why this choice:* `PlaywrightFetcher.get()` now checks
`_looks_like_raw_resource(url)` (a URL-extension heuristic — there is no real
`Content-Type` to inspect before a request is made) before deciding whether to navigate
or issue a raw `page.request.get()` call; `HeadlessPage`'s fixture-double Protocol grew
a `request` property (`HeadlessRequestContext`/`HeadlessRawResponse`) to support this in
tests with no real browser. `PoliteFetcher`, every adapter, and `discovery/sitemap.py`
are unaffected by construction — same as the class docstring already promised.
*Consequences:* one root cause (navigating to a raw resource at all), one fix, fully
contained to this module; live-verified against `lajollalibrary.org`'s real sitemap
index and a real child `<urlset>` sitemap, both previously `net::ERR_ABORTED`, now
returning their real XML bodies unchanged.

## 5. Interfaces

### Exposes
- **`Fetcher` Protocol** — `get(url, headers=None) -> FetchResponse` and (sprint 031)
  `post(url, body, headers=None) -> FetchResponse`. The seam every other subsystem
  depends on.
- **`FetchResponse`** — `url`, `status`, `headers`, `body`, `fetched_at`. `status == 0`
  means transport failure.
- **`PoliteFetcher(cache_dir=None, fetcher=None, throttle=None, user_agent=...,
  clock=...)`** with `.get(url, rate_limit_seconds=1.0, respect_robots=True,
  headers=None)` — the production entry point. Raises `RobotsDisallowed` when robots.txt
  forbids the URL; otherwise returns a `FetchResponse` (possibly cache-sourced, possibly
  status 0). **(Sprint 031)** `.post(url, body, rate_limit_seconds=1.0,
  respect_robots=True, headers=None)` — same robots/throttle composition, but never reads
  or writes the on-disk cache (see Design Rationale above).
- **`UrllibFetcher(user_agent=..., timeout=30.0)`** — the default real transport.
  **(Sprint 031)** `.post(url, body, headers=None)` sends `body` JSON-encoded with
  `Content-Type: application/json`, same transport-error handling as `.get()`.
- **`PlaywrightFetcher(page_factory=None)`** — headless transport, same contract. Raises
  `PlaywrightNotInstalledError` if the optional dependency is missing at first real use.
  **(Sprint 014)** `.get()` now holds an instance-owned `threading.Lock` for its
  duration — defense in depth against overlapping calls, same external contract, no
  new constructor parameter. The load-bearing thread-affinity guarantee is provided
  by `pipeline.py`'s dispatch (a dedicated single-worker executor for
  `headless`-strategy sources), not by this lock alone — see Design above.
  **(Sprint 015)** `.get()` routes a non-HTML target through `page.request.get()`
  instead of navigating — see Design above. Still the same external contract; still no
  new constructor parameter.
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

- **(Sprint 014)** Routing all `headless`-strategy sources through one dedicated
  worker fixes correctness (and thread affinity) but not throughput: with headless
  sources now numbering roughly 10-15, a run's headless fetches are effectively
  sequential against each other (one shared, lazily-built page, one worker thread),
  even though static-strategy sources stay fully concurrent in the main pool. If a
  future sprint pushes the headless-flagged count meaningfully higher, a small pool
  of several browser pages/contexts (each with its own dedicated worker) would
  restore some parallelism — not needed at this sprint's scale, not built here.
- **(Sprint 014, revision — found during ticket 002's required pre-close live
  validation, resolved in the same ticket) `wait_until` changed from
  `"networkidle"` to `"load"`; `NETWORK_IDLE_TIMEOUT_MS` unchanged.** Live-testing
  the 8 newly-flagged Wix sources (2026-08-30) found `PlaywrightFetcher.get()`
  raised `TimeoutError` under the original `networkidle` wait for all 8 real
  homepage/listing fetches tested (`gsdsef.org`, `xplorstem.com`, `sdrvc.org`,
  `titanbot.org`, `lajollalibrary.org`, `techadventurecamp.com`,
  `climate-science-alliance.org`, `escondidocreek.org`) — these Wix sites keep a
  persistent analytics/chat-widget connection open indefinitely, so the network
  never truly idles. The *content* was never the problem: the same URLs fetched
  with `wait_until="load"` instead consistently returned full, real, rendered
  text (e.g. `gsdsef.org` in ~1s, real nav/program text) rather than an empty
  shell — a wait-*strategy* mismatch, not a rendering or fetch failure.
  Team-lead ruling (post-implementation review): a global default-strategy
  change is not the "per-source timeout/retry tuning" this ticket's own Design
  Rationale rejected as scope creep — that alternative was about adding a *new*,
  per-source config surface, not correcting the one shared default every source
  already uses identically; and ticket 003's zero-yield triage depends on
  headless fetching actually working against real sites, making this load-bearing
  for the sprint, not merely nice-to-have. Fixed here: `get()` now passes
  `wait_until="load"` (still bounded by the same, unchanged
  `NETWORK_IDLE_TIMEOUT_MS`) — no new config surface, no per-source override
  added, matching the one thing the original alternatives-analysis actually
  rejected. Re-validated live post-fix, through the exact production
  construction path (`pipeline._build_default_headless_fetcher()`): `gsdsef.org`,
  `xplorstem.com`, and `sdrvc.org` (3 of the 8 newly-flagged Wix sites) all
  return HTTP 200 with 1MB+ of real rendered HTML (thousands of characters of
  real visible nav/program text, not an empty shell) through
  `PlaywrightFetcher.get()` unchanged. `sandiego-cv.aopsacademy.org` (the one
  non-Wix source this ticket also flags headless) was already unaffected by the
  original strategy — its content is a lighter JS shell that reached
  `networkidle` well inside the 15s bound either way — and remains unaffected by
  this change. Existing fixture tests updated to assert `wait_until == "load"`
  (`tests/test_fetch_headless.py`); no other test depended on the literal
  `"networkidle"` string. This closes what was recorded as a "recommended
  follow-up" in the ticket's initial live-validation pass — resolved in the same
  ticket instead, per the ruling above.
- **(Sprint 014) The dispatch-level thread-affinity hazard this ticket fixes is
  not hypothetical — reproduced live during ticket 002's validation.** Two raw
  Python threads (bypassing `pipeline.py`'s dispatch entirely, i.e. deliberately
  recreating the pre-fix hazard) calling `.get()` on one shared, real
  `PlaywrightFetcher` instance for two different real Wix URLs: the first call's
  `networkidle` wait timed out and that thread exited; the second thread's call
  then failed with Playwright's own real error, `"cannot switch to a different
  thread (which happens to have exited)"` — exactly the thread-affinity failure
  mode this section's Constraints already predicted, now confirmed against the
  real `playwright` package rather than only reasoned about. A real production
  run using `pipeline.py`'s actual dedicated single-worker executor (two real
  registered headless sources, no fixtures) completed with both sources' calls
  landing on the same worker thread and no such error — the fix works; the
  hazard it fixes is real.
- **(Sprint 015)** `_RAW_RESOURCE_EXTENSIONS` deliberately excludes `.txt`, even though
  it is exactly as non-HTML as `.xml`/`.json`/etc. `fetch/robots.py` fetches
  `robots.txt` through this same `get()` for every source (headless or not), and that
  path has no evidenced bug — issue 37's live triage found only `.xml` sitemaps
  failing. Adding `.txt` would silently change robots.txt retrieval behavior as a side
  effect of a fix scoped to sitemaps, not a deliberate, evidenced change; a future
  ticket with actual evidence of a broken `.txt` (or other extension) fetch can extend
  the tuple then.
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
- **(Sprint 031)** `PoliteFetcher.post()` has no cache of any kind (Design Rationale
  above) — if Workday's registered-tenant count grows meaningfully past this sprint's
  four-to-six, or if a future non-Workday source also needs POST at higher volume, a
  body-hash-aware cache extension should be designed then, with real traffic numbers
  informing whether it is worth the complexity. Not built speculatively here.
- **(Sprint 031)** Whether browser-like headers alone (no real browser, no TLS/JA3
  fingerprint change) are sufficient to clear Workday's 403 on a plain `urllib` POST is
  unconfirmed at architecture-authoring time — issue 31's own census only establishes
  that a headerless plain request 403s. `adapters/DESIGN.md`'s own sprint 031 section
  carries the live-verification finding and the enable/disable-with-reason fallback if
  headers alone prove insufficient for a given tenant.
