"""Greenhouse Job Board public JSON API adapter.

See sprint.md's Architecture (ticket 003) and SUC-001: Greenhouse's
public job-list endpoint (``boards-api.greenhouse.io/v1/boards/{token}/
jobs?content=true``) is **not paginated** -- confirmed live during
sprint planning against four real company boards, every open job comes
back in one response -- so, unlike ``adapters/tec.py``/``localist.py``,
``discover()`` here returns exactly one ``EventRef``, no probe-then-
paginate dance.

Real response shape (confirmed live, e.g.
``https://boards-api.greenhouse.io/v1/boards/gossamerbio/jobs``)::

    {"jobs": [{"id": 8632329002, "title": "...", "updated_at": "...",
      "location": {"name": "San Diego, California, United States"},
      "absolute_url": "https://...", "content": "<html description>",
      "departments": [{"name": "..."}], "offices": [{"name": "..."}]}]}

Field mapping: ``external_id`` <- ``id`` (stringified); ``title`` <-
``title``; ``description`` <- ``content`` (HTML -- stripped, see
:func:`_strip_html`); ``start`` <- parsed ``updated_at``; ``location``
<- ``location.name``; ``registration_url`` <- ``absolute_url``. Every
field this adapter sets is high-trust (:data:`CONFIDENCE` 1.0),
matching ``tec.py``'s convention -- it's a structured, first-party feed.

Every raw job is run through ``adapters.ats_filters.classify_posting``
(ticket 002) *before* an ``Event`` is constructed; only a match becomes
an ``Event``, with ``kind="internship"`` and the verdict's default
``age_grade_level``/``time_of_day`` applied via ``Event.set(...)``.
Deliberately does not set ``Event.cost``/``Event.cost_range`` -- ticket
002's own contract (see ``ats_filters.py``'s module docstring).

**On duplicating ``tec.py``'s ``_strip_html`` helper rather than
extracting a shared module**: sprint.md's Architecture > Step 5 "Impact
on Existing Components" states ``adapters/tec.py`` (and
``adapters/wordpress.py``, which already carries its own independent
copy of the same small helper) are **unchanged, zero modification** by
this sprint -- so a shared-module extraction that touches ``tec.py`` is
out of this ticket's scope. Duplicating the ~15-line regex/entity-table
helper here matches the codebase's existing convention (``tec.py`` and
``wordpress.py`` already each carry their own copy) rather than
introducing a third, inconsistent pattern.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Iterable

from partner_scrape.adapters.ats_filters import classify_posting
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "greenhouse"

#: Greenhouse's public board API is a structured, first-party feed --
#: every field this adapter sets is maximally trusted, matching
#: ``tec.py``'s/``localist.py``'s convention.
CONFIDENCE = 1.0

#: Default Greenhouse Job Board API base, per sprint.md's confirmed-live
#: shape. A source's ``config`` may override this with its own
#: ``api_base`` key (mirrors ``tec.py``'s/``localist.py``'s own
#: ``api_base`` config convention), though every company confirmed live
#: during sprint planning used this same default host.
DEFAULT_API_BASE = "https://boards-api.greenhouse.io/v1/boards"

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
    """Strip HTML tags and decode the common entities Greenhouse's ``content`` uses.

    Same small, proven approach as ``tec.py``'s ``_strip_html`` (see
    module docstring for why this is a deliberate duplicate, not a
    shared import).
    """
    stripped = _TAG_RE.sub(" ", text)
    stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
    for entity, replacement in _HTML_ENTITIES.items():
        stripped = stripped.replace(entity, replacement)
    return stripped


def _parse_datetime(value: str) -> datetime | None:
    """Parse a Greenhouse ``updated_at`` timestamp string.

    Returns ``None`` for an absent/empty value. Raises ``ValueError`` on
    an unparseable non-empty value -- left uncaught here so the caller
    (``_extract_one``) can isolate it as a whole-record failure, matching
    ``tec.py``'s ``_parse_datetime`` convention.
    """
    if not value:
        return None
    return datetime.fromisoformat(value)


def _department_text(raw_job: dict[str, Any]) -> str:
    """Join Greenhouse's ``departments`` list into one text blob for STEM matching."""
    departments = raw_job.get("departments") or []
    names = [d.get("name", "") for d in departments if isinstance(d, dict) and d.get("name")]
    return ", ".join(names)


def _extract_one(raw_job: dict[str, Any], source: SourceConfig) -> Event | None:
    """Map one raw Greenhouse job record into a canonical internship ``Event``.

    Returns ``None`` when the posting does not pass
    ``ats_filters.classify_posting`` -- not an error, simply not a
    match, so the caller must not treat it as a skipped/malformed
    record.

    Raises:
        ValueError: the record has no usable title.
        ValueError: an ``updated_at`` value is present but unparseable.

    Both are caught by the caller (``extract()``) and treated as a
    per-record skip -- never fatal to the rest of the response, matching
    ``tec.py``'s per-record isolation convention.
    """
    title = (raw_job.get("title") or "").strip()
    if not title:
        raise ValueError("job record has no title")

    location = ((raw_job.get("location") or {}).get("name") or "").strip()
    department = _department_text(raw_job)
    location_keywords = source.config.get("location_keywords")

    verdict = classify_posting(
        title,
        department=department,
        location=location,
        location_keywords=location_keywords,
    )
    if verdict is None:
        return None

    event = Event(kind="internship", source_id=source.source_id)
    event.external_id = str(raw_job.get("id") or "")

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    description = _strip_html(raw_job.get("content") or "")
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_datetime(raw_job.get("updated_at") or "")
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    registration_url = (raw_job.get("absolute_url") or "").strip()
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


def _board_url(source: SourceConfig) -> str:
    """Build the one board-JSON URL this source's ``discover()`` resolves to."""
    api_base = source.config.get("api_base") or DEFAULT_API_BASE
    board_token = source.config["board_token"]
    return f"{api_base}/{board_token}/jobs?content=true"


class GreenhouseAdapter:
    """``Adapter`` for the Greenhouse Job Board public JSON API (``greenhouse``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Return exactly one ``EventRef`` for this board's job-list URL.

        Greenhouse's public job-list endpoint is not paginated (module
        docstring) -- there is no probe/page-count step to run, unlike
        ``tec.py``'s/``localist.py``'s ``discover()``.
        """
        return [EventRef(url=_board_url(source))]

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        response = fetcher.get(ref.url)
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "Greenhouse board fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning(
                "Greenhouse board %s returned unparseable JSON; skipping", raw.ref.url
            )
            return []

        if not isinstance(data, dict):
            logger.warning(
                "Greenhouse board %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        events: list[Event] = []
        for raw_job in data.get("jobs", []):
            try:
                event = _extract_one(raw_job, source)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed Greenhouse job record on %s: %s", raw.ref.url, exc
                )
                continue
            if event is not None:
                events.append(event)
        return events
