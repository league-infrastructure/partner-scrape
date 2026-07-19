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

import logging
from datetime import date
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from partner_scrape.adapters import run as run_adapter
from partner_scrape.config import get_site_dir
from partner_scrape.export import export_opportunities
from partner_scrape.fetch import Fetcher, PlaywrightFetcher, PoliteFetcher
from partner_scrape.model import Event
from partner_scrape.normalize import run as normalize_run
from partner_scrape.registry import load_active_sources

logger = logging.getLogger(__name__)

#: `acquisition_policy.fetch_strategy` value that routes a source
#: through the lazily-constructed headless `Fetcher` instead of the
#: run's default one. Every other value (including the registry
#: default, `"static"`) uses the default `Fetcher` unchanged.
HEADLESS_FETCH_STRATEGY = "headless"


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


def run(
    registry_dir: str | Path | None = None,
    site_dir: str | Path | None = None,
    *,
    fetcher: Fetcher | None = None,
    headless_fetcher_factory: Callable[[], Fetcher] | None = None,
    enrichers: Sequence[Enricher] = (),
    partners_path: str | Path | None = None,
    source_id: str | None = None,
    limit: int | None = None,
    today: date | None = None,
    dry_run: bool = False,
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
            `dry_run`).

    Returns:
        The list of opportunity dicts that were (or, for `dry_run`,
        would have been) written -- `export_opportunities`'s return
        value, passed through unchanged.
    """
    sources = load_active_sources(Path(registry_dir) if registry_dir is not None else None)

    if source_id is not None:
        sources = [s for s in sources if s.source_id == source_id]
    if limit is not None:
        sources = sources[:limit]

    active_fetcher = fetcher if fetcher is not None else PoliteFetcher()
    build_headless_fetcher = headless_fetcher_factory or _build_default_headless_fetcher
    # Lazily constructed on the first `headless`-flagged active source
    # this run actually reaches -- `None` here means "not built yet",
    # never "built once, never rebuilt" for a run with zero `headless`
    # sources (ticket 005's Acceptance Criteria: constructed at most
    # once, and only when at least one active source needs it).
    headless_fetcher: Fetcher | None = None

    events: list[Event] = []
    for source in sources:
        fetch_strategy = source.acquisition_policy.get("fetch_strategy", "static")
        if fetch_strategy == HEADLESS_FETCH_STRATEGY:
            if headless_fetcher is None:
                headless_fetcher = build_headless_fetcher()
            source_fetcher = headless_fetcher
        else:
            source_fetcher = active_fetcher

        try:
            source_events = run_adapter(source, source_fetcher)
        except Exception:
            # Per-source error isolation (SUC-008): one broken source is
            # logged and skipped, never fatal to the rest of the run.
            logger.exception(
                "Source %r (adapter_type=%r) failed; skipping it, run continues "
                "with the remaining sources",
                source.source_id,
                source.adapter_type,
            )
            continue
        logger.info("Source %r yielded %d event(s)", source.source_id, len(source_events))
        events.extend(source_events)

    for enricher in enrichers:
        events = list(enricher.enrich(events))

    resolved_site_dir = Path(site_dir) if site_dir is not None else get_site_dir()
    resolved_partners_path = (
        Path(partners_path)
        if partners_path is not None
        else resolved_site_dir / "src" / "data" / "partners.json"
    )
    source_org_names = {source.source_id: source.org_name for source in sources}

    opportunities = normalize_run(
        events, resolved_partners_path, source_org_names=source_org_names
    )

    return export_opportunities(
        opportunities,
        site_dir=resolved_site_dir,
        today=today,
        dry_run=dry_run,
    )
