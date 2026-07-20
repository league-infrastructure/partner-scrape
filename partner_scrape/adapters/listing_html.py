"""The ``listing_html`` Adapter: listing-page discovery + the extraction ladder.

See ``sprint.md``'s Architecture > ``listing_html`` Adapter, SUC-014. This
module is thin glue only, structurally parallel to ``generic_html.py``
(same ``fetch()``, same ``extract.ladder.extract_fields`` call, same
``Event`` construction) and per sprint.md's Design Rationale on why
Listing-Page Discovery and the Generic HTML Extractor stay separate
modules from the adapter itself: ``discover()`` delegates entirely to
``discovery.listing.discover_via_listing`` (ticket 003) instead of
``discovery.sitemap.discover_changed_urls`` -- the only difference from
``generic_html`` -- and ``extract()`` delegates field recovery to
``extract.ladder.extract_fields`` (unchanged, sprint 002) before
constructing the canonical ``Event``.
"""

from __future__ import annotations

import logging
from typing import Iterable

from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.extract.ladder import extract_fields
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it
#: sets via the ladder's per-field confidence (never a single uniform
#: value -- matches ``generic_html``'s own convention; see sprint.md's
#: Architecture > Generic HTML Extractor).
SOURCE_NAME = "listing_html"


class ListingHtmlAdapter:
    """``Adapter`` for no-sitemap sites discoverable via a listing page
    (``listing_html``).

    Structurally identical to ``GenericHtmlAdapter`` apart from
    ``discover()`` -- see this module's docstring.
    """

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> Iterable[EventRef]:
        """Resolve ``source`` into event ``EventRef``s via listing-page
        discovery -- no discovery logic of its own.

        The import is deferred to call time to break the import cycle
        between ``adapters`` (whose package ``__init__`` eagerly imports
        every adapter, including this one) and ``discovery.listing``
        (which imports ``EventRef`` from ``adapters.base``).
        """
        from partner_scrape.discovery.listing import discover_via_listing

        return discover_via_listing(source, fetcher)

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        """Standard single-page GET, matching every other adapter's
        ``fetch()`` -- a ``listing_html`` ``EventRef`` is just a URL.
        """
        response = fetcher.get(ref.url)
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        """Run the extraction ladder over one fetched page and construct
        a canonical ``Event`` from its field+confidence output -- the
        exact same logic as ``GenericHtmlAdapter.extract`` (sprint 002's
        ladder is reused unchanged, never duplicated).

        A non-200 fetch or a page with no usable title anywhere in the
        ladder is dropped -- logged and skipped, never raised, matching
        sprint 001's per-record error isolation convention (one bad page
        must not fail the rest of the source). Fleet's real detail pages
        carry no JSON-LD or ``<time>`` markup (confirmed live during
        sprint 003 planning), so in practice the OpenGraph and
        title-fallback rungs are what fire here, not the top JSON-LD/
        ``<time>`` rungs -- the ladder's existing priority order already
        handles this gracefully; no new rung is needed.
        """
        if raw.status != 200:
            logger.warning(
                "listing_html page fetch %s returned status %s; skipping",
                raw.ref.url,
                raw.status,
            )
            return []

        fields = extract_fields(raw.body, raw.ref.url)

        title, _ = fields.get("title", ("", 0.0))
        title = (title or "").strip()
        if not title:
            logger.warning(
                "listing_html page %s has no usable title in any ladder rung; skipping",
                raw.ref.url,
            )
            return []

        event = Event(kind="event", source_id=source.source_id, url=raw.ref.url)
        for field_name, (value, confidence) in fields.items():
            event.set(field_name, value, source=SOURCE_NAME, confidence=confidence)

        return [event]
