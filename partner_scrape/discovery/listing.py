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

**(Sprint 027 ticket 006 exception revision)** ``discover_via_selector``
is a sibling to ``discover_via_listing``, used by
``ProgramListingAdapter.discover()`` only when ``source.config`` sets
``link_selector`` -- a CSS selector string. Where ``discover_via_listing``
assumes a card's *target URL* is itself program-shaped (``EVENT_PATH_RE``),
``discover_via_selector`` assumes the *source page's markup* around each
card (a ``data-*`` attribute, a class name) is what reliably identifies
it, regardless of where the link then points -- the shape UCSD's Summer
Program Finder actually has (see ``adapters/DESIGN.md``'s Revision note).
The two functions share the per-listing-page fetch loop
(:func:`_iter_listing_pages`) and differ only in how links are picked out
of the parsed tree. Same statelessness, same no-domain-restriction, same
per-page failure isolation as its sibling -- see ``discovery/DESIGN.md``'s
own Revision note.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from lxml import html as lxml_html

from partner_scrape.adapters.base import EventRef, acquisition_kwargs
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


def _extract_selector_links(body: str, page_url: str, link_selector: str) -> list[str]:
    """Parse ``body`` and return the absolute URL of every element's
    ``href`` matched by ``link_selector`` (an operator-authored CSS
    selector), in document order and deduplicated -- the
    markup-structure-driven sibling of :func:`_extract_matching_links`.

    An element matched by the selector with no ``href`` attribute (or an
    empty one) contributes nothing -- a selector is expected to target
    the anchor itself (e.g. ``li[data-grade*="High School"] a.learnmore``),
    but this stays defensive rather than raising if it targets a
    non-anchor ancestor by mistake.

    Malformed/unparseable HTML yields an empty list (with a logged
    warning) rather than raising, matching
    :func:`_extract_matching_links`'s own handling.
    """
    try:
        tree = lxml_html.fromstring(body)
    except Exception:
        logger.warning("Listing page %s is not parseable HTML; skipping", page_url)
        return []

    matched: dict[str, None] = {}
    for element in tree.cssselect(link_selector):
        href = element.get("href")
        if not href:
            continue
        href = href.strip()
        if not href:
            continue
        absolute = urljoin(page_url, href)
        matched.setdefault(absolute, None)
    return list(matched)


def _iter_listing_pages(source: SourceConfig, fetcher: Fetcher) -> list[tuple[str, str]]:
    """Fetch every one of ``source.config["listing_urls"]`` (resolved
    against ``source.config["site_url"]``) and return the ``(resolved_url,
    body)`` pairs for the pages that returned HTTP 200.

    Shared per-listing-page fetch loop for :func:`discover_via_listing`
    and :func:`discover_via_selector` -- the two functions differ only in
    how links are picked out of each page's parsed tree, not in how the
    pages themselves are resolved and fetched. An unreachable (non-200)
    listing page is logged and skipped -- per-page isolation means it
    does not prevent any other configured listing page on the same
    source from still being processed.
    """
    site_url = source.config["site_url"]
    listing_urls = source.config["listing_urls"]

    pages: list[tuple[str, str]] = []
    for listing_url in listing_urls:
        resolved_url = _resolve_listing_url(site_url, listing_url)
        response = fetcher.get(resolved_url, **acquisition_kwargs(source))
        if response.status != 200:
            logger.warning(
                "Listing page %s for source %r returned status %s; skipping",
                resolved_url,
                source.source_id,
                response.status,
            )
            continue
        pages.append((resolved_url, response.body))

    return pages


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
    refs: list[EventRef] = []
    for page_url, body in _iter_listing_pages(source, fetcher):
        for url in _extract_matching_links(body, page_url):
            refs.append(EventRef(url=url))

    return refs


def discover_via_selector(source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
    """Resolve ``source``'s configured listing page(s) into ``EventRef``s
    via a CSS selector rather than ``EVENT_PATH_RE`` path matching.

    Used only when ``source.config["link_selector"]`` is set (a CSS
    selector string, e.g. ``li[data-grade*="High School"] a.learnmore``).
    Fetches each URL in ``source.config["listing_urls"]`` exactly as
    :func:`discover_via_listing` does (same resolution against
    ``site_url``, same per-page non-200 isolation -- see
    :func:`_iter_listing_pages`), but picks links via ``lxml``'s
    ``tree.cssselect(link_selector)`` instead of matching every ``<a
    href>`` against ``EVENT_PATH_RE``. No domain restriction, matching
    ``discover_via_listing``'s own already-documented behavior -- see
    this module's docstring and ``discovery/DESIGN.md``'s Revision note.

    Every call re-crawls every configured listing page in full -- no
    diffing against a prior result, same as ``discover_via_listing``.
    """
    link_selector = source.config["link_selector"]

    refs: list[EventRef] = []
    for page_url, body in _iter_listing_pages(source, fetcher):
        for url in _extract_selector_links(body, page_url, link_selector):
            refs.append(EventRef(url=url))

    return refs
