"""Sitemap-diff discovery: resolves a source's sitemap into new/changed URLs.

See ``sprint.md``'s Architecture > Sitemap Discovery, SUC-009. Fetches a
source's ``sitemap_index.xml`` (falling back to ``sitemap.xml``) via the
injected ``Fetcher``, identifies event/program-related URLs by sitemap
child-filename pattern (recursing into a ``<sitemapindex>``) or by
URL-path pattern for sites with no dedicated event sitemap, and diffs
the resulting ``{url: lastmod}`` set against a persisted snapshot for
``source.source_id`` under ``SCRAPE_CACHE_DIR`` -- only new or
``<lastmod>``-changed URLs come back as ``EventRef``s, and the snapshot
is rewritten to the current full state on every successful resolution.

Classification patterns are ported from ``dev/inventory_sitemaps.py``'s
``EVENT_PATTERNS``/``PROGRAM_PATTERNS`` and ``dev/lib/sitemap_parser.py``'s
inline event-path regex as a starting point, not a dependency -- ``dev/``
stays untouched (this ticket's Scope).

This module depends only on ``Fetch & Cache``'s ``Fetcher`` protocol,
``Config``, ``registry.schema.SourceConfig``, and ``adapters.base.EventRef``
(a plain, logic-free data shape shared by every adapter's ``discover()``,
imported directly from ``adapters.base`` rather than the heavier
``adapters`` package so no dispatch table or concrete adapter is pulled
in) -- never the ``Adapter`` protocol or dispatch table itself. Ticket
002's ``generic_html`` adapter calls into this module, never the other
way around (sprint.md's dependency-direction check).
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from partner_scrape import config
from partner_scrape.adapters.base import EventRef
from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: XML namespace every standard sitemap uses (sitemaps.org protocol),
#: matching ``dev/inventory_sitemaps.py``'s ``NS``.
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

#: Sitemap child-filename patterns for event content. Ported from
#: ``dev/inventory_sitemaps.py``'s ``EVENT_PATTERNS`` -- a starting
#: point, not a dependency.
EVENT_PATTERNS = re.compile(
    r"(tribe_events|tribe_event_series|tribe_events_cat|tribe_venue|tribe_organizer"
    r"|tec_recurring|ajde_events|stec_event|event|events)",
    re.IGNORECASE,
)

#: Sitemap child-filename patterns for program/course content. Ported
#: from ``dev/inventory_sitemaps.py``'s ``PROGRAM_PATTERNS``.
PROGRAM_PATTERNS = re.compile(
    r"(program|course|workshop|camp|class|training)", re.IGNORECASE
)

#: URL-path pattern applied to individual ``<loc>`` values -- the
#: fallback for sites with no dedicated event sitemap (a flat
#: ``sitemap.xml`` urlset, or a ``<sitemapindex>`` whose children have
#: no event/program-suggestive filename). Ported from
#: ``dev/lib/sitemap_parser.py``'s ``get_event_urls`` inline regex.
EVENT_PATH_RE = re.compile(
    r"/(events?|tribe_events|public-events?|science-events?|"
    r"programs?|courses?|camps?|classes|workshops?|training|calendar)(/|$)",
    re.IGNORECASE,
)

#: Candidate root sitemap filenames, tried in order against
#: ``{site_url}/{filename}`` (this ticket's Scope).
_ROOT_SITEMAP_FILENAMES = ("sitemap_index.xml", "sitemap.xml")

#: Subdirectory of ``SCRAPE_CACHE_DIR`` snapshots are stored under.
_SNAPSHOT_SUBDIR = "sitemap_snapshots"


def _snapshot_path(source_id: str) -> Path:
    """The on-disk path a source's ``{url: lastmod}`` snapshot lives at."""
    return config.get_scrape_cache_dir() / _SNAPSHOT_SUBDIR / f"{source_id}.json"


def _read_snapshot(path: Path) -> dict[str, str]:
    """Read a source's prior snapshot, or ``{}`` if this is the first
    run for it (no snapshot file on disk yet).
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_snapshot(path: Path, urls: dict[str, str]) -> None:
    """Persist ``urls`` as the source's new full-state snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2, sort_keys=True)


def _local_name(tag: str) -> str:
    """Strip a namespace URI off an ElementTree tag, e.g.
    ``{http://www.sitemaps.org/schemas/sitemap/0.9}urlset`` -> ``urlset``.
    """
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_urlset(root: ET.Element, *, path_filter: bool) -> dict[str, str]:
    """Extract ``{loc: lastmod}`` from a ``<urlset>`` root.

    ``path_filter`` applies :data:`EVENT_PATH_RE` to each ``<loc>`` --
    used when the urlset came from a generic (non-event-dedicated)
    sitemap and needs URL-path filtering; skipped when the urlset is
    already known to be event-dedicated (a filename-matched child
    sitemap from a ``<sitemapindex>``), where every URL in it is kept.
    """
    urls: dict[str, str] = {}
    for url_el in root.findall("sm:url", _NS):
        loc = (url_el.findtext("sm:loc", "", _NS) or "").strip()
        if not loc:
            continue
        if path_filter and not EVENT_PATH_RE.search(loc):
            continue
        lastmod = (url_el.findtext("sm:lastmod", "", _NS) or "").strip()
        urls[loc] = lastmod
    return urls


def _is_event_related_filename(loc: str) -> bool:
    """Whether a child sitemap's own filename (last path segment of its
    ``<loc>``) matches :data:`EVENT_PATTERNS` or :data:`PROGRAM_PATTERNS`.
    """
    filename = loc.rsplit("/", 1)[-1]
    return bool(EVENT_PATTERNS.search(filename) or PROGRAM_PATTERNS.search(filename))


def _parse_sitemap_index(root: ET.Element, fetcher: Fetcher) -> dict[str, str]:
    """Resolve a ``<sitemapindex>`` root into ``{loc: lastmod}`` across
    its children.

    Children whose filename matches :data:`EVENT_PATTERNS`/
    :data:`PROGRAM_PATTERNS` are fetched and fully included (no further
    path filtering -- an event-dedicated child sitemap's own URLs are
    trusted as-is; this is what keeps an unrelated sibling child, e.g. a
    page/post sitemap, from ever being fetched at all). If no child
    matches by filename, every child is fetched instead and its URLs
    are kept only when they pass :data:`EVENT_PATH_RE` -- the
    "URL-path pattern for sites with no dedicated event sitemap"
    fallback this ticket's Scope calls for.

    A child that fails to fetch (non-200) or fails to parse is logged
    and skipped -- per-child isolation, one bad child sitemap does not
    fail the whole source.
    """
    children = [
        (sm.findtext("sm:loc", "", _NS) or "").strip()
        for sm in root.findall("sm:sitemap", _NS)
    ]
    children = [loc for loc in children if loc]

    event_children = [loc for loc in children if _is_event_related_filename(loc)]
    candidates = event_children if event_children else children
    path_filter = not event_children

    urls: dict[str, str] = {}
    for child_url in candidates:
        response = fetcher.get(child_url)
        if response.status != 200:
            logger.warning(
                "Child sitemap %s returned status %s; skipping", child_url, response.status
            )
            continue
        try:
            child_root = ET.fromstring(response.body)
        except ET.ParseError:
            logger.warning("Child sitemap %s is not valid XML; skipping", child_url)
            continue
        if _local_name(child_root.tag) != "urlset":
            logger.warning(
                "Child sitemap %s has unrecognized root element %r; skipping",
                child_url,
                child_root.tag,
            )
            continue
        urls.update(_parse_urlset(child_root, path_filter=path_filter))
    return urls


def _fetch_root_sitemap(site_url: str, fetcher: Fetcher) -> tuple[str, str] | None:
    """Fetch the first of :data:`_ROOT_SITEMAP_FILENAMES` that resolves
    with a 200 status.

    Returns ``(url, body)`` for whichever candidate succeeded first, or
    ``None`` if neither candidate is reachable.
    """
    for filename in _ROOT_SITEMAP_FILENAMES:
        url = f"{site_url}/{filename}"
        response = fetcher.get(url)
        if response.status == 200:
            return url, response.body
        logger.info("Sitemap probe %s returned status %s", url, response.status)
    return None


def _resolve_event_urls(source: SourceConfig, fetcher: Fetcher) -> dict[str, str] | None:
    """Resolve ``source``'s sitemap(s) into ``{url: lastmod}`` for every
    discovered event/program page.

    Returns ``None`` (with a logged warning) on any unreachable,
    malformed, or unrecognized-root-element sitemap -- never raises,
    per SUC-009's Error Flow. A distinct return value from ``{}`` (a
    reachable, well-formed sitemap that simply matched no event URLs)
    matters to the caller: only a genuine failure should leave a prior
    snapshot untouched rather than overwriting it with an empty one.
    """
    site_url = source.config["site_url"].rstrip("/")

    fetched = _fetch_root_sitemap(site_url, fetcher)
    if fetched is None:
        logger.warning(
            "No reachable sitemap for source %r at %s (tried %s)",
            source.source_id,
            site_url,
            ", ".join(_ROOT_SITEMAP_FILENAMES),
        )
        return None
    root_url, body = fetched

    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        logger.warning(
            "Sitemap %s for source %r is not valid XML; skipping discovery",
            root_url,
            source.source_id,
        )
        return None

    tag = _local_name(root.tag)
    if tag == "sitemapindex":
        return _parse_sitemap_index(root, fetcher)
    if tag == "urlset":
        return _parse_urlset(root, path_filter=True)

    logger.warning(
        "Sitemap %s for source %r has unrecognized root element %r; skipping discovery",
        root_url,
        source.source_id,
        root.tag,
    )
    return None


def discover_changed_urls(source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
    """Resolve ``source``'s sitemap into the ``EventRef``s that are new
    or ``<lastmod>``-changed since the last run.

    Diffs the current ``{url: lastmod}`` set against a persisted
    snapshot for ``source.source_id`` under ``SCRAPE_CACHE_DIR``
    (``Config.get_scrape_cache_dir()``), then rewrites the snapshot to
    the current full state on success -- the next call against an
    unchanged sitemap yields zero ``EventRef``s (SUC-009's Main Flow;
    this ticket's round-trip testing requirement).

    No prior snapshot (first run for this source) treats every
    discovered URL as new. A malformed or unreachable sitemap yields an
    empty list and a logged warning rather than raising, and leaves any
    existing snapshot untouched (SUC-009's Error Flow) -- this function
    must never propagate an exception up through the calling adapter's
    ``discover()``.

    Each returned ``EventRef``'s ``context`` carries the sitemap's own
    ``lastmod`` value under the ``"lastmod"`` key, for adapters that
    want it as a date-recovery fallback signal.
    """
    current = _resolve_event_urls(source, fetcher)
    if current is None:
        return []

    snapshot_path = _snapshot_path(source.source_id)
    previous = _read_snapshot(snapshot_path)

    changed = [
        EventRef(url=url, context={"lastmod": lastmod})
        for url, lastmod in current.items()
        if previous.get(url) != lastmod
    ]

    _write_snapshot(snapshot_path, current)

    return changed
