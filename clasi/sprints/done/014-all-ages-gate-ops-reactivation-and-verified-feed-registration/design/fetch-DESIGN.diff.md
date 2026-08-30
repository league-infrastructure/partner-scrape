---
source_file: fetch-DESIGN.md
source_hash: ac755379c0379648b91a1695f0d52ccecef6a5f43b4a586b43909d857bdac874
---
# Diff: fetch-DESIGN.md

Comparison of the sprint overlay copy of `fetch-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- fetch-DESIGN.md (pristine)
+++ fetch-DESIGN.md (current)
@@ -1,6 +1,6 @@
 # Fetch
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-08-30 · **Status:** stable
 
 ---
 
@@ -13,6 +13,19 @@
 cross-cutting — every adapter and every discovery strategy needs all of them, and none of
 them should be re-implemented per caller. It owns *retrieval only*: it never interprets a
 response body.
+
+**(Sprint 014)** `PlaywrightFetcher` gains an instance-owned lock, and — the
+load-bearing half of the fix — `pipeline.py` now dispatches every `headless`-strategy
+source through its own dedicated single-worker executor rather than the main 8-worker
+one. Both were discovered necessary during this sprint's own architecture
+self-review, not part of the sprint's original scope statement. See §3's new
+constraint and §4's Design Rationale for why: today exactly one registered source
+uses `fetch_strategy = "headless"`, so concurrent (and cross-thread) access to
+`PlaywrightFetcher`'s single shared browser page has never been possible in
+production; this sprint's ops-reactivation track (issue 23) flags roughly ten more
+sources headless, which — under `pipeline.py`'s existing 8-worker source-level
+concurrency — would make concurrent, multi-threaded headless dispatch a near-certainty
+in a normal run if nothing changed.
 
 ## 2. Orientation
 
@@ -54,6 +67,29 @@
   `fetch_strategy = "headless"`. The whole test suite runs with `playwright` fully
   uninstalled, and `pipeline.run()` constructs the default headless fetcher eagerly
   enough that an import-time dependency would break every run on machines without it.
+- **`PlaywrightFetcher.get()` must never run concurrently with itself, and — per
+  Playwright's own documented sync-API constraint — should be driven from one
+  consistent thread, not merely one call at a time from arbitrary threads**
+  (sprint 014). A single Playwright sync-API `Page` (this class's `_page`, lazily
+  built once and reused for every subsequent call — see §4) is not safe for
+  concurrent navigation from multiple threads: two threads calling `.get()` at once
+  could interleave `goto()`/`content()` calls on the *same* page object, at best
+  raising, at worst silently returning one URL's rendered content attributed to a
+  different URL's `FetchResponse` — a correctness bug, not just a crash, and exactly
+  the kind of "shared mutable state without a clear owner" this project's own
+  boundary principle warns against. Playwright's sync API additionally documents
+  thread-affinity expectations beyond plain mutual exclusion (its internal sync/async
+  bridge is built around being driven consistently), so a bare mutual-exclusion lock
+  guarantees *no two calls overlap* but does not by itself guarantee *every call comes
+  from the same thread* — a `ThreadPoolExecutor` does not otherwise promise that a
+  given object is always touched by the same worker. `PlaywrightFetcher.get()` keeps
+  an instance-owned lock as defense in depth (cheap, catches any future misuse), but
+  the load-bearing guarantee — every call to a given shared instance originates from
+  one consistent thread for a run's lifetime — is provided by *dispatch*, not by
+  this class: see `partner_scrape/DESIGN.md`'s new sprint 014 concurrency convention
+  for why `pipeline.py`, not `fetch/` or `PoliteFetcher`, is the correct owner of
+  that guarantee (it is the only module that decides which worker thread a given
+  source's work runs on).
 - **`Throttle` must be thread-safe per domain and non-blocking across domains.** A single
   instance is shared across `pipeline.run()`'s source-level thread pool. Two concurrent
   `wait()` calls for the *same* domain must not interleave their check-sleep-write
@@ -104,6 +140,40 @@
 module in the codebase that constructs it, selected per source from
 `acquisition_policy.fetch_strategy`.
 
+**Why the primary fix is dispatch-level (`pipeline.py`'s dedicated single-worker
+executor), with `PlaywrightFetcher`'s own lock as defense in depth, not the reverse**
+(sprint 014). *Context:* `_LazyHeadlessFetcher` (`pipeline.py`) already holds a
+lock, but it guards only the *one-time construction* of the shared headless
+`Fetcher` (the double-checked-locking pattern its own docstring documents), not each
+subsequent `.get()` call against every other — that lock is released the instant
+construction finishes, long before any source's fetch happens. Separately, Playwright's
+sync API's documented thread-affinity expectation means a `PlaywrightFetcher`-local
+lock alone — sufficient to prevent overlapping calls — does not by itself guarantee
+every call comes from the *same* thread, which a plain `ThreadPoolExecutor` does not
+otherwise promise. *Alternatives considered:* fix this entirely inside
+`PlaywrightFetcher` with a lock and stop there — rejected once the thread-affinity
+requirement was identified: a lock can serialize timing but cannot control *which*
+thread `pipeline.py`'s executor happens to hand a given task to; only the dispatcher
+controls that. Fix it entirely in `pipeline.py` with no `fetch/`-side change at all —
+rejected as leaving `PlaywrightFetcher` unprotected against any future caller that
+does not route through `pipeline.py`'s careful dispatch (a test harness, a future
+direct-use script), which would silently reintroduce the hazard outside this one
+call site. *Why this choice:* the guarantee that matters (same-thread, non-overlapping
+access to the shared page) can only be provided where the thread is chosen —
+`pipeline.py`'s new dedicated single-worker executor for `headless`-strategy sources
+(§2's `pipeline.py` bullet in `partner_scrape/DESIGN.md`) — while `PlaywrightFetcher`'s
+own lock remains a correctly-scoped, cheap backstop consistent with `PoliteFetcher`'s
+own precedent of locking only the specific resource that needs it (`_cache_lock`
+guards the cache file, nothing else), not a claim that the lock alone is sufficient.
+*Consequences:* headless-flagged sources now execute strictly one at a time, on one
+consistent worker thread, for the run's duration — never concurrently with each
+other, though still fully concurrently with static-strategy sources in the main pool
+— an accepted throughput cost (see Open Questions), justified because headless
+sources are a small minority of the registry (roughly 10-15 of ~120 after this
+sprint) and correctness (never returning one URL's content under another URL's
+`FetchResponse`, never risking a Playwright thread-affinity error) is non-negotiable
+in a way a few extra seconds of wall-clock time is not.
+
 **Testing the headless path without the dependency.** `PlaywrightFetcher` takes a
 `page_factory` callable. Tests inject a fixture page; production omits it and gets
 `_default_page_factory`, which performs the deferred import. This is the same DI pattern
@@ -125,6 +195,11 @@
 - **`UrllibFetcher(user_agent=..., timeout=30.0)`** — the default real transport.
 - **`PlaywrightFetcher(page_factory=None)`** — headless transport, same contract. Raises
   `PlaywrightNotInstalledError` if the optional dependency is missing at first real use.
+  **(Sprint 014)** `.get()` now holds an instance-owned `threading.Lock` for its
+  duration — defense in depth against overlapping calls, same external contract, no
+  new constructor parameter. The load-bearing thread-affinity guarantee is provided
+  by `pipeline.py`'s dispatch (a dedicated single-worker executor for
+  `headless`-strategy sources), not by this lock alone — see Design above.
 - **`Throttle(clock=..., sleep=...)`** with `.wait(domain, rate_limit_seconds)` — shared,
   thread-safe, per-domain.
 - **`is_allowed(url, fetcher, user_agent) -> bool`**, **`RobotsDisallowed`** — robots
@@ -142,6 +217,14 @@
 
 ## 6. Open Questions / Known Limitations
 
+- **(Sprint 014)** Routing all `headless`-strategy sources through one dedicated
+  worker fixes correctness (and thread affinity) but not throughput: with headless
+  sources now numbering roughly 10-15, a run's headless fetches are effectively
+  sequential against each other (one shared, lazily-built page, one worker thread),
+  even though static-strategy sources stay fully concurrent in the main pool. If a
+  future sprint pushes the headless-flagged count meaningfully higher, a small pool
+  of several browser pages/contexts (each with its own dedicated worker) would
+  restore some parallelism — not needed at this sprint's scale, not built here.
 - The cache has no eviction policy. It grows without bound and is pruned by hand.
 - `PoliteFetcher` has no retry/backoff. A transient 5xx or timeout is a status-0 or
   non-200 response for that run, recovered only on the next scheduled run.
```
