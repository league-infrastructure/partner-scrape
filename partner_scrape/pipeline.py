"""Pipeline/CLI orchestration: wires Registry -> Adapters -> Normalize -> Export.

See sprint.md's Architecture > Pipeline/CLI: this module's whole job is
sequencing the business logic each other module already owns --
enumerate active Source Registry entries (ticket 002), dispatch each to
its adapter via the ticket 004/005 dispatch registry, run the (currently
empty) `Enricher` hook over the collected Events, hand the result to
`normalize.run()` (ticket 006), then to `export.export_opportunities()`
(ticket 007). If this file grows business logic of its own beyond
sequencing + per-source error isolation, that is a sign a responsibility
leaked out of its owning module and belongs there instead -- the "must
not become a god component" check sprint.md's self-review pre-justified.

Per-source error isolation (SUC-008's Error Flow: "One source's adapter
raises -> logged, run continues with remaining sources, non-zero sources
still produce output") is this module's one piece of real logic: each
source's `adapters.run(source, fetcher)` call is wrapped in its own
try/except inside the enumeration loop, not around the whole batch --
distinct from ticket 004's per-*record* isolation inside a single
adapter's own `extract()`.

Sprint 003 ticket 005 adds this module's other piece of real logic:
per-source `Fetcher` selection. Each source's
`acquisition_policy.get("fetch_strategy", "static")` (registry/schema.py,
also ticket 005) picks between the run's one default `Fetcher` (as
before this ticket) and a headless-wrapping `Fetcher` -- `PoliteFetcher`
wrapping `PlaywrightFetcher` (`fetch/headless.py`, ticket 001), built
lazily via `headless_fetcher_factory` at most once per `run()` call, and
only if at least one active source actually needs it. See sprint.md's
Design Rationale ("Headless fetch strategy is selected by Pipeline...")
-- no `Adapter` implementation, existing or future, needs to know
headless fetching exists; this module is the only one that ever
constructs a headless `Fetcher`.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from partner_scrape.adapters import run as run_adapter
from partner_scrape.config import get_site_dir
from partner_scrape.export import (
    EventImageDownloader,
    export_ads,
    export_opportunities,
    load_ad_configs,
)
from partner_scrape.fetch import Fetcher, PlaywrightFetcher, PoliteFetcher
from partner_scrape.model import Event
from partner_scrape.normalize import run as normalize_run
from partner_scrape.registry import load_active_sources
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: `acquisition_policy.fetch_strategy` value that routes a source
#: through the lazily-constructed headless `Fetcher` instead of the
#: run's default one. Every other value (including the registry
#: default, `"static"`) uses the default `Fetcher` unchanged.
HEADLESS_FETCH_STRATEGY = "headless"

#: Default `max_source_workers` (see `run()`): how many sources are
#: processed concurrently. Politeness is enforced per-DOMAIN (`Throttle`,
#: `fetch/throttle.py`), not per-run, and the Source Registry's ~100
#: entries are ~100 different domains -- so running this many sources at
#: once is both fast (the old strictly-sequential `run()` took ~5 hours
#: for a full crawl once the registry grew past ~30 sources; the 1
#: req/sec per-domain rate limit was the wall-clock bottleneck, not any
#: real per-run concurrency ceiling) and still polite (no domain is ever
#: hit faster than its own configured `rate_limit_seconds`, regardless
#: of how many *other* domains are being fetched at the same instant).
#: 8 mirrors `enrich/enricher.py`'s own `DEFAULT_MAX_WORKERS` for its
#: LLM-call `ThreadPoolExecutor` -- high enough to cut wall-clock time
#: substantially, low enough not to open an unbounded burst of sockets
#: at once.
DEFAULT_MAX_SOURCE_WORKERS = 8


def _build_default_headless_fetcher() -> Fetcher:
    """Production headless-`Fetcher` construction: a `PoliteFetcher`
    wrapping a real `PlaywrightFetcher`, exactly as the run's default
    `Fetcher` wraps `UrllibFetcher` -- see sprint.md's Architecture >
    Pipeline/CLI ("the headless-wrapping `PoliteFetcher` ... exactly as
    the default fetcher is").

    `PlaywrightFetcher()`'s own constructor never imports `playwright`
    (see `fetch/headless.py`) -- that deferred import only happens on
    the first real `.get()` call a source flagged `headless` actually
    triggers, so simply *constructing* this default (e.g. because a
    test needs to prove it was never called) never requires the
    optional `playwright` dependency.

    Overridable via `run()`'s `headless_fetcher_factory` parameter so
    tests can substitute a fixture-backed factory (or a bare spy/counter
    proving this default path was never invoked) -- this function is
    never called directly by anything other than that parameter's
    default.
    """
    return PoliteFetcher(fetcher=PlaywrightFetcher())


class Enricher(Protocol):
    """Deferred seam (sprint.md's Deferred Seams: "Enrichment"): an
    ordered, optional transformation over the collected Event stream,
    applied after adapter collection and before Normalize.

    Ships with zero implementations this sprint -- `enrichers` defaults
    to `()`. Sprint 2's LLM enrichment (issue 04) is expected to
    implement this protocol and be added as one more entry in the list
    passed to :func:`run`, with no Pipeline rework required.
    """

    def enrich(self, events: list[Event]) -> list[Event]:
        """Return a (possibly transformed) copy of ``events``."""
        ...


class Reporter(Protocol):
    """Observability seam (sprint 004's Architecture > `Reporter`
    protocol + hook): an optional observer handed the raw facts
    `run()` already produces at two points it already visits them,
    structurally parallel to `Enricher` above -- same "hands over
    facts it already has, computes nothing itself" boundary that keeps
    this module from becoming a god component.

    Ships with zero implementations in this ticket -- `reporter`
    defaults to `None` (no-op). `observability.YieldReporter` (ticket
    002) is expected to implement this protocol with no import of
    `pipeline.py` at all, satisfying it structurally exactly as
    `enrich.enricher.LLMEnricher` already satisfies `Enricher`.
    """

    def record_source(
        self,
        source_id: str,
        org_name: str,
        events: list[Event],
        error: Exception | None = None,
    ) -> None:
        """Called once per active source, in both branches of the
        existing per-source try/except: on success, ``events`` is that
        source's real, unmodified `list[Event]` and ``error`` is
        `None`; on the adapter's isolated exception, ``events`` is
        `[]` and ``error`` is the caught exception -- so a fetch
        failure and a genuine zero-event run are both reported, never
        conflated."""
        ...

    def record_opportunities(self, opportunities: list[Any]) -> None:
        """Called exactly once, after `normalize_run()` produces the
        final `Opportunity` list and before `export_opportunities()`
        strips its `.sources` attribution."""
        ...


class _NoOpReporter:
    """`run()`'s default `reporter` -- both hook calls are no-ops, so
    every existing caller/test is unaffected without any change on
    their part (sprint.md's Migration Concerns: "Backward
    compatibility")."""

    def record_source(
        self,
        source_id: str,
        org_name: str,
        events: list[Event],
        error: Exception | None = None,
    ) -> None:
        return None

    def record_opportunities(self, opportunities: list[Any]) -> None:
        return None


class _LazyHeadlessFetcher:
    """Thread-safe lazy singleton wrapping a `headless_fetcher_factory`.

    Preserves `run()`'s pre-existing "constructed at most once per
    `run()` call, only when at least one active source needs it"
    contract (see `run()`'s own `headless_fetcher_factory` docstring)
    now that multiple sources can reach the "I need the headless
    Fetcher" check at the same instant from different worker threads.
    A single-threaded `if self._instance is None: build it` check would
    race: two threads could both see `None` and both call `factory()`,
    building two headless Fetchers (two browsers, in the real
    Playwright-backed default) when the contract promises at most one.

    Standard double-checked locking: the cheap, lock-free `None` check
    happens first (the overwhelmingly common case once built -- every
    call after the first skips the lock entirely), and only a thread
    that might actually need to build the instance takes the lock,
    re-checking once inside it in case another thread finished building
    while this one was waiting.
    """

    def __init__(self, factory: Callable[[], Fetcher]) -> None:
        self._factory = factory
        self._instance: Fetcher | None = None
        self._lock = threading.Lock()

    def get(self) -> Fetcher:
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._factory()
        return self._instance


@dataclass
class _SourceResult:
    """One source's outcome from `_run_one_source` -- the unit of work
    `run()`'s source-level `ThreadPoolExecutor` collects, joins, and
    then (on the main thread only, in registry order) reports and
    accumulates. Carries `source` itself (not just its id) so the
    caller never needs a second `sources` lookup to recover
    `org_name`/`adapter_type` for logging or the `Reporter` call.
    """

    source: SourceConfig
    events: list[Event]
    error: Exception | None


def _run_one_source(
    source: SourceConfig,
    active_fetcher: Fetcher,
    lazy_headless_fetcher: _LazyHeadlessFetcher,
) -> _SourceResult:
    """Run one source's discover -> fetch -> extract chain (`adapters.run`),
    selecting its `Fetcher` first exactly as the old sequential loop did.

    This is the callable `run()` hands to its source-level
    `ThreadPoolExecutor` (or simply calls directly in a plain `for`
    loop when `max_source_workers <= 1`) -- one call per active source,
    safe to run concurrently with any other source's call: it only ever
    touches `source` (this call's own, never shared/mutated) and the
    two already-thread-safe shared `Fetcher`s (see `PoliteFetcher`'s own
    docstring for why a single shared instance tolerates concurrent
    `.get()` calls from multiple sources at once).

    Mirrors the original per-source loop body exactly, including one
    subtlety: `lazy_headless_fetcher.get()` is called *outside* the
    try/except below, same as the old code's `build_headless_fetcher()`
    call -- a `headless_fetcher_factory` that itself raises (never the
    production default, which only ever fails, if at all, on the
    Fetcher's later `.get()` call -- see `_build_default_headless_fetcher`'s
    own docstring) is not caught by per-source isolation, unchanged from
    before this function existed.
    """
    fetch_strategy = source.acquisition_policy.get("fetch_strategy", "static")
    if fetch_strategy == HEADLESS_FETCH_STRATEGY:
        source_fetcher = lazy_headless_fetcher.get()
    else:
        source_fetcher = active_fetcher

    try:
        source_events = run_adapter(source, source_fetcher)
    except Exception as exc:
        # Per-source error isolation (SUC-008): one broken source is
        # logged and skipped, never fatal to the rest of the run --
        # still true under concurrency, since each worker only ever
        # returns its own `_SourceResult` rather than raising into the
        # executor (a raised exception here would otherwise surface
        # from that source's own `Future.result()` and nowhere else,
        # which is exactly the "logged and skipped" isolation this
        # ticket must preserve, just reached one layer further down).
        logger.exception(
            "Source %r (adapter_type=%r) failed; skipping it, run continues "
            "with the remaining sources",
            source.source_id,
            source.adapter_type,
        )
        return _SourceResult(source=source, events=[], error=exc)

    logger.info("Source %r yielded %d event(s)", source.source_id, len(source_events))
    return _SourceResult(source=source, events=source_events, error=None)


def run(
    registry_dir: str | Path | None = None,
    site_dir: str | Path | None = None,
    *,
    ads_dir: str | Path | None = None,
    fetcher: Fetcher | None = None,
    headless_fetcher_factory: Callable[[], Fetcher] | None = None,
    enrichers: Sequence[Enricher] = (),
    reporter: Reporter | None = None,
    partners_path: str | Path | None = None,
    source_id: str | None = None,
    limit: int | None = None,
    today: date | None = None,
    dry_run: bool = False,
    max_source_workers: int = DEFAULT_MAX_SOURCE_WORKERS,
    image_resolver: Callable[[str], str] | None = None,
) -> list[dict[str, Any]]:
    """Run the full aggregator engine end-to-end: Registry -> Adapters ->
    (empty) Enrichers -> Normalize -> Export.

    Args:
        registry_dir: Source Registry directory to load sources from.
            Defaults to the real seed registry
            (`partner_scrape/registry/sources/`) when omitted -- see
            `registry.load_active_sources`.
        site_dir: sibling `stem-ecosystem` checkout to write into.
            Defaults to `Config.get_site_dir()` (`../stem-ecosystem`, or
            `$SITE_DIR`) when omitted. Tests should always pass an
            explicit `tmp_path`-based directory here.
        ads_dir: directory of hand-authored ad-config TOML files (Ad
            Content Export, sprint 005 ticket 005). Defaults to the real
            seed ad registry (`partner_scrape/registry/ads/`) when
            omitted -- see `export.ads.load_ad_configs`. Tests that don't
            care about the exact seeded ad content may pass an explicit
            fixture directory here.
        fetcher: the `Fetcher` each source flagged `static` (the
            registry default, `acquisition_policy.fetch_strategy` unset
            or `"static"`) retrieves raw content through. Defaults to a
            real `PoliteFetcher()` (robots.txt + rate limiting +
            on-disk cache under `$SCRAPE_CACHE_DIR`) when omitted -- the
            production path. Tests inject a fixture `Fetcher` here so
            the whole run touches no sockets.
        headless_fetcher_factory: builds the `Fetcher` every source
            flagged `acquisition_policy.fetch_strategy = "headless"`
            retrieves raw content through. Called at most once per
            `run()` call -- lazily, only when the first `headless`-
            flagged active source is reached -- and its return value is
            reused for every subsequent `headless`-flagged source in
            the same run. Defaults to `_build_default_headless_fetcher`
            (a real `PoliteFetcher` wrapping a real `PlaywrightFetcher`)
            when omitted -- the production path. Tests inject a factory
            returning a fixture-backed `Fetcher` (e.g. `PoliteFetcher`
            wrapping `PlaywrightFetcher(page_factory=...)` with a
            fixture `page_factory`, ticket 001's DI seam), or a bare
            spy/counter, so no run needs a real browser or the optional
            `playwright` dependency.
        enrichers: an ordered sequence of `Enricher`s applied to the
            collected Event stream before normalization. Empty by
            default (see `Enricher`'s docstring).
        reporter: an optional observability hook, called once per
            source (both branches of the per-source try/except) and
            once after normalization with the final `Opportunity`
            list. Defaults to a no-op when omitted -- see `Reporter`'s
            docstring.
        partners_path: path to the site's `partners.json`. Defaults to
            `{site_dir}/src/data/partners.json` (sprint.md's documented
            location) when omitted.
        source_id: when given, run only the active source whose
            `source_id` matches (the registry TOML file's stem) -- the
            CLI's `--source` flag.
        limit: when given, run only the first `limit` active sources
            (after any `source_id` filter) -- the CLI's `--limit` flag.
        today: the reference date for Site Export's current/upcoming
            filter. Defaults to `date.today()` when omitted (via
            `export_opportunities`). Tests should pass an explicit value
            for determinism.
        dry_run: when `True`, compute and return the would-be-written
            export payload without touching disk (`export_opportunities`
            and `export_ads` both respect this the same way).
        max_source_workers: how many active sources' discover -> fetch ->
            extract chains (`adapters.run`) run concurrently, across a
            bounded `ThreadPoolExecutor`. Defaults to
            `DEFAULT_MAX_SOURCE_WORKERS` (8) -- see that constant's own
            docstring for why source-level concurrency is both fast and
            still polite (politeness is enforced per-DOMAIN, by the
            shared `Fetcher`(s)' `Throttle`, not per-run). `1` runs
            every source strictly sequentially, in registry order, on
            the calling thread -- byte-for-byte the same code path
            `run()` used before this parameter existed (no
            `ThreadPoolExecutor` is even constructed), so existing
            callers that care about exact sequential timing/ordering
            can pin it. Regardless of this value, every source's
            events are accumulated into the final `events` list, and
            every `reporter.record_source(...)` call is made, in the
            registry's own source order -- never completion order --
            so a run's output is identical (same events, same order,
            same reported data) no matter how many workers processed
            it or in what order they happened to finish.
        image_resolver: the `image_url -> local filename` callable
            `normalize_run()` uses to populate `Opportunity.image_src`
            (sprint 008 ticket 008, issue 19). Defaults to `None`, which
            makes `run()` construct a real
            `export.images.EventImageDownloader` writing into
            `{resolved site_dir}/public/images/opportunities/` --
            *unless* `dry_run` is `True`, in which case no downloader is
            constructed and `image_src` simply stays `""` for every
            record, matching `export_opportunities`'/`export_ads`'s own
            "computes without touching disk" `dry_run` contract
            (downloading and writing image files is itself a disk write
            this parameter must not perform during a dry run). Tests
            inject a fixture-backed callable (or `lambda _: ""`) here so
            no test touches a real socket; every existing caller/test
            that omits this parameter and never sets `Event.image_url`
            is completely unaffected either way, since
            `EventImageDownloader.download()` makes no network call at
            all for an empty `image_url` (see that class's docstring).

    Returns:
        The list of opportunity dicts that were (or, for `dry_run`,
        would have been) written -- `export_opportunities`'s return
        value, passed through unchanged. `export_ads()` is also called
        (writing/returning `ads.json`'s payload as a side effect) but its
        return value is not part of `run()`'s own return value -- this
        keeps every existing caller/test that only cares about
        opportunities unaffected by this addition.
    """
    sources = load_active_sources(Path(registry_dir) if registry_dir is not None else None)

    if source_id is not None:
        sources = [s for s in sources if s.source_id == source_id]
    if limit is not None:
        sources = sources[:limit]

    active_fetcher = fetcher if fetcher is not None else PoliteFetcher()
    build_headless_fetcher = headless_fetcher_factory or _build_default_headless_fetcher
    # Lazily constructed on the first `headless`-flagged active source
    # this run actually reaches -- wrapped in `_LazyHeadlessFetcher` so
    # "at most once per run(), only when at least one active source
    # needs it" (ticket 005's Acceptance Criteria) still holds when
    # multiple worker threads can reach that first `headless` source at
    # the same instant (see `_LazyHeadlessFetcher`'s own docstring).
    lazy_headless_fetcher = _LazyHeadlessFetcher(build_headless_fetcher)
    active_reporter = reporter if reporter is not None else _NoOpReporter()

    # Source-level concurrency: each active source's discover -> fetch
    # -> extract chain (`_run_one_source`) is independent of every other
    # source's -- the only state any two calls could contend over is the
    # shared `Fetcher`(s) above, and both `PoliteFetcher` and `Throttle`
    # are documented safe for exactly this (see their own docstrings).
    # `max_source_workers <= 1` skips `ThreadPoolExecutor` entirely and
    # runs the exact same sequential `for` loop `run()` always has --
    # not merely a `ThreadPoolExecutor(max_workers=1)`, so there is no
    # thread-pool machinery of any kind on that path (`max_source_workers`'s
    # own docstring above: "byte-for-byte the same code path").
    results: list[_SourceResult]
    if max_source_workers <= 1:
        results = [
            _run_one_source(source, active_fetcher, lazy_headless_fetcher) for source in sources
        ]
    else:
        # `min(...)` avoids spinning up idle worker threads beyond the
        # number of sources actually being run; `max(1, ...)` keeps that
        # from ever reaching 0 (ThreadPoolExecutor requires >= 1) for an
        # empty `sources` list.
        worker_count = max(1, min(max_source_workers, len(sources)))
        results_by_source_id: dict[str, _SourceResult] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(_run_one_source, source, active_fetcher, lazy_headless_fetcher)
                for source in sources
            ]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results_by_source_id[result.source.source_id] = result
        # Deterministic order regardless of completion order: the
        # registry's own source order, so a run's accumulated events and
        # reported data never depend on which worker happened to finish
        # first (`max_source_workers`'s own docstring above).
        results = [results_by_source_id[source.source_id] for source in sources]

    events: list[Event] = []
    for source_result in results:
        active_reporter.record_source(
            source_result.source.source_id,
            source_result.source.org_name,
            source_result.events,
            error=source_result.error,
        )
        events.extend(source_result.events)

    for enricher in enrichers:
        events = list(enricher.enrich(events))

    resolved_site_dir = Path(site_dir) if site_dir is not None else get_site_dir()
    resolved_partners_path = (
        Path(partners_path)
        if partners_path is not None
        else resolved_site_dir / "src" / "data" / "partners.json"
    )
    source_org_names = {source.source_id: source.org_name for source in sources}

    # Event Image Downloader (sprint 008 ticket 008, issue 19 scraper
    # half): constructed here, not defaulted inside `normalize_run()`
    # itself, so `normalize` never imports `export` (see
    # `normalize.run._to_opportunity`'s own comment on this) and so a
    # single `EventImageDownloader` instance's dedup cache is shared
    # across every source's events in this one `run()` call. Skipped
    # entirely under `dry_run` -- see this parameter's own docstring for
    # why constructing it would violate `dry_run`'s "no disk writes"
    # contract.
    resolved_image_resolver = image_resolver
    if resolved_image_resolver is None and not dry_run:
        resolved_image_resolver = EventImageDownloader(
            resolved_site_dir / "public" / "images" / "opportunities"
        ).download

    opportunities = normalize_run(
        events,
        resolved_partners_path,
        source_org_names=source_org_names,
        image_resolver=resolved_image_resolver,
    )
    active_reporter.record_opportunities(opportunities)

    result = export_opportunities(
        opportunities,
        site_dir=resolved_site_dir,
        today=today,
        dry_run=dry_run,
    )

    # Ad Content Export (sprint 005 ticket 005): one more "write a site
    # data-contract file" sequencing step, structurally identical to the
    # Site Export call above -- see sprint.md's self-review note on
    # Pipeline's fan-out. Additive: existing callers/tests that only
    # inspect run()'s own return value are unaffected.
    export_ads(
        load_ad_configs(Path(ads_dir) if ads_dir is not None else None),
        site_dir=resolved_site_dir,
        dry_run=dry_run,
    )

    return result
