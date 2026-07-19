"""UCSD Localist calendar API adapter.

Serves Birch Aquarium (this ticket's registered source) and, per issue
06's framing, any future UCSD/campus source registered against this same
``adapter_type`` -- ``calendar.ucsd.edu/api/2/events`` is a structured,
first-party JSON feed filterable by ``group_id``, in the same spirit as
``adapters/tec.py``'s proven ``tec_rest`` pattern (trivial discovery = a
paginated API probe; no separate discovery module needed).

Every field this adapter sets is high-trust -- Localist's API is a
structured, first-party feed, so every ``Event.set(...)`` call below
uses :data:`CONFIDENCE` (1.0), matching TEC's convention.

**Critical implementation detail**: confirmed live during sprint 003
planning, Localist's ``/api/2/events`` returns one row per matching
*day* for a recurring event, not one row per event -- a single Birch
"Shark Summer" event (``id=52950294007943``) appeared as 9 separate rows
across a ``days=180`` window, all sharing that same ``id``. :func:`extract`
therefore deduplicates by the API's own ``id`` *within one fetched page*
before constructing Events -- this is this adapter's primary defense
against duplicate Events for the same underlying occurrence; Normalize &
Dedup's existing recurring-instance collapse is a second line of
defense, not relied on here.

Field-mapping decisions made by this implementation (documented per the
ticket's "implementer's call" note):
- Localist's ``tags`` maps to ``Event.tags``; ``keywords`` maps to
  ``Event.categories`` -- kept as two separate lists rather than folded
  together, matching TEC's existing tags/categories split.
- Localist's ``photo_url`` (present on some events) maps to
  ``Event.image_url``, matching the Constraints' "image ... if present"
  ask even though the ticket's detailed field list doesn't name a raw
  field -- Localist's public API names this field ``photo_url``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Iterable

from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "localist"

#: Localist's API is a structured, first-party feed -- every field this
#: adapter sets is maximally trusted, matching TEC's convention.
CONFIDENCE = 1.0

#: Default query window when a source's ``config`` omits ``days``/``pp``
#: -- sprint.md's Open Question 3 proposes this generous window so
#: Birch's current+upcoming events are reliably captured; Site Export's
#: own current/upcoming filter does the real date-relevance trimming
#: downstream, matching TEC's ``start_date=now``-then-filter precedent.
DEFAULT_DAYS = 180
DEFAULT_PP = 50


def _parse_date(value: str) -> datetime | None:
    """Parse a Localist ``first_date``/``last_date`` (date-only ISO string).

    Returns ``None`` for an absent/empty value. Raises ``ValueError`` on
    an unparseable non-empty value -- left uncaught here so the caller
    (``_extract_one``) can isolate it as a whole-record failure, matching
    TEC's ``_parse_datetime`` convention.
    """
    if not value:
        return None
    return datetime.fromisoformat(value)


def _extract_location(raw_event: dict[str, Any]) -> str:
    """Build a single display string from ``location_name`` + ``room_number``."""
    location_name = (raw_event.get("location_name") or "").strip()
    room_number = (raw_event.get("room_number") or "").strip()
    if location_name and room_number:
        return f"{location_name}, {room_number}"
    return location_name or room_number


def _registration_url(raw_event: dict[str, Any], api_domain: str) -> str:
    """Resolve the event's canonical page URL.

    Prefers Localist's own ``url`` field (``.strip()``'d -- a
    live-captured sample had a trailing space); falls back to
    constructing ``{api_domain}/event/{urlname}`` when ``url`` is empty.
    """
    url = (raw_event.get("url") or "").strip()
    if url:
        return url
    urlname = (raw_event.get("urlname") or "").strip()
    if urlname:
        return f"https://{api_domain}/event/{urlname}"
    return ""


def _extract_one(raw_event: dict[str, Any], source: SourceConfig, api_domain: str) -> Event:
    """Map one raw Localist event record into a canonical ``Event``.

    Raises:
        ValueError: the record has no usable title.
        ValueError: a ``first_date``/``last_date`` value is present but
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

    description = (raw_event.get("description_text") or "").strip()
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_date(raw_event.get("first_date") or "")
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    end = _parse_date(raw_event.get("last_date") or "")
    if end is not None:
        event.set("end", end, source=SOURCE_NAME, confidence=CONFIDENCE)

    location = _extract_location(raw_event)
    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    cost = (raw_event.get("ticket_cost") or "").strip()
    if cost:
        event.set("cost", cost, source=SOURCE_NAME, confidence=CONFIDENCE)

    registration_url = _registration_url(raw_event, api_domain)
    if registration_url:
        event.set(
            "registration_url", registration_url, source=SOURCE_NAME, confidence=CONFIDENCE
        )

    image_url = (raw_event.get("photo_url") or "").strip()
    if image_url:
        event.set("image_url", image_url, source=SOURCE_NAME, confidence=CONFIDENCE)

    tags = [t.strip() for t in raw_event.get("tags") or [] if t and str(t).strip()]
    if tags:
        event.set("tags", tags, source=SOURCE_NAME, confidence=CONFIDENCE)

    categories = [k.strip() for k in raw_event.get("keywords") or [] if k and str(k).strip()]
    if categories:
        event.set("categories", categories, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


def _api_domain(api_base: str) -> str:
    """Extract the host to build a fallback event URL against.

    ``api_base`` is e.g. ``https://calendar.ucsd.edu/api/2/events`` --
    the fallback registration URL lives at ``https://<host>/event/...``,
    not under ``/api/2/...``.
    """
    without_scheme = api_base.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0]


def _page_url(api_base: str, group_id: str, days: int, pp: int, page: int) -> str:
    return f"{api_base}?group_id={group_id}&days={days}&pp={pp}&page={page}"


class LocalistAdapter:
    """``Adapter`` for the UCSD Localist calendar API (``localist``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Probe ``page=1`` with a cheap ``pp=1`` request to learn the
        real query's page count, then enumerate one ``EventRef`` per
        real (configured ``pp``) page -- matching TEC's probe-then-
        paginate shape.

        A probe that fails to fetch or parse is treated as "exactly one
        page" rather than raising -- per-source failure isolation
        belongs to the Pipeline; this adapter degrades gracefully rather
        than crashing the whole run.
        """
        api_base = source.config["api_base"]
        group_id = source.config["group_id"]
        days = int(source.config.get("days", DEFAULT_DAYS))
        pp = int(source.config.get("pp", DEFAULT_PP))

        probe_url = _page_url(api_base, group_id, days, pp=1, page=1)
        probe = fetcher.get(probe_url)

        total_pages = 1
        if probe.status == 200:
            try:
                data = json.loads(probe.body)
                total_pages = max(1, int((data.get("page") or {}).get("total", 1)))
            except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
                logger.warning(
                    "Localist probe for %s returned unparseable JSON; assuming 1 page",
                    api_base,
                )
        else:
            logger.warning(
                "Localist probe for %s returned status %s; assuming 1 page",
                api_base,
                probe.status,
            )

        return [
            EventRef(url=_page_url(api_base, group_id, days, pp, page))
            for page in range(1, total_pages + 1)
        ]

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        response = fetcher.get(ref.url)
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "Localist page fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning("Localist page %s returned unparseable JSON; skipping", raw.ref.url)
            return []

        if not isinstance(data, dict):
            logger.warning(
                "Localist page %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        api_domain = _api_domain(source.config.get("api_base", ""))

        events: list[Event] = []
        seen_ids: set[str] = set()
        for wrapper in data.get("events") or []:
            raw_event = wrapper.get("event") if isinstance(wrapper, dict) else None
            if not raw_event:
                continue

            event_id = str(raw_event.get("id") or "")
            if event_id and event_id in seen_ids:
                # Localist returns one row per matching *day* for a
                # recurring event -- collapse the repeated rows to a
                # single Event here (see module docstring). This is the
                # primary dedup mechanism; Normalize & Dedup's recurring-
                # instance collapse is only a second line of defense.
                continue

            try:
                event = _extract_one(raw_event, source, api_domain)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed Localist event record on %s: %s", raw.ref.url, exc
                )
                continue

            if event_id:
                seen_ids.add(event_id)
            events.append(event)

        return events
