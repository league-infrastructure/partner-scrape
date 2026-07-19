"""Listing-page discovery: resolves a source's listing page(s) into
event/program URLs by crawling and pattern-matching anchor links.

See ``sprint.md``'s Architecture > Listing-Page Discovery, SUC-014 -- a
second discovery strategy alongside ``discovery/sitemap.py``'s
sitemap-diff discovery, for sites confirmed to have no sitemap (e.g.
Fleet Science Center's ``/events`` page, a single, non-paginating Drupal
Views listing). This module is a sibling of ``discovery/sitemap.py``, not
a modification of it -- that file stays untouched, and this module
imports its ``EVENT_PATH_RE`` rather than duplicating it.

**Deliberately no incremental diffing**: unlike ``discovery/sitemap.py``,
this module does not diff against a persisted snapshot. A listing page
carries no ``<lastmod>``-equivalent signal to diff against, so every
link matching the event-path pattern on every configured listing page is
returned as an ``EventRef`` on every call -- no ``SCRAPE_CACHE_DIR``
write, no snapshot state. See ``sprint.md``'s Design Rationale ("Listing-
Page Discovery does no incremental diffing") and Open Question 2 -- this
is a deliberate, scale-appropriate scope decision for Fleet's ~10-page
listing, not an oversight.

This module depends only on ``Fetch & Cache``'s ``Fetcher`` protocol,
``registry.schema.SourceConfig``, and ``adapters.base.EventRef`` --
mirroring ``discovery/sitemap.py``'s exact dependency shape -- never the
``Adapter`` protocol or dispatch table. It does not compose into a
working adapter itself; that is ticket 004's ``listing_html`` Adapter.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from lxml import html as lxml_html

from partner_scrape.adapters.base import EventRef
from partner_scrape.discovery.sitemap import EVENT_PATH_RE
from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)


def _resolve_listing_url(site_url: str, listing_url: str) -> str:
    """Resolve one ``source.config["listing_urls"]`` entry against
    ``site_url``.

    An entry that is already an absolute URL (``http://``/``https://``)
    is used as-is; a bare path (Fleet's is ``"/events"``) is joined onto
    ``site_url`` -- the same resolution ``discovery/sitemap.py`` applies
    to ``site_url`` itself when building its own candidate URLs.
    """
    if listing_url.startswith("http://") or listing_url.startswith("https://"):
        return listing_url
    return f"{site_url.rstrip('/')}/{listing_url.lstrip('/')}"


def _extract_matching_links(body: str, page_url: str) -> list[str]:
    """Parse ``body`` and return the absolute URL of every ``<a href>``
    matching :data:`discovery.sitemap.EVENT_PATH_RE`, in document order
    and deduplicated -- a listing page commonly links the same detail
    page more than once (e.g. a thumbnail anchor and a title anchor both
    pointing at the same ``/events/{slug}`` URL), and this module returns
    one ``EventRef`` per distinct URL, not per anchor tag.

    Malformed/unparseable HTML yields an empty list (with a logged
    warning) rather than raising, matching ``extract/ladder.py``'s own
    ``lxml.html.fromstring`` error handling.
    """
    try:
        tree = lxml_html.fromstring(body)
    except Exception:
        logger.warning("Listing page %s is not parseable HTML; skipping", page_url)
        return []

    matched: dict[str, None] = {}
    for href in tree.xpath("//a/@href"):
        href = href.strip()
        if not href:
            continue
        absolute = urljoin(page_url, href)
        if not EVENT_PATH_RE.search(absolute):
            continue
        matched.setdefault(absolute, None)
    return list(matched)


def discover_via_listing(source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
    """Resolve ``source``'s configured listing page(s) into ``EventRef``s.

    Fetches each URL in ``source.config["listing_urls"]`` via the
    injected ``fetcher`` (resolved against ``source.config["site_url"]``
    the same way ``discovery/sitemap.py`` resolves ``site_url``),
    extracts every ``<a href>`` target matching the event-path pattern,
    and returns one ``EventRef`` per matched link across all configured
    pages.

    Every call re-crawls every configured listing page in full and
    returns every currently-matching link -- no diffing against a prior
    result, by design (see this module's docstring).

    An unreachable (non-200) listing page is logged and skipped -- zero
    ``EventRef``s for that page, but per-page isolation means it does not
    prevent any other configured listing page on the same source from
    still being processed.
    """
    site_url = source.config["site_url"]
    listing_urls = source.config["listing_urls"]

    refs: list[EventRef] = []
    for listing_url in listing_urls:
        resolved_url = _resolve_listing_url(site_url, listing_url)
        response = fetcher.get(resolved_url)
        if response.status != 200:
            logger.warning(
                "Listing page %s for source %r returned status %s; skipping",
                resolved_url,
                source.source_id,
                response.status,
            )
            continue

        for url in _extract_matching_links(response.body, resolved_url):
            refs.append(EventRef(url=url))

    return refs
