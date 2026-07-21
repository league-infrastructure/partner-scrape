"""The League's own sync.jtlapp.net query API adapter (``leaguesync``).

The League of Amazing Programmers runs its own read-only query API
(``sync.jtlapp.net``) over its Pike13 (classes/courses) and Meetup
(free tech clubs) data. This is now the authoritative source for
League classes -- the previous ``generic_html`` scrape of
jointheleague.org/classes (``registry/sources/jointheleague.toml``,
now disabled) could get titles/descriptions but never real schedules
or dates, since jointheleague.org's public pages don't publish
occurrence dates -- only Pike13's booking widget does, and this API
exposes exactly that.

Two logical pulls, both against the same ``GET /query?sql=<SELECT>``
endpoint, distinguished via each ``EventRef.context["kind"]`` set by
``discover()`` and read back by ``extract()`` (see ``base.py``'s
``EventRef`` docstring -- this is exactly the "distinguish what a ref
is for" use ``context`` exists for):

1. CLASSES -- one canonical ``Event`` per qualifying ``services`` row,
   built from that service's *next* upcoming ``event_occurrences`` row
   (earliest ``start_at >= now``, computed server-side by
   :data:`CLASSES_SQL`'s window function -- one row per service in the
   result, no client-side grouping needed).
2. TECH_CLUBS -- one ``Event`` per upcoming, active ``meetup_events``
   row (the League's free FTC/robotics tech clubs), left-joined to
   ``meetup_venues`` for location.

Every field this adapter sets is high-trust -- like ``tec_rest`` and
``localist``, this is a structured, first-party API (the League's own
sync of its own Pike13/Meetup data), so every ``Event.set(...)`` call
below uses :data:`CONFIDENCE` (1.0).

Every ``Event`` this adapter emits also sets ``Event.trusted = True``
(OOP, 2026-07-20): live-observed that the LLM relevance gate
(``enrich/enricher.py``) dropped real League youth classes with thin
titles ("Summer Camps@SFA", "Python@GA") as apparently not-relevant.
The League's own beta site requires all of its curated youth
programming to show regardless of that verdict -- ``trusted`` tells the
Enricher to still classify the Event (areas/age/cost still wanted) but
never let the relevance gate drop it. Because the gate can no longer
catch a wrongly-included non-youth service, :data:`CLASSES_SQL` itself
excludes teacher/staff/professional-development services (see its own
comment) -- the SQL filter is the only thing standing between a
"Teacher Development" service and the parent-facing site once
``trusted`` is set.

Auth: the API requires ``Authorization: Bearer <token>`` (see
``config.get_leaguesync_api_key()``) -- passed as an explicit
``headers`` argument to ``fetcher.get()`` on every fetch, per the
``Fetcher`` protocol (``fetch/fetcher.py``). Query text (not the token)
is embedded directly in the URL as ``?sql=<url-encoded SELECT>``, per
sync.jtlapp.net's own contract -- SELECT/WITH only, no mutation
possible even if the URL were logged.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from datetime import datetime
from typing import Any, Iterable

from partner_scrape import config
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "leaguesync"

#: sync.jtlapp.net is a structured, first-party feed over the League's
#: own Pike13 + Meetup data -- every field this adapter sets is
#: maximally trusted, matching tec_rest/localist's convention.
CONFIDENCE = 1.0

#: EventRef.context["kind"] values -- how extract() tells a classes
#: page from a tech-clubs page apart (both are plain RawResponse JSON
#: bodies from the same /query endpoint; there is no other signal).
KIND_CLASSES = "classes"
KIND_TECH_CLUBS = "tech_clubs"

#: One row per qualifying service, each carrying its *next* upcoming
#: occurrence (earliest event_occurrences.start_at >= now) -- the
#: ROW_NUMBER()/PARTITION BY window function does the "next occurrence
#: per service" grouping server-side, so extract() never needs to
#: dedupe multiple occurrence rows per service itself.
#:
#: Filters match sprint.md's confirmed WANT clause: service_type IN
#: ('Course','GroupClass') (excludes 1:1 'Appointment' bookings, not
#: public classes), visitors_can_view=1, deleted_at IS NULL for both
#: the service and its chosen occurrence. eo.state='active' additionally
#: excludes canceled occurrences (confirmed live: 6 of 356 near-term
#: occurrences are state='canceled') from ever being picked as "next".
#:
#: Teacher/staff/professional-development exclusion (OOP, 2026-07-20):
#: confirmed live that "Teacher Development" (a staff-facing service,
#: not a youth class) otherwise passes every filter above and -- once
#: `Event.trusted` bypasses the LLM relevance gate -- would surface on
#: the parent-facing site with no downstream check to catch it. Excluded
#: here, at the source, on both `s.name` and `s.category_name` so it
#: never becomes an Event at all; kept to the specific
#: Teacher/Staff/Professional Development vocabulary (not e.g. a bare
#: "%Staff%" alone) so a legitimate class that happens to mention staff
#: in passing isn't accidentally excluded.
CLASSES_SQL = """
WITH next_occ AS (
  SELECT eo.service_id, eo.id AS occurrence_id, eo.start_at, eo.end_at, eo.location_id,
         ROW_NUMBER() OVER (PARTITION BY eo.service_id ORDER BY eo.start_at ASC) AS rn
  FROM event_occurrences eo
  WHERE eo.deleted_at IS NULL
    AND eo.state = 'active'
    AND eo.start_at >= datetime('now')
)
SELECT s.id AS service_id, s.name, s.description, s.description_short,
       s.category_name, s.service_type,
       no.occurrence_id, no.start_at, no.end_at,
       l.id AS location_id, l.name AS location_name, l.city,
       l.latitude, l.longitude, l.formatted_address, l.timezone
FROM services s
JOIN next_occ no ON no.service_id = s.id AND no.rn = 1
LEFT JOIN locations l ON l.id = no.location_id
WHERE s.service_type IN ('Course', 'GroupClass')
  AND s.visitors_can_view = 1
  AND s.deleted_at IS NULL
  AND s.name NOT LIKE '%Teacher%'
  AND s.name NOT LIKE '%Staff%'
  AND s.name NOT LIKE '%Professional Development%'
  AND COALESCE(s.category_name, '') NOT LIKE '%Teacher%'
  AND COALESCE(s.category_name, '') NOT LIKE '%Staff%'
  AND COALESCE(s.category_name, '') NOT LIKE '%Professional Development%'
ORDER BY no.start_at ASC
""".strip()

#: One row per upcoming, active, non-deleted meetup event -- the
#: League's free tech clubs (FTC/robotics workshops, Robot Garage open
#: sessions, etc, run under its "League Labs"/"League Tech Club" Meetup
#: groups). Left-joined to meetup_venues for location; confirmed live
#: that some venue_ids (e.g. the League's own meetup venue, 26906060)
#: have no matching meetup_venues row -- the LEFT JOIN degrades that to
#: NULL venue fields rather than dropping the event, and extract()
#: below leaves Event.location blank in that case.
TECH_CLUBS_SQL = """
SELECT me.id, me.title, me.description, me.date_time, me.event_url,
       me.featured_photo_url, me.venue_id,
       mv.name AS venue_name, mv.address, mv.city, mv.state, mv.lat, mv.lon
FROM meetup_events me
LEFT JOIN meetup_venues mv ON mv.id = me.venue_id
WHERE me.deleted_at IS NULL
  AND me.status = 'ACTIVE'
  AND me.date_time >= datetime('now')
ORDER BY me.date_time ASC
""".strip()

#: Registration URL for classes: the League's Pike13 booking portal.
#: Confirmed live (embedded in multiple services' own ``description``
#: HTML, e.g. "Create a client account" links to exactly this URL) --
#: no clean per-service Pike13 URL is derivable from ``services.data``
#: (it carries the same rendered-HTML description, not a structured
#: booking-page URL), so every class Event uses this same League-wide
#: booking entrypoint. Overridable via ``source.config["registration_url"]``.
DEFAULT_REGISTRATION_URL = "https://jtl.pike13.com"

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
    """Strip HTML tags and decode the common entities Pike13's rendered
    ``services.description`` uses -- same approach as ``adapters/tec.py``'s
    ``_strip_html`` (Pike13's description is rendered HTML, same shape
    TEC's WordPress-backed descriptions are).
    """
    stripped = _TAG_RE.sub(" ", text)
    stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
    for entity, replacement in _HTML_ENTITIES.items():
        stripped = stripped.replace(entity, replacement)
    return stripped


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse a ``start_at``/``end_at``/``date_time`` ISO8601 timestamp.

    Both APIs emit tz-aware timestamps -- Pike13's occurrences as a
    ``Z``-suffixed UTC string (e.g. ``"2026-07-21T17:00:00Z"``,
    confirmed live), Meetup's as an explicit UTC-offset string (e.g.
    ``"2026-07-22T18:30:00-07:00"``). ``datetime.fromisoformat`` doesn't
    accept a bare trailing ``Z`` (pre-3.11 semantics, and this project
    doesn't rely on 3.11+ parsing behavior elsewhere), so it's rewritten
    to ``+00:00`` first; the offset form needs no rewriting. Returned
    tz-aware -- ``normalize.run()`` already strips ``tzinfo`` to naive
    for every Event field, so this adapter doesn't convert timezones
    itself.

    Returns ``None`` for an absent/empty value. Raises ``ValueError`` on
    an unparseable non-empty value -- left uncaught here so the caller
    (``_extract_class``/``_extract_tech_club``) can isolate it as a
    whole-record failure, matching every other structured adapter's
    convention.
    """
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _join_nonempty(parts: Iterable[str | None]) -> str:
    return ", ".join(p.strip() for p in parts if p and p.strip())


def _query_url(api_base: str, sql: str) -> str:
    return f"{api_base.rstrip('/')}/query?sql={urllib.parse.quote(sql)}"


def _auth_headers() -> dict[str, str]:
    """Build the Bearer-auth header sync.jtlapp.net requires.

    Reads the token fresh on every call via ``config.get_leaguesync_api_key()``
    rather than caching it on the adapter instance -- adapter instances
    are constructed fresh per ``adapters.run()`` call (see ``base.py``'s
    ``Adapter`` docstring: "no adapter-instance state to inject into"),
    so there is no instance to cache it on anyway.
    """
    return {"Authorization": f"Bearer {config.get_leaguesync_api_key()}"}


def _extract_class(row: dict[str, Any], source: SourceConfig) -> Event:
    """Map one CLASSES_SQL row (a service + its next occurrence) into a
    canonical ``Event``.

    Raises:
        ValueError: the record has no usable title (``services.name``).
        ValueError: ``start_at``/``end_at`` is present but unparseable.
    """
    title = (row.get("name") or "").strip()
    if not title:
        raise ValueError("service record has no name")

    event = Event(kind="event", source_id=source.source_id, trusted=True)
    event.external_id = str(row.get("service_id") or "")

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    # Both services.description and services.description_short are
    # Pike13-rendered HTML in practice -- confirmed live (e.g.
    # "Competitive Robotics Summer Warm Up"'s description_short carries
    # its own <ul><li> list), not just description -- so whichever one
    # is actually used gets the same HTML strip.
    description = (row.get("description") or "").strip()
    if not description:
        description = (row.get("description_short") or "").strip()
    if description:
        event.set(
            "description", _strip_html(description), source=SOURCE_NAME, confidence=CONFIDENCE
        )

    start = _parse_datetime(row.get("start_at"))
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    end = _parse_datetime(row.get("end_at"))
    if end is not None:
        event.set("end", end, source=SOURCE_NAME, confidence=CONFIDENCE)

    location = _join_nonempty([row.get("location_name"), row.get("city")])
    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    latitude = row.get("latitude")
    if latitude is not None:
        event.set("latitude", float(latitude), source=SOURCE_NAME, confidence=CONFIDENCE)

    longitude = row.get("longitude")
    if longitude is not None:
        event.set("longitude", float(longitude), source=SOURCE_NAME, confidence=CONFIDENCE)

    category_name = (row.get("category_name") or "").strip()
    if category_name:
        event.set("categories", [category_name], source=SOURCE_NAME, confidence=CONFIDENCE)

    registration_url = source.config.get("registration_url") or DEFAULT_REGISTRATION_URL
    event.set("registration_url", registration_url, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


def _extract_tech_club(row: dict[str, Any], source: SourceConfig) -> Event:
    """Map one TECH_CLUBS_SQL row (a meetup event, left-joined to its
    venue) into a canonical ``Event``.

    Raises:
        ValueError: the record has no usable title.
        ValueError: ``date_time`` is present but unparseable.
    """
    title = (row.get("title") or "").strip()
    if not title:
        raise ValueError("meetup event record has no title")

    event = Event(kind="event", source_id=source.source_id, trusted=True)
    event.external_id = str(row.get("id") or "")

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    description = (row.get("description") or "").strip()
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_datetime(row.get("date_time"))
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    location = _join_nonempty([row.get("venue_name"), row.get("city")])
    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    latitude = row.get("lat")
    if latitude is not None:
        event.set("latitude", float(latitude), source=SOURCE_NAME, confidence=CONFIDENCE)

    longitude = row.get("lon")
    if longitude is not None:
        event.set("longitude", float(longitude), source=SOURCE_NAME, confidence=CONFIDENCE)

    registration_url = (row.get("event_url") or "").strip()
    if registration_url:
        event.set(
            "registration_url", registration_url, source=SOURCE_NAME, confidence=CONFIDENCE
        )

    image_url = (row.get("featured_photo_url") or "").strip()
    if image_url:
        event.set("image_url", image_url, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


class LeagueSyncAdapter:
    """``Adapter`` for the League's own sync.jtlapp.net query API (``leaguesync``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Return exactly two ``EventRef``s -- the classes query and the
        tech-clubs query -- both fixed SQL against the source's
        ``api_base``. No probing needed: unlike TEC/Localist's paginated
        REST APIs, this is a single SELECT each, with the server doing
        all the filtering/joining/grouping (see :data:`CLASSES_SQL`'s
        window function).
        """
        api_base = source.config.get("api_base") or config.get_leaguesync_url()
        return [
            EventRef(
                url=_query_url(api_base, CLASSES_SQL),
                context={"kind": KIND_CLASSES},
            ),
            EventRef(
                url=_query_url(api_base, TECH_CLUBS_SQL),
                context={"kind": KIND_TECH_CLUBS},
            ),
        ]

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        response = fetcher.get(ref.url, headers=_auth_headers())
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "leaguesync query %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            rows = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning("leaguesync query %s returned unparseable JSON; skipping", raw.ref.url)
            return []

        if not isinstance(rows, list):
            logger.warning(
                "leaguesync query %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        kind = raw.ref.context.get("kind")
        extract_one = _extract_class if kind == KIND_CLASSES else _extract_tech_club

        events: list[Event] = []
        for row in rows:
            try:
                events.append(extract_one(row, source))
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed leaguesync %s record on %s: %s", kind, raw.ref.url, exc
                )
        return events
