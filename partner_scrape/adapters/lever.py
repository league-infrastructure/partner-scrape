"""Lever Postings public JSON API adapter.

See sprint.md's Architecture (ticket 004) and SUC-002: Lever's public
postings endpoint (``api.lever.co/v0/postings/{company}?mode=json``) is
**not paginated** -- confirmed live during sprint planning against
``api.lever.co/v0/postings/shieldai?mode=json`` (8 postings returned in
one response) -- so, like ``adapters/greenhouse.py``, ``discover()``
here returns exactly one ``EventRef``, no probe-then-paginate dance.

Real response shape (confirmed live): a **top-level JSON array**, not an
object with a ``jobs`` key -- the one structural difference from every
other structured-API adapter in this codebase (Greenhouse/TEC/Localist
all wrap their list in an object key; Lever does not)::

    [{"id": "41468aca-...", "text": "Aerostructures Design Engineer II",
      "categories": {"location": "United States",
        "commitment": "Full Time Employee", "team": "...", "department": "..."},
      "descriptionPlain": "...", "hostedUrl": "https://...",
      "applyUrl": "https://...", "createdAt": 1234567890000}]

Field mapping: ``external_id`` <- ``id``; ``title`` <- ``text``;
``description`` <- ``descriptionPlain`` (already plain text -- unlike
Greenhouse's HTML ``content``, no ``_strip_html`` step is needed here);
``start`` <- ``createdAt`` (epoch **milliseconds** -- divided by 1000
and interpreted as UTC via ``datetime.fromtimestamp(..., tz=timezone.
utc)``, matching this codebase's existing UTC-aware-datetime convention
-- see e.g. ``fetch/fetcher.py``'s ``fetched_at`` -- rather than a
local-timezone-dependent naive ``fromtimestamp`` that would make tests
flaky across machines); ``location`` <- ``categories.location``;
``registration_url`` <- ``applyUrl``, falling back to ``hostedUrl`` when
``applyUrl`` is absent. Every field this adapter sets is high-trust
(:data:`CONFIDENCE` 1.0), matching ``greenhouse.py``'s convention.

``categories.commitment`` is passed into ``ats_filters.classify_posting``
as an *additional* internship signal alongside ``text`` (the title) --
Lever's ``commitment`` field often says "Intern"/"Internship" directly, a
stronger signal than title-regex alone (sprint.md's SUC-002 Main Flow
step 2). ``categories.team`` is passed as the STEM-classification
``department`` text, per this ticket's Constraints (Lever's raw payload
also carries a separate ``categories.department`` key, but ``team`` is
the field this ticket specifies).

Every raw posting is run through ``adapters.ats_filters.classify_posting``
(ticket 002) *before* an ``Event`` is constructed; only a match becomes
an ``Event``, with ``kind="internship"`` and the verdict's default
``age_grade_level``/``time_of_day`` applied via ``Event.set(...)``.
Deliberately does not set ``Event.cost``/``Event.cost_range`` -- ticket
002's own contract (see ``ats_filters.py``'s module docstring), same as
``greenhouse.py``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from partner_scrape.adapters.ats_filters import classify_posting
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "lever"

#: Lever's public postings API is a structured, first-party feed --
#: every field this adapter sets is maximally trusted, matching
#: ``greenhouse.py``'s/``tec.py``'s convention.
CONFIDENCE = 1.0

#: Default Lever Postings API base, per sprint.md's confirmed-live
#: shape. A source's ``config`` may override this with its own
#: ``api_base`` key (mirrors ``greenhouse.py``'s own ``api_base`` config
#: convention).
DEFAULT_API_BASE = "https://api.lever.co/v0/postings"


def _parse_created_at(value: Any) -> datetime | None:
    """Parse a Lever ``createdAt`` epoch-milliseconds value into a UTC ``datetime``.

    Returns ``None`` for an absent/empty/zero value. Raises ``ValueError``/
    ``TypeError`` on an unparseable non-empty value -- left uncaught here
    so the caller (``_extract_one``) can isolate it as a whole-record
    failure, matching ``greenhouse.py``'s ``_parse_datetime`` convention.
    """
    if not value:
        return None
    return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)


def _extract_one(raw_posting: dict[str, Any], source: SourceConfig) -> Event | None:
    """Map one raw Lever posting record into a canonical internship ``Event``.

    Returns ``None`` when the posting does not pass
    ``ats_filters.classify_posting`` -- not an error, simply not a
    match, so the caller must not treat it as a skipped/malformed
    record.

    Raises:
        ValueError: the record has no usable title (``text``).
        ValueError: a ``createdAt`` value is present but unparseable.
        TypeError: a ``createdAt`` value is present but not numeric.

    All are caught by the caller (``extract()``) and treated as a
    per-record skip -- never fatal to the rest of the response, matching
    ``greenhouse.py``'s per-record isolation convention.
    """
    title = (raw_posting.get("text") or "").strip()
    if not title:
        raise ValueError("posting record has no text/title")

    categories = raw_posting.get("categories") or {}
    location = (categories.get("location") or "").strip()
    commitment = (categories.get("commitment") or "").strip()
    department = (categories.get("team") or "").strip()
    location_keywords = source.config.get("location_keywords")

    verdict = classify_posting(
        title,
        commitment=commitment,
        department=department,
        location=location,
        location_keywords=location_keywords,
    )
    if verdict is None:
        return None

    event = Event(kind="internship", source_id=source.source_id)
    event.external_id = str(raw_posting.get("id") or "")

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    description = (raw_posting.get("descriptionPlain") or "").strip()
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_created_at(raw_posting.get("createdAt"))
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    registration_url = (raw_posting.get("applyUrl") or raw_posting.get("hostedUrl") or "").strip()
    if registration_url:
        event.set(
            "registration_url", registration_url, source=SOURCE_NAME, confidence=CONFIDENCE
        )

    # Ticket 002's classification defaults -- deliberately no cost/
    # cost_range (see module docstring and ats_filters.py).
    event.set(
        "age_grade_level", verdict.age_grade_level, source=SOURCE_NAME, confidence=CONFIDENCE
    )
    event.set("time_of_day", verdict.time_of_day, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


def _postings_url(source: SourceConfig) -> str:
    """Build the one postings-JSON URL this source's ``discover()`` resolves to."""
    api_base = source.config.get("api_base") or DEFAULT_API_BASE
    company = source.config["company"]
    return f"{api_base}/{company}?mode=json"


class LeverAdapter:
    """``Adapter`` for the Lever Postings public JSON API (``lever``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Return exactly one ``EventRef`` for this company's postings-list URL.

        Lever's public postings endpoint is not paginated (module
        docstring) -- there is no probe/page-count step to run, unlike
        ``tec.py``'s/``localist.py``'s ``discover()``.
        """
        return [EventRef(url=_postings_url(source))]

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        response = fetcher.get(ref.url)
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "Lever postings fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning(
                "Lever postings %s returned unparseable JSON; skipping", raw.ref.url
            )
            return []

        # Lever's response is a top-level JSON array -- not a
        # {"jobs": [...]}-style wrapper like Greenhouse/TEC/Localist. See
        # module docstring.
        if not isinstance(data, list):
            logger.warning(
                "Lever postings %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        events: list[Event] = []
        for raw_posting in data:
            if not isinstance(raw_posting, dict):
                logger.warning(
                    "Skipping malformed Lever posting record on %s: not an object", raw.ref.url
                )
                continue
            try:
                event = _extract_one(raw_posting, source)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed Lever posting record on %s: %s", raw.ref.url, exc
                )
                continue
            if event is not None:
                events.append(event)
        return events
