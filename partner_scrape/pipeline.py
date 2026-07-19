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
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, Protocol, Sequence

from partner_scrape.adapters import run as run_adapter
from partner_scrape.config import get_site_dir
from partner_scrape.export import export_opportunities
from partner_scrape.fetch import Fetcher, PoliteFetcher
from partner_scrape.model import Event
from partner_scrape.normalize import run as normalize_run
from partner_scrape.registry import load_active_sources

logger = logging.getLogger(__name__)


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
        fetcher: the `Fetcher` each adapter retrieves raw content
            through. Defaults to a real `PoliteFetcher()` (robots.txt +
            rate limiting + on-disk cache under `$SCRAPE_CACHE_DIR`) when
            omitted -- the production path. Tests inject a fixture
            `Fetcher` here so the whole run touches no sockets.
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

    events: list[Event] = []
    for source in sources:
        try:
            source_events = run_adapter(source, active_fetcher)
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
