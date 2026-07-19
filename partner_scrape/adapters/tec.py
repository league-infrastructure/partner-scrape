"""The Events Calendar (TEC) REST API adapter.

The highest-quality, best-proven source tier per
``dev/SCRAPER_GUIDELINES.md`` #2: 100% dated, structured JSON, no HTML
parsing. Field mapping and pagination strategy are reused from the
proven ``dev/fetch_tec_api.py`` script, rewritten fresh against the
canonical ``Event`` shape (ticket 001) rather than that script's flat
dict.

Every field this adapter sets is high-trust -- TEC's API is a
structured, first-party feed, so every ``Event.set(...)`` call below
uses :data:`CONFIDENCE` (1.0).

Not mapped: TEC's ``organizer`` field. The canonical ``Event`` model
(ticket 001, frozen by the time this ticket runs) has no organizer
field -- adding one would be a ticket 001 model change, out of this
ticket's scope.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Iterable

from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "tec_rest"

#: TEC's API is a structured, first-party feed -- every field this
#: adapter sets is maximally trusted (sprint.md Architecture: "highest-
#: trust source this sprint handles").
CONFIDENCE = 1.0

#: Events per page for the real paginated fetches (matches
#: dev/fetch_tec_api.py's proven value). The initial probe uses
#: ``per_page=1`` instead -- see ``discover()``.
PAGE_SIZE = 50

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_HTML_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&#8217;": "'",
    "&#8220;": '"',
    "&#8221;": '"',
    "&nbsp;": " ",
    "&#8211;": "-",
}


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode the common entities TEC descriptions use.

    Reuses ``dev/fetch_tec_api.py``'s proven approach: TEC's
    ``description``/``excerpt`` fields are rendered HTML, and this is
    enough to get clean plain text without a full HTML parser
    dependency.
    """
    stripped = _TAG_RE.sub(" ", text)
    stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
    for entity, replacement in _HTML_ENTITIES.items():
        stripped = stripped.replace(entity, replacement)
    return stripped


def _parse_datetime(value: str) -> datetime | None:
    """Parse a TEC ``start_date``/``end_date`` string.

    Returns ``None`` for an absent/empty value. Raises ``ValueError`` on
    an unparseable non-empty value -- left uncaught here so the caller
    (``_extract_one``) can isolate it as a whole-record failure, per
    this ticket's per-record error isolation requirement.
    """
    if not value:
        return None
    return datetime.fromisoformat(value)


def _extract_location(venue: dict[str, Any]) -> str:
    """Build a single display string from TEC's structured ``venue`` object."""
    parts = [
        venue.get("venue", ""),
        venue.get("address", ""),
        venue.get("city", ""),
        venue.get("state", ""),
    ]
    return ", ".join(part.strip() for part in parts if part and part.strip())


def _extract_one(raw_event: dict[str, Any], source: SourceConfig) -> Event:
    """Map one raw TEC event record into a canonical ``Event``.

    Raises:
        ValueError: the record has no usable title.
        ValueError: a ``start_date``/``end_date`` value is present but
            unparseable.

    Both are caught by the caller (``extract()``) and treated as a
    per-record skip -- never fatal to the rest of the page.
    """
    title = (raw_event.get("title") or "").strip()
    if not title:
        raise ValueError("event record has no title")

    event = Event(kind="event", source_id=source.source_id)
    event.external_id = str(raw_event.get("id") or "")

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    description = _strip_html(raw_event.get("description") or "")
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_datetime(raw_event.get("start_date") or "")
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    end = _parse_datetime(raw_event.get("end_date") or "")
    if end is not None:
        event.set("end", end, source=SOURCE_NAME, confidence=CONFIDENCE)

    event.set(
        "all_day", bool(raw_event.get("all_day", False)), source=SOURCE_NAME, confidence=CONFIDENCE
    )

    location = _extract_location(raw_event.get("venue") or {})
    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    cost = (raw_event.get("cost") or "").strip()
    if cost:
        event.set("cost", cost, source=SOURCE_NAME, confidence=CONFIDENCE)

    registration_url = (raw_event.get("url") or "").strip()
    if registration_url:
        event.set(
            "registration_url", registration_url, source=SOURCE_NAME, confidence=CONFIDENCE
        )

    image_url = ((raw_event.get("image") or {}).get("url") or "").strip()
    if image_url:
        event.set("image_url", image_url, source=SOURCE_NAME, confidence=CONFIDENCE)

    categories = [c.get("name", "") for c in raw_event.get("categories") or [] if c.get("name")]
    if categories:
        event.set("categories", categories, source=SOURCE_NAME, confidence=CONFIDENCE)

    tags = [t.get("name", "") for t in raw_event.get("tags") or [] if t.get("name")]
    if tags:
        event.set("tags", tags, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


def _page_url(api_base: str, page: int) -> str:
    """Build one paginated TEC events page URL.

    ``status=publish`` and ``start_date=now`` match
    ``dev/SCRAPER_GUIDELINES.md`` #2's recommended approach -- only
    published, future-dated events, matching this ticket's "request
    future events where the API supports it" constraint.
    """
    return f"{api_base}?per_page={PAGE_SIZE}&page={page}&status=publish&start_date=now"


class TecRestAdapter:
    """``Adapter`` for The Events Calendar's public REST API (``tec_rest``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Probe ``{api_base}?per_page=1`` to learn ``total_pages``, then
        enumerate one ``EventRef`` per real (``per_page=50``) page.

        A probe that fails to fetch or parse is treated as "exactly one
        page" rather than raising -- this ticket's per-source failure
        isolation belongs to the Pipeline (ticket 008); this adapter
        degrades gracefully rather than crashing the whole run.
        """
        api_base = source.config["api_base"]
        probe_url = f"{api_base}?per_page=1&status=publish&start_date=now"
        probe = fetcher.get(probe_url)

        total_pages = 1
        if probe.status == 200:
            try:
                data = json.loads(probe.body)
                total_pages = max(1, int(data.get("total_pages", 1)))
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning(
                    "TEC probe for %s returned unparseable JSON; assuming 1 page", api_base
                )
        else:
            logger.warning(
                "TEC probe for %s returned status %s; assuming 1 page", api_base, probe.status
            )

        return [EventRef(url=_page_url(api_base, page)) for page in range(1, total_pages + 1)]

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        response = fetcher.get(ref.url)
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "TEC page fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning("TEC page %s returned unparseable JSON; skipping", raw.ref.url)
            return []

        events: list[Event] = []
        for raw_event in data.get("events", []):
            try:
                events.append(_extract_one(raw_event, source))
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed TEC event record on %s: %s", raw.ref.url, exc
                )
        return events
