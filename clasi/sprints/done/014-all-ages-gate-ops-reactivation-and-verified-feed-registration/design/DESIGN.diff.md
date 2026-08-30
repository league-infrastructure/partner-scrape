---
source_file: DESIGN.md
source_hash: cca6a9c4e9e54550e1f8aade2b209e9a0728f3d36d3d4b93585ee44446ec36bd
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -61,14 +61,18 @@
 
 **Root-level modules.**
 
-- **`pipeline.py`** — the orchestrator. Loads active sources; runs each source's
-  discover→fetch→extract chain in a bounded `ThreadPoolExecutor` (default 8 workers, or a
-  plain sequential loop when `max_source_workers <= 1`); selects each source's `Fetcher`
-  from its `acquisition_policy.fetch_strategy`, lazily constructing the headless one at
-  most once per run; applies enrichers in order; normalizes; exports opportunities and
-  ads. It defines two Protocols that other subsystems satisfy structurally without
-  importing them — `Enricher` and `Reporter`. Its only real logic is sequencing,
-  per-source `Fetcher` selection, and per-source error isolation.
+- **`pipeline.py`** — the orchestrator. Loads active sources; runs each `static`-strategy
+  source's discover→fetch→extract chain in a bounded `ThreadPoolExecutor` (default 8
+  workers, or a plain sequential loop when `max_source_workers <= 1`); selects each
+  source's `Fetcher` from its `acquisition_policy.fetch_strategy`, lazily constructing the
+  headless one at most once per run; applies enrichers in order; normalizes; exports
+  opportunities and ads. It defines two Protocols that other subsystems satisfy
+  structurally without importing them — `Enricher` and `Reporter`. Its only real logic is
+  sequencing, per-source `Fetcher` selection, and per-source error isolation.
+  **(Sprint 014)** every `headless`-strategy source is now dispatched through a second,
+  dedicated single-worker `ThreadPoolExecutor` rather than the main 8-worker one — see
+  §4's new concurrency convention and `fetch/DESIGN.md`'s sprint 014 section for why a
+  lock alone is not sufficient for `PlaywrightFetcher`.
 - **`cli.py`** — the `partner-scrape` console script. `argparse` wrapper over
   `pipeline.run()`, plus the `discover-candidates` subcommand for the lead-generation
   flow. Constructs the default concrete implementations (`LLMEnricher` with
@@ -134,6 +138,21 @@
 `RelevanceGate` all follow this. Python's structural typing makes the import unnecessary,
 and taking it would invert the dependency direction.
 
+**(Sprint 014) A shared `Fetcher` must tolerate `pipeline.py`'s source-level
+concurrency — and when it cannot, dispatch, not the `Fetcher`, adapts.** The default
+static `Fetcher` (`PoliteFetcher` wrapping `UrllibFetcher`) is safe under concurrent
+calls from multiple sources' worker threads because each call is independent and
+stateless. The headless `Fetcher` (`PoliteFetcher` wrapping `PlaywrightFetcher`) is
+not: a single shared Playwright browser page is not just unsafe under *concurrent*
+calls but, per Playwright's own documented sync-API constraint, expected to be
+driven from one consistent thread. `pipeline.py` accommodates this by routing every
+`headless`-strategy source through its own dedicated single-worker executor (see
+§2's `pipeline.py` bullet) rather than asking `fetch/` to somehow make an
+inherently single-threaded browser driver behave as if it were not — `fetch/`'s own
+`PlaywrightFetcher.get()` additionally keeps an instance-owned lock as defense in
+depth, but the load-bearing guarantee is dispatch-level thread affinity, not the
+lock alone. See `fetch/DESIGN.md`'s sprint 014 section for the full rationale.
+
 **One-way dependency direction.** `pipeline` → `registry`/`adapters`/`enrich`/`normalize`/
 `export`; `adapters` → `discovery`/`extract`/`fetch`/`registry`/`model`; `export` →
 `normalize`; and never the reverse in any of these. `normalize/` in particular never
@@ -225,3 +244,11 @@
   the other 104 are a candidate recruitment list, not resolved here. `TBA_KEY` is
   provisioned and verified locally but not yet in the scheduled workflow's GitHub Actions
   secrets — see `sprint.md`'s Migration Concerns.
+- (Sprint 014) The dedicated single-worker executor for `headless`-strategy sources
+  fixes correctness (and, per Playwright's documented constraint, thread affinity) but
+  caps headless throughput at one source at a time, regardless of how many are flagged.
+  At this sprint's scale (roughly 10-15 of ~120 sources) this is an accepted trade-off,
+  not a bottleneck; if a future sprint pushes the headless-flagged count much higher,
+  wall-clock time for that portion of a run would grow roughly linearly and might
+  warrant a small pool of browser pages/contexts instead of one. Not built here — see
+  `fetch/DESIGN.md`'s matching Open Questions entry.
```
