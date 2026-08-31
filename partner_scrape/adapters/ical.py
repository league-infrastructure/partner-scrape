"""The iCal/RSS adapter.

Per sprint.md's Open Question 2, no production target site is confirmed
for this adapter this sprint -- it is built generically against a
``.ics`` feed (many TEC sites expose one at ``?ical=1``, per
``dev/SCRAPER_GUIDELINES.md`` #5) and fixture-tested, with live registry
entries deferred to sprint 2.

Parsing uses the ``icalendar`` library rather than hand-parsing RFC
5545 -- see sprint.md's Design Rationale: hand-parsing iCal is a
correctness trap not worth taking on. Recurring ``VEVENT``s (an
``RRULE`` property) are expanded into individual occurrences using
``python-dateutil``'s ``rrulestr``, **bounded** to the smaller of
:data:`MAX_RRULE_WINDOW_DAYS` or :data:`MAX_RRULE_INSTANCES` -- an
unbounded RRULE (e.g. ``FREQ=DAILY`` with no ``COUNT``/``UNTIL``) must
never produce unbounded output. This bound is a deliberate, documented
scope cut (this ticket's Description), not a silently-missing feature.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

import icalendar
from dateutil.rrule import rrulestr

from partner_scrape.adapters.base import EventRef, RawResponse, acquisition_kwargs
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "ical"

#: A ``.ics`` feed is a first-party structured feed (parsed via
#: ``icalendar``, not guessed from text) -- same trust tier as TEC's
#: JSON API.
CONFIDENCE = 1.0

#: Bound on RRULE expansion: the smaller of this many days from DTSTART
#: or :data:`MAX_RRULE_INSTANCES` occurrences, whichever triggers first.
#: See module docstring -- this cap is deliberately enforced in code,
#: not left to the RRULE's own COUNT/UNTIL, since the whole point is to
#: protect against the case where those are absent.
MAX_RRULE_WINDOW_DAYS = 180

#: See :data:`MAX_RRULE_WINDOW_DAYS`.
MAX_RRULE_INSTANCES = 52

#: **(Sprint 016 tickets 001 and 002)** Tockify emits non-standard
#: calendar-level duration properties this adapter never reads, both
#: observed with the same invalid value ``P15M`` on the live
#: ``county-parks`` feed -- presumably intended as ``PT15M``, 15 minutes,
#: not the 15-month reading the ISO-8601 duration grammar would give it.
#: ``X-PUBLISHED-TTL`` (ticket 001) and ``REFRESH-INTERVAL`` (ticket 002,
#: found immediately adjacent to it in the same feed once ticket 001's
#: strip alone still left the feed unparseable) are the two
#: live-evidenced properties; this list is extensible if a third
#: evidenced case appears, but deliberately stays a targeted list of
#: real, measured properties rather than a blanket X-property/custom-
#: property sanitizer -- a different malformed property still fails
#: loudly through the existing top-level ``except Exception`` around
#: ``from_ical()``. See ``adapters/DESIGN.md``'s sprint-016 addendum.
_NONSTANDARD_DURATION_PROPERTIES = ("X-PUBLISHED-TTL", "REFRESH-INTERVAL")
_NONSTANDARD_DURATION_RE = re.compile(
    r"(?im)^(?:" + "|".join(_NONSTANDARD_DURATION_PROPERTIES) + r"):[^\r\n]*\r?\n?"
)


def _as_datetime(value: date | datetime) -> tuple[datetime, bool]:
    """Normalize an icalendar DTSTART/DTEND value to a naive ``datetime``.

    Returns ``(value, all_day)``. A ``.ics`` ``VALUE=DATE`` property
    (whole-day event) decodes to ``datetime.date``; a ``VALUE=DATE-TIME``
    property decodes to ``datetime.datetime``, possibly timezone-aware.
    Timezone-aware values are made naive by dropping ``tzinfo`` (not
    converting to another timezone first) -- this preserves the venue's
    authored wall-clock time, matching ``tec.py``'s naive-datetime
    convention that the rest of this sprint's pipeline assumes
    throughout.
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=None), False
    if isinstance(value, date):
        return datetime.combine(value, time.min), True
    raise TypeError(f"unexpected DTSTART/DTEND type: {type(value)!r}")


def _expand_rrule(dtstart: datetime, rrule_text: str) -> list[datetime]:
    """Expand an RRULE into occurrence start times, bounded per module docstring.

    Iterates lazily and stops as soon as either bound is hit -- safe
    even for a truly unbounded rule (``FREQ=DAILY`` with no
    ``COUNT``/``UNTIL``), since ``rrulestr`` iteration is itself lazy.
    """
    rule = rrulestr(rrule_text, dtstart=dtstart)
    horizon = dtstart + timedelta(days=MAX_RRULE_WINDOW_DAYS)
    occurrences: list[datetime] = []
    for occurrence in rule:
        if occurrence > horizon:
            break
        occurrences.append(occurrence)
        if len(occurrences) >= MAX_RRULE_INSTANCES:
            break
    return occurrences


class ICalAdapter:
    """``Adapter`` for a generic ``.ics`` feed (``ical``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """A single ``EventRef`` for the source's whole feed -- a ``.ics``
        feed is already the complete set of events, not a paginated API.
        """
        feed_url = source.config["feed_url"]
        return [EventRef(url=feed_url)]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        response = fetcher.get(ref.url, **acquisition_kwargs(source))
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "iCal fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        if not raw.body.strip():
            logger.warning("iCal feed %s returned an empty body; skipping", raw.ref.url)
            return []

        # (Sprint 016 tickets 001, 002) Strip the known non-standard
        # duration properties that break icalendar's parser before
        # from_ical() ever sees them -- see
        # _NONSTANDARD_DURATION_PROPERTIES' docstring.
        body = _NONSTANDARD_DURATION_RE.sub("", raw.body)

        try:
            calendar = icalendar.Calendar.from_ical(body)
        except Exception as exc:
            # icalendar raises several distinct exception types for
            # malformed input (ValueError, its own parser errors, ...) --
            # caught broadly so no malformed feed can kill the source,
            # per this ticket's Acceptance Criteria.
            logger.warning("iCal feed %s was unparseable: %s", raw.ref.url, exc)
            return []

        events: list[Event] = []
        for component in calendar.walk("VEVENT"):
            try:
                events.extend(self._extract_component(component, source))
            except Exception as exc:
                # (Sprint 016 ticket 001) Widened from
                # (ValueError, TypeError, KeyError) to match this module's
                # own top-level `except Exception` above and
                # adapters/DESIGN.md's per-record isolation invariant --
                # a narrower tuple here previously let an AttributeError
                # (a list-valued RRULE, see _extract_component) escape
                # this loop and abort the whole source.
                logger.warning("Skipping malformed VEVENT in %s: %s", raw.ref.url, exc)
        return events

    def _extract_component(self, component: Any, source: SourceConfig) -> list[Event]:
        """Map one ``VEVENT`` into one or more canonical ``Event``s.

        A non-recurring ``VEVENT`` yields exactly one ``Event``. A
        ``VEVENT`` with an ``RRULE`` yields one ``Event`` per occurrence,
        bounded by :func:`_expand_rrule`.

        Raises:
            ValueError: no ``DTSTART`` or no ``SUMMARY``.
        """
        dtstart_prop = component.get("dtstart")
        if dtstart_prop is None:
            raise ValueError("VEVENT has no DTSTART")
        dtstart, all_day = _as_datetime(dtstart_prop.dt)

        duration: timedelta | None = None
        dtend_prop = component.get("dtend")
        if dtend_prop is not None:
            dtend, _ = _as_datetime(dtend_prop.dt)
            duration = dtend - dtstart

        uid = str(component.get("uid") or "").strip()

        rrule_prop = component.get("rrule")
        if rrule_prop is None:
            return [self._build_event(component, dtstart, all_day, duration, uid, source)]

        if isinstance(rrule_prop, list):
            # (Sprint 016 ticket 001) icalendar returns a list of vRecur
            # when a VEVENT carries more than one RRULE property (RFC 5545
            # technically permits it, though most calendar tools write
            # only one). Salvage via the first rule rather than dropping
            # the whole record -- see adapters/DESIGN.md's sprint-016
            # addendum for why this is preferred over raising.
            discarded = len(rrule_prop) - 1
            logger.warning(
                "VEVENT %s has %d RRULE properties; using the first and discarding %d",
                uid or "<no UID>",
                len(rrule_prop),
                discarded,
            )
            rrule_prop = rrule_prop[0]

        rrule_text = rrule_prop.to_ical().decode("utf-8")
        occurrences = _expand_rrule(dtstart, rrule_text)
        events = []
        for occurrence in occurrences:
            # Distinct external_id per occurrence -- each is a distinct
            # record, not a repeat of the master VEVENT (collapsing
            # recurring instances back down is ticket 006's job, a
            # different question). When the feed has no UID, leave
            # external_id empty; Event.identity_key()'s (source_id,
            # normalized_title, start_date) fallback already
            # disambiguates occurrences by date.
            occurrence_id = f"{uid}::{occurrence.isoformat()}" if uid else ""
            events.append(
                self._build_event(component, occurrence, all_day, duration, occurrence_id, source)
            )
        return events

    def _build_event(
        self,
        component: Any,
        start: datetime,
        all_day: bool,
        duration: timedelta | None,
        external_id: str,
        source: SourceConfig,
    ) -> Event:
        """Build one canonical ``Event`` for a resolved occurrence ``start``.

        Raises:
            ValueError: the ``VEVENT`` has no ``SUMMARY``.
        """
        title = str(component.get("summary") or "").strip()
        if not title:
            raise ValueError("VEVENT has no SUMMARY")

        event = Event(kind="event", source_id=source.source_id)
        event.external_id = external_id

        event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)
        event.set("all_day", all_day, source=SOURCE_NAME, confidence=CONFIDENCE)

        if duration is not None:
            event.set("end", start + duration, source=SOURCE_NAME, confidence=CONFIDENCE)

        description = str(component.get("description") or "").strip()
        if description:
            event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

        location = str(component.get("location") or "").strip()
        if location:
            event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

        return event
