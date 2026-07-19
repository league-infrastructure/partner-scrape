"""The ``generic_html`` Adapter: sitemap discovery + the extraction ladder.

See ``sprint.md``'s Architecture > ``generic_html`` Adapter, SUC-009 and
SUC-010. This module is thin glue only, per sprint.md's Design
Rationale on why Sitemap Discovery and the Generic HTML Extractor are
separate modules from the adapter itself: ``discover()`` delegates
entirely to ``discovery.sitemap.discover_changed_urls`` (ticket 001),
``fetch()`` is the same standard ``fetcher.get(ref.url)`` every
structured-API adapter uses, and ``extract()`` delegates field recovery
to ``extract.ladder.extract_fields`` before constructing the one thing
that *is* this module's job: the canonical ``Event``.
"""

from __future__ import annotations

import logging
from typing import Iterable

from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.discovery.sitemap import discover_changed_urls
from partner_scrape.extract.ladder import extract_fields
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it
#: sets via the ladder's per-field confidence (never a single uniform
#: value -- see sprint.md's Architecture > Generic HTML Extractor).
SOURCE_NAME = "generic_html"


class GenericHtmlAdapter:
    """``Adapter`` for arbitrary sitemap-discoverable sites (``generic_html``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> Iterable[EventRef]:
        """Resolve ``source`` into new/changed event ``EventRef``s via
        ticket 001's sitemap-diff discovery -- no logic of its own.
        """
        return discover_changed_urls(source, fetcher)

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        """Standard single-page GET, matching every other adapter's
        ``fetch()`` -- a ``generic_html`` ``EventRef`` is just a URL.
        """
        response = fetcher.get(ref.url)
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        """Run the extraction ladder over one fetched page and construct
        a canonical ``Event`` from its field+confidence output.

        A non-200 fetch or a page with no usable title anywhere in the
        ladder is dropped -- logged and skipped, never raised, matching
        sprint 001's per-record error isolation convention (one bad page
        must not fail the rest of the source).
        """
        if raw.status != 200:
            logger.warning(
                "generic_html page fetch %s returned status %s; skipping",
                raw.ref.url,
                raw.status,
            )
            return []

        fields = extract_fields(raw.body, raw.ref.url)

        title, _ = fields.get("title", ("", 0.0))
        title = (title or "").strip()
        if not title:
            logger.warning(
                "generic_html page %s has no usable title in any ladder rung; skipping",
                raw.ref.url,
            )
            return []

        event = Event(kind="event", source_id=source.source_id, url=raw.ref.url)
        for field_name, (value, confidence) in fields.items():
            event.set(field_name, value, source=SOURCE_NAME, confidence=confidence)

        return [event]
