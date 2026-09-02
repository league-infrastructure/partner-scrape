"""Workable public job-widget JSON API adapter.

See sprint 031's ticket 003 and SUC-056: Workable's public widget
endpoint (``apply.workable.com/api/v1/widget/accounts/{account}
?details=true``) is confirmed live (2026-09-02 re-verification of issue
31's 2026-08-30 census; San Diego County Regional Airport Authority,
account slug ``san-diego-county-regional-airport-authority``).
Live-confirmed **not paginated** for this account -- the entire jobs
list (5 open postings, 2026-09-02) came back in one response, mirroring
``greenhouse.py``'s "no probe-then-paginate" shape rather than
SmartRecruiters' offset/limit pagination.

Real response shape (confirmed live, e.g.
``https://apply.workable.com/api/v1/widget/accounts/
san-diego-county-regional-airport-authority?details=true``)::

    {"name": "San Diego County Regional Airport Authority",
     "description": "...", "jobs": [{"title": "Airport Traffic
       Officer", "shortcode": "4FC496237D", "employment_type":
       "Full-time", "department": "Landside Operations - 23",
       "url": "https://apply.workable.com/j/4FC496237D",
       "application_url": "https://apply.workable.com/j/4FC496237D/apply",
       "created_at": "2026-08-27", "city": "San Diego",
       "state": "California", "country": "United States",
       "locations": [{"city": "San Diego", "region": "California", ...}],
       "description": "<p>...</p>", ...}]}

Live re-verification found one difference from this ticket's originally
assumed shape (recorded in the ticket's own Notes): location is **not**
a nested ``location.city``/``location.region`` object -- Workable's
widget API puts ``city``/``state`` as flat top-level keys on each job
record directly (a separate, richer ``locations[]`` array also exists,
but the flat ``city``/``state`` pair is simpler and sufficient, and is
what this adapter reads).

Field mapping: ``external_id`` <- ``shortcode``; ``title`` <- ``title``;
``description`` <- ``description`` (HTML -- stripped, see
:func:`_strip_html`, reusing ``greenhouse.py``'s proven small helper);
``start`` <- parsed ``created_at`` (a date-only string, ``YYYY-MM-DD``,
interpreted as UTC midnight -- unlike Greenhouse's/Lever's full
timestamp fields, Workable's widget API carries no time-of-day
component); ``location`` <- ``"{city}, {state}"`` (module docstring's
shape note above); ``registration_url`` <- ``application_url``, falling
back to ``url`` when absent. Every field this adapter sets is high-trust
(:data:`CONFIDENCE` 1.0), matching ``greenhouse.py``'s/``lever.py``'s
convention.

``employment_type`` is passed into ``ats_filters.classify_posting`` as
the ``commitment`` signal (Workable's own internship marker -- live-
confirmed distinct value ``"Full-time"`` among this account's current
postings; Workable's public documentation names ``"Internship"`` as a
sibling ``employment_type`` value for a paid internship posting, not
observed live in this account's *current* 5 open postings but confirmed
via issue 31's own census that this account has posted 9-week paid
summer internships before -- this ticket's fixture reproduces that
shape for filtering-correctness proof, per this ticket's own
acceptance criteria). ``department`` is passed as the STEM-
classification ``department`` text.

Every raw posting is run through ``adapters.ats_filters.classify_posting``
*before* an ``Event`` is constructed; only a match becomes an ``Event``,
with ``kind="internship"`` and the verdict's default
``age_grade_level``/``time_of_day`` applied via ``Event.set(...)``.
Deliberately does not set ``Event.cost``/``Event.cost_range`` -- same
contract as ``greenhouse.py``/``lever.py``/``smartrecruiters.py`` (see
``ats_filters.py``'s module docstring).

Live-verification result (2026-09-02, San Diego County Regional Airport
Authority, recorded in ticket 003's own Notes): 5 raw postings, all
"Full-time", all located San Diego -- none currently carries an
internship/co-op/apprentice title or commitment signal, so 0 of the 5
pass ``classify_posting``. A working, zero-current-match pass, not a
failure, per this sprint's own Success Criteria -- this account's
internship postings (like the "Business Intelligence - Intern II" role
issue 31's census found) are seasonal and not always open.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from partner_scrape.adapters.ats_filters import classify_posting
from partner_scrape.adapters.base import EventRef, RawResponse, acquisition_kwargs
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "workable"

#: Workable's public widget API is a structured, first-party feed --
#: every field this adapter sets is maximally trusted, matching
#: ``greenhouse.py``'s/``lever.py``'s/``smartrecruiters.py``'s
#: convention.
CONFIDENCE = 1.0

#: Default Workable public widget API base, per this ticket's confirmed-
#: live shape. A source's ``config`` may override this with its own
#: ``api_base`` key (mirrors ``greenhouse.py``'s own ``api_base`` config
#: convention).
DEFAULT_API_BASE = "https://apply.workable.com/api/v1/widget/accounts"

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
    """Strip HTML tags and decode the common entities Workable's ``description`` uses.

    Same small, proven approach as ``greenhouse.py``'s ``_strip_html``
    (see that module's own docstring for why this is a deliberate
    duplicate, not a shared import, a convention this adapter follows
    identically).
    """
    stripped = _TAG_RE.sub(" ", text)
    stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
    for entity, replacement in _HTML_ENTITIES.items():
        stripped = stripped.replace(entity, replacement)
    return stripped


def _parse_created_at(value: str) -> datetime | None:
    """Parse a Workable ``created_at`` date-only string (``YYYY-MM-DD``).

    Returns ``None`` for an absent/empty value. Raises ``ValueError`` on
    an unparseable non-empty value -- left uncaught here so the caller
    (``_extract_one``) can isolate it as a whole-record failure, matching
    ``greenhouse.py``'s ``_parse_datetime`` convention. Interpreted as
    UTC midnight, matching this codebase's existing UTC-aware-datetime
    convention (see e.g. ``lever.py``'s own ``_parse_created_at``).
    """
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _location_text(raw_job: dict[str, Any]) -> str:
    """Build a single display string from Workable's flat ``city``/``state`` keys."""
    city = (raw_job.get("city") or "").strip()
    state = (raw_job.get("state") or "").strip()
    parts = [part for part in (city, state) if part]
    return ", ".join(parts)


def _extract_one(raw_job: dict[str, Any], source: SourceConfig) -> Event | None:
    """Map one raw Workable job record into a canonical internship ``Event``.

    Returns ``None`` when the posting does not pass
    ``ats_filters.classify_posting`` -- not an error, simply not a
    match, so the caller must not treat it as a skipped/malformed
    record.

    Raises:
        ValueError: the record has no usable title.
        ValueError: a ``created_at`` value is present but unparseable.

    Both are caught by the caller (``extract()``) and treated as a
    per-record skip -- never fatal to the rest of the response, matching
    ``greenhouse.py``'s per-record isolation convention.
    """
    title = (raw_job.get("title") or "").strip()
    if not title:
        raise ValueError("job record has no title")

    location = _location_text(raw_job)
    department = (raw_job.get("department") or "").strip()
    commitment = (raw_job.get("employment_type") or "").strip()
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
    event.external_id = str(raw_job.get("shortcode") or "")

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    description = _strip_html(raw_job.get("description") or "")
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_created_at(raw_job.get("created_at") or "")
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    registration_url = (raw_job.get("application_url") or raw_job.get("url") or "").strip()
    if registration_url:
        event.set(
            "registration_url", registration_url, source=SOURCE_NAME, confidence=CONFIDENCE
        )

    # Same classification-defaults contract as greenhouse.py/lever.py/
    # smartrecruiters.py -- deliberately no cost/cost_range (see module
    # docstring and ats_filters.py).
    event.set(
        "age_grade_level", verdict.age_grade_level, source=SOURCE_NAME, confidence=CONFIDENCE
    )
    event.set("time_of_day", verdict.time_of_day, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


def _account_url(source: SourceConfig) -> str:
    """Build the one account-JSON URL this source's ``discover()`` resolves to."""
    api_base = source.config.get("api_base") or DEFAULT_API_BASE
    account = source.config["account"]
    return f"{api_base}/{account}?details=true"


class WorkableAdapter:
    """``Adapter`` for the Workable public job-widget JSON API (``workable``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Return exactly one ``EventRef`` for this account's jobs-widget URL.

        Workable's public widget endpoint is not paginated for this
        account's size (module docstring, live-confirmed) -- there is
        no probe/page-count step to run, unlike
        ``smartrecruiters.py``'s ``discover()``.
        """
        return [EventRef(url=_account_url(source))]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        response = fetcher.get(ref.url, **acquisition_kwargs(source))
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "Workable account fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning(
                "Workable account %s returned unparseable JSON; skipping", raw.ref.url
            )
            return []

        if not isinstance(data, dict):
            logger.warning(
                "Workable account %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        events: list[Event] = []
        for raw_job in data.get("jobs", []):
            if not isinstance(raw_job, dict):
                logger.warning(
                    "Skipping malformed Workable job record on %s: not an object", raw.ref.url
                )
                continue
            try:
                event = _extract_one(raw_job, source)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed Workable job record on %s: %s", raw.ref.url, exc
                )
                continue
            if event is not None:
                events.append(event)
        return events
