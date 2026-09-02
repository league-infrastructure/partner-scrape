"""SmartRecruiters public job-postings JSON API adapter.

See sprint 031's ticket 002 and SUC-055: SmartRecruiters' public GET
endpoint (``api.smartrecruiters.com/v1/companies/{company}/postings``)
is confirmed live (2026-09-02 re-verification of issue 31's 2026-08-30
census; ``ServiceNow``, ``totalFound=577``). Unlike ``greenhouse.py``/
``lever.py``'s single-response shape, this endpoint **paginates** via
``offset``/``limit`` query params -- ``discover()`` here follows
``tec.py``'s/``localist.py``'s probe-then-paginate shape: a cheap probe
call learns ``totalFound``, then one ``EventRef`` per page is returned.

Real response shape (confirmed live, list endpoint --
``GET .../postings?limit=100&offset=0``)::

    {"offset": 0, "limit": 100, "totalFound": 577,
     "content": [{"id": "744000147051798", "name": "Partner Technology
       Architect", "releasedDate": "2026-09-02T17:25:42.923Z",
       "location": {"city": "Austin", "region": "Texas",
         "country": "us", "fullLocation": "Austin, Texas, United
         States", "remote": true, "hybrid": false},
       "department": {"id": "...", "label": "Sales"},
       "typeOfEmployment": {"id": "permanent", "label": "Full-time"},
       ...}]}

Live re-verification found two differences from this ticket's
originally assumed shape (recorded in the ticket's own Notes):

1. **The list endpoint's ``limit`` is server-capped at 100** --
   requesting ``limit=200`` echoes back ``limit=100`` in the response.
   :data:`PAGE_SIZE` is 100, matching this cap (probing at the real page
   size, exactly like ``tec.py``'s own ``PAGE_SIZE``-probe convention,
   so ``totalFound`` divided by the probe's own page size gives the
   correct page count).
2. **The list endpoint's ``content[]`` entries carry no
   ``postingUrl``/``applyUrl`` field at all** -- those only appear on
   the *per-posting detail* endpoint (``.../postings/{id}``), which
   would mean one extra fetch per posting (an N-fold request-count
   increase over the list endpoint alone). Live-confirmed instead that
   ``https://jobs.smartrecruiters.com/{company}/{id}`` (the detail
   endpoint's own ``postingUrl`` value, minus its optional
   title-slug suffix) returns HTTP 200 on its own -- so
   ``registration_url`` is built deterministically from the list
   response's own ``id`` and the source's configured ``company``, with
   no extra network call.

Field mapping: ``external_id`` <- ``id``; ``title`` <- ``name`` (not
``title`` -- SmartRecruiters' own field name, per the shape above);
``start`` <- parsed ``releasedDate`` (RFC 3339 with a trailing ``Z``;
Python's ``datetime.fromisoformat`` accepts this directly since Python
3.11, confirmed live against a real ``releasedDate`` value during this
ticket's verification); ``location`` <- ``location.fullLocation``;
``registration_url`` <- constructed per point 2 above. Every field this
adapter sets is high-trust (:data:`CONFIDENCE` 1.0), matching
``greenhouse.py``'s/``lever.py``'s convention.

``typeOfEmployment.label`` is passed into ``ats_filters.classify_posting``
as the ``commitment`` signal (SmartRecruiters' own internship marker --
live-confirmed distinct values include ``"Full-time"`` and ``"Intern"``,
the latter a stronger internship signal than title-regex alone, the same
role Lever's ``categories.commitment`` plays). ``department.label`` is
passed as the STEM-classification ``department`` text -- live-confirmed
some postings carry no ``department`` key at all, handled the same way
as an absent/empty string.

Every raw posting is run through ``adapters.ats_filters.classify_posting``
*before* an ``Event`` is constructed; only a match becomes an ``Event``,
with ``kind="internship"`` and the verdict's default
``age_grade_level``/``time_of_day`` applied via ``Event.set(...)``.
Deliberately does not set ``Event.cost``/``Event.cost_range`` -- same
contract as ``greenhouse.py``/``lever.py`` (see ``ats_filters.py``'s
module docstring).

Live-verification result (2026-09-02, ServiceNow, recorded in ticket
002's own Notes): 577 raw postings fetched across 6 pages; 41 located in
San Diego, all Senior/Staff/Director/Manager-level full-time roles; the
one ``typeOfEmployment.label == "Intern"`` posting found
(``"Intern - Marketing Associate"``) is in Sydney, Australia, in
Marketing, not STEM. 0 of the 577 pass ``classify_posting``'s
internship + STEM + San Diego test -- a working, zero-match pass, not a
failure, per this sprint's own Success Criteria.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Iterable

from partner_scrape.adapters.ats_filters import classify_posting
from partner_scrape.adapters.base import EventRef, RawResponse, acquisition_kwargs
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "smartrecruiters"

#: SmartRecruiters' public postings API is a structured, first-party
#: feed -- every field this adapter sets is maximally trusted, matching
#: ``greenhouse.py``'s/``lever.py``'s convention.
CONFIDENCE = 1.0

#: Default SmartRecruiters public API base, per this ticket's confirmed-
#: live shape. A source's ``config`` may override this with its own
#: ``api_base`` key (mirrors ``greenhouse.py``'s/``lever.py``'s own
#: ``api_base`` config convention).
DEFAULT_API_BASE = "https://api.smartrecruiters.com/v1/companies"

#: Public apply-page host, used to construct ``registration_url``
#: without an extra per-posting fetch (module docstring, point 2).
POSTING_URL_BASE = "https://jobs.smartrecruiters.com"

#: Postings per page for the real paginated fetches. Server-capped at
#: 100 (live-confirmed: requesting ``limit=200`` echoes back
#: ``limit=100``) -- the probe uses this same size so the page count
#: derived from ``totalFound`` is correct, matching ``tec.py``'s own
#: probe-at-real-page-size convention.
PAGE_SIZE = 100

#: Hard cap on pages enumerated for a single source, as a backstop
#: against an API that misreports ``totalFound``. At PAGE_SIZE=100 this
#: is 10,000 postings -- far beyond any real company's board -- so
#: hitting it means the source is misreporting.
MAX_PAGES = 100


def _parse_released_date(value: str) -> datetime | None:
    """Parse a SmartRecruiters ``releasedDate`` (RFC 3339, trailing ``Z``).

    Returns ``None`` for an absent/empty value. Raises ``ValueError`` on
    an unparseable non-empty value -- left uncaught here so the caller
    (``_extract_one``) can isolate it as a whole-record failure, matching
    ``greenhouse.py``'s ``_parse_datetime`` convention.
    """
    if not value:
        return None
    return datetime.fromisoformat(value)


def _posting_url(company: str, posting_id: str) -> str:
    """Build this posting's public apply page (module docstring, point 2)."""
    return f"{POSTING_URL_BASE}/{company}/{posting_id}"


def _extract_one(raw_posting: dict[str, Any], source: SourceConfig, company: str) -> Event | None:
    """Map one raw SmartRecruiters posting record into a canonical internship ``Event``.

    Returns ``None`` when the posting does not pass
    ``ats_filters.classify_posting`` -- not an error, simply not a
    match, so the caller must not treat it as a skipped/malformed
    record.

    Raises:
        ValueError: the record has no usable title (``name``).
        ValueError: a ``releasedDate`` value is present but unparseable.

    Both are caught by the caller (``extract()``) and treated as a
    per-record skip -- never fatal to the rest of the page, matching
    ``greenhouse.py``'s per-record isolation convention.
    """
    title = (raw_posting.get("name") or "").strip()
    if not title:
        raise ValueError("posting record has no name/title")

    posting_id = str(raw_posting.get("id") or "")

    location_obj = raw_posting.get("location") or {}
    location = (location_obj.get("fullLocation") or "").strip()
    department = ((raw_posting.get("department") or {}).get("label") or "").strip()
    commitment = ((raw_posting.get("typeOfEmployment") or {}).get("label") or "").strip()
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
    event.external_id = posting_id

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_released_date(raw_posting.get("releasedDate") or "")
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    if posting_id:
        event.set(
            "registration_url",
            _posting_url(company, posting_id),
            source=SOURCE_NAME,
            confidence=CONFIDENCE,
        )

    # Ticket 002's (sprint 006) classification defaults -- deliberately
    # no cost/cost_range (see module docstring and ats_filters.py).
    event.set(
        "age_grade_level", verdict.age_grade_level, source=SOURCE_NAME, confidence=CONFIDENCE
    )
    event.set("time_of_day", verdict.time_of_day, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


def _postings_base_url(source: SourceConfig) -> str:
    """Build this source's base postings-list URL (no query params)."""
    api_base = source.config.get("api_base") or DEFAULT_API_BASE
    company = source.config["company"]
    return f"{api_base}/{company}/postings"


def _page_url(base_url: str, offset: int) -> str:
    return f"{base_url}?limit={PAGE_SIZE}&offset={offset}"


class SmartRecruitersAdapter:
    """``Adapter`` for the SmartRecruiters public postings JSON API (``smartrecruiters``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Probe ``offset=0`` to learn ``totalFound``, then enumerate one
        ``EventRef`` per page (``context={"offset": N}``).

        Mirrors ``tec.py``'s probe-then-paginate shape: a probe that
        fails to fetch or parse is treated as "exactly one page" rather
        than raising -- per-source failure isolation belongs to the
        Pipeline, so this adapter degrades gracefully. Page count is
        also capped at :data:`MAX_PAGES` as a backstop against a source
        that misreports ``totalFound``.
        """
        base_url = _postings_base_url(source)
        probe_url = _page_url(base_url, 0)
        probe = fetcher.get(probe_url, **acquisition_kwargs(source))

        total_pages = 1
        if probe.status == 200:
            try:
                data = json.loads(probe.body)
                total_found = max(0, int(data.get("totalFound", 0)))
                total_pages = max(1, -(-total_found // PAGE_SIZE)) if total_found else 1
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning(
                    "SmartRecruiters probe for %s returned unparseable JSON; assuming 1 page",
                    base_url,
                )
        else:
            logger.warning(
                "SmartRecruiters probe for %s returned status %s; assuming 1 page",
                base_url,
                probe.status,
            )

        if total_pages > MAX_PAGES:
            logger.warning(
                "SmartRecruiters source %s reports %d pages; capping at %d",
                base_url, total_pages, MAX_PAGES,
            )
            total_pages = MAX_PAGES

        return [
            EventRef(url=_page_url(base_url, page * PAGE_SIZE), context={"offset": page * PAGE_SIZE})
            for page in range(total_pages)
        ]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        response = fetcher.get(ref.url, **acquisition_kwargs(source))
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "SmartRecruiters page fetch %s returned status %s; skipping",
                raw.ref.url,
                raw.status,
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning(
                "SmartRecruiters page %s returned unparseable JSON; skipping", raw.ref.url
            )
            return []

        if not isinstance(data, dict):
            logger.warning(
                "SmartRecruiters page %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        company = source.config.get("company", "")

        events: list[Event] = []
        for raw_posting in data.get("content", []):
            if not isinstance(raw_posting, dict):
                logger.warning(
                    "Skipping malformed SmartRecruiters posting record on %s: not an object",
                    raw.ref.url,
                )
                continue
            try:
                event = _extract_one(raw_posting, source, company)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed SmartRecruiters posting record on %s: %s",
                    raw.ref.url,
                    exc,
                )
                continue
            if event is not None:
                events.append(event)
        return events
