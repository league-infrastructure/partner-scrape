"""RobotEvents API v2 adapter (``robotevents``) -- VEX Robotics
Competition (V5RC/VIQRC) and Aerial Drone Competition tournament events.

VEX (CA Region 4: San Diego/Imperial -- roughly a dozen local V5RC/VIQRC
tournaments per season plus two ~96-team regional championships) and the
Aerial Drone Competition (RECF + partner Robolink, same platform) are
entirely absent from the opportunity pipeline before this ticket.
``robotevents.com`` 403s a plain fetch (sprint.md's Problem) -- RobotEvents
API v2 (``robotevents.com/api/v2``) is the only viable path: a free,
Bearer-token-gated, structured JSON REST API, in the same spirit as
``adapters/tec.py``'s ``tec_rest`` and ``adapters/localist.py`` (known
endpoint, probe-then-paginate discovery, ``CONFIDENCE = 1.0``).

**Endpoint shape, confirmed against RobotEvents' own published OpenAPI
schema, not a live authenticated probe.** No ``ROBOTEVENTS_KEY`` was
available during this ticket's execution (see ``config.py``'s
``ROBOTEVENTS_API_KEY_ENV_VAR`` docstring and this sprint's Migration
Concerns) and every documented v2 endpoint requires the Bearer token, so
there was no unauthenticated live call this ticket could run instead.
Instead, the exact request/response shape below is taken from the
actively-maintained, open-source ``robotevents`` npm client
(https://github.com/brenapp/robotevents), whose TypeScript types are
generated directly from RobotEvents' own OpenAPI spec:

- ``GET {base}/events`` takes ``season[]`` (int, repeatable),
  ``sku[]``, ``id[]``, ``team[]``, ``start``/``end`` (date filters),
  ``region`` (free string), ``level[]`` (``"World"``/``"National"``/
  ``"Regional"``/``"State"``/``"Signature"``/``"Other"``),
  ``eventTypes[]`` (``"tournament"``/``"league"``/``"workshop"``/
  ``"virtual"``), ``page``, and ``per_page`` -- confirmed there is
  **no** ``program[]`` filter on this endpoint (RobotEvents.com hosts
  only REC Foundation/VEX-family programs -- VRC, VIQRC, VEX U, ADC --
  so this adapter never needs to filter FTC/FLL out the way it would
  on a shared platform).
- The response envelope is ``{"meta": {...page fields...}, "data":
  [...]}`` -- ``meta.last_page``/``meta.total`` drive pagination,
  matching ``adapters/localist.py``'s ``page.total`` probe-then-
  paginate shape almost exactly.
- Each ``data[]`` element carries ``id`` (int), ``sku`` (str,
  e.g. ``"RE-VRC-24-1234"``), ``name``, ``start``/``end`` (ISO 8601
  date-times), ``season``/``program`` (``{id, name, code}``),
  ``location`` (``{venue, address_1, address_2, city, region,
  postcode, country, coordinates}``), ``level``, ``event_type``.
  The event's canonical public page is
  ``https://www.robotevents.com/{sku}.html`` (the client library's own
  ``Event.getURL()``) -- used here as ``registration_url``.
- Auth: ``Authorization: Bearer <token>`` (see
  ``config.get_robotevents_api_key()``), same as ``adapters/
  leaguesync.py``/``teams/sources/tba.py``.

**Query scope is date- and region-driven, not season-ID-driven.** This
adapter does not require a ``season_ids`` config value (RobotEvents
assigns season IDs as opaque incrementing integers with no derivable
pattern, and there was no token available this ticket to look the
current V5RC/VIQRC/ADC season IDs up via ``/seasons``) -- ``config``
may set ``season_ids`` (a list of ints) to narrow the query once an
operator confirms them live, but the default query instead filters on
``start`` (defaults to "today", matching ``adapters/tec.py``'s
``start_date=now``-then-filter precedent, documented in ``adapters/
localist.py``'s own docstring) so the source degrades to "every
upcoming event in the configured region," not zero events, when
``season_ids`` is unset.

**"Spectator-open"** (sprint.md's Problem/Solution framing) is not a
field RobotEvents' schema exposes -- every local/regional VRC/VIQRC/ADC
tournament in a season's normal competition calendar is open to
spectators; RobotEvents does not distinguish an invite-only event via
any documented ``/events`` field. This adapter does not attempt to
invent a spectator-open filter; ``event_types`` (default
``["tournament"]``) is this adapter's actual scoping knob, excluding
``"workshop"``/``"virtual"``/``"league"`` event types from the
Opportunity pipeline, which is the closer, evidenced distinction.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import date, datetime
from typing import Any, Iterable

from partner_scrape import config
from partner_scrape.adapters.base import EventRef, RawResponse, acquisition_kwargs
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's provenance source name, recorded on every field it sets.
SOURCE_NAME = "robotevents"

#: RobotEvents API v2 is a structured, first-party REST API -- every
#: field this adapter sets is maximally trusted, matching
#: tec_rest/localist/leaguesync's convention.
CONFIDENCE = 1.0

#: Default ``eventTypes[]`` filter -- see this module's docstring
#: ("Spectator-open") for why event type, not a nonexistent spectator
#: flag, is this adapter's real scoping knob. Overridable via
#: ``source.config["event_types"]``.
DEFAULT_EVENT_TYPES = ["tournament"]

#: Default page size for the real (non-probe) paginated request.
#: Matches ``adapters/localist.py``'s ``DEFAULT_PP`` magnitude.
DEFAULT_PER_PAGE = 50

#: Host RobotEvents' canonical public event page lives under -- see this
#: module's docstring ("the event's canonical public page is
#: https://www.robotevents.com/{sku}.html").
EVENT_PAGE_BASE = "https://www.robotevents.com"


def _events_url(
    api_base: str,
    season_ids: list[int],
    region: str,
    event_types: list[str],
    start: str,
    page: int,
    per_page: int,
) -> str:
    """Build one ``GET {api_base}/events`` URL.

    Uses a list of ``(key, value)`` pairs (not a ``dict``) with
    ``urllib.parse.urlencode`` so repeated array-style keys
    (``season[]``, ``eventTypes[]``) survive intact -- a ``dict`` can
    only hold one value per key.
    """
    params: list[tuple[str, str]] = []
    for season_id in season_ids:
        params.append(("season[]", str(season_id)))
    if region:
        params.append(("region", region))
    for event_type in event_types:
        params.append(("eventTypes[]", event_type))
    if start:
        params.append(("start", start))
    params.append(("page", str(page)))
    params.append(("per_page", str(per_page)))
    query = urllib.parse.urlencode(params)
    return f"{api_base.rstrip('/')}/events?{query}"


def _auth_headers() -> dict[str, str]:
    """Build the Bearer-auth header RobotEvents API v2 requires.

    Reads the token fresh on every call via
    ``config.get_robotevents_api_key()`` rather than caching it on the
    adapter instance -- adapter instances are constructed fresh per
    ``adapters.run()`` call (see ``base.py``'s ``Adapter`` docstring:
    "no adapter-instance state to inject into"), matching
    ``adapters/leaguesync.py``'s and ``teams/sources/tba.py``'s
    ``_auth_headers()`` exactly. Raises ``RuntimeError`` (uncaught
    here) when ``ROBOTEVENTS_KEY`` is unset -- this is deliberate: it
    is the "config-read failure" ``pipeline.run()``'s existing
    per-source ``try/except`` must isolate (see this module's own
    docstring and ``config.get_robotevents_api_key()``'s), matching
    ``teams/sources/tba.py``'s documented rationale for why this
    propagates rather than being caught locally.
    """
    return {"Authorization": f"Bearer {config.get_robotevents_api_key()}"}


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse a RobotEvents ``start``/``end`` ISO 8601 date-time.

    RobotEvents' OpenAPI schema documents these as ``format: date-time``
    (a tz-aware ISO 8601 timestamp); the open-source client's captured
    examples show an explicit UTC-offset suffix (e.g.
    ``"2026-02-27T08:00:00-08:00"``). A bare trailing ``Z`` is also
    accepted, matching ``adapters/leaguesync.py``'s
    ``_parse_datetime()`` -- ``datetime.fromisoformat`` doesn't accept
    ``Z`` directly on the Python versions this project supports, so it
    is rewritten to ``+00:00`` first. Returned tz-aware --
    ``normalize.run()`` strips ``tzinfo`` to naive for every ``Event``
    field, so this adapter doesn't convert timezones itself.

    Returns ``None`` for an absent/empty value. Raises ``ValueError``
    on an unparseable non-empty value -- left uncaught here so the
    caller (``_extract_one``) can isolate it as a whole-record
    failure, matching every other structured adapter's convention.
    """
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _extract_location(location: dict[str, Any]) -> str:
    """Build a single "Venue, Street, City, Region Postcode" display
    string from RobotEvents' ``location`` object.

    Matches the comma-separated shape ``normalize.dedup.normalize_venue``
    (sprint 016 ticket 003) expects: a venue/org-name segment, a
    street-number+name segment, then city/region -- so a RobotEvents
    venue that happens to coincide with another source's own record
    (e.g. a host school also registered directly) is eligible for the
    same cross-source dedup collapse any other venue string is.
    """
    venue = (location.get("venue") or "").strip()
    address_1 = (location.get("address_1") or "").strip()
    address_2 = (location.get("address_2") or "").strip()
    city = (location.get("city") or "").strip()
    region = (location.get("region") or "").strip()
    postcode = (location.get("postcode") or "").strip()

    street = " ".join(p for p in (address_1, address_2) if p)
    region_zip = " ".join(p for p in (region, postcode) if p)

    parts = [venue, street, city, region_zip]
    return ", ".join(p for p in parts if p)


def _extract_one(record: dict[str, Any], source: SourceConfig) -> Event:
    """Map one raw RobotEvents ``/events`` record into a canonical ``Event``.

    Raises:
        ValueError: the record has no usable ``name``.
        ValueError: a ``start``/``end`` value is present but
            unparseable.

    Both are caught by the caller (``extract()``) and treated as a
    per-record skip -- never fatal to the rest of the page, matching
    every other structured adapter's convention.
    """
    name = (record.get("name") or "").strip()
    if not name:
        raise ValueError("RobotEvents event record has no name")

    event = Event(kind="event", source_id=source.source_id)
    event_id = record.get("id")
    event.external_id = str(event_id) if event_id is not None else ""

    event.set("title", name, source=SOURCE_NAME, confidence=CONFIDENCE)

    start = _parse_datetime(record.get("start"))
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    end = _parse_datetime(record.get("end"))
    if end is not None:
        event.set("end", end, source=SOURCE_NAME, confidence=CONFIDENCE)

    location = _extract_location(record.get("location") or {})
    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    sku = (record.get("sku") or "").strip()
    if sku:
        event.set(
            "registration_url",
            f"{EVENT_PAGE_BASE}/{sku}.html",
            source=SOURCE_NAME,
            confidence=CONFIDENCE,
        )

    program = record.get("program") or {}
    program_name = (program.get("name") or "").strip()
    if program_name:
        event.set("categories", [program_name], source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


class RobotEventsAdapter:
    """``Adapter`` for RobotEvents API v2 (``robotevents``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Probe ``page=1`` with a cheap ``per_page=1`` request to learn
        the real query's page count, then enumerate one ``EventRef`` per
        real (configured ``per_page``) page -- matching ``adapters/
        localist.py``'s probe-then-paginate shape.

        Raises:
            RuntimeError: ``ROBOTEVENTS_KEY`` is unset/invalid
                (propagated uncaught from ``_auth_headers()``, before
                any request is sent), or the probe request itself
                returns ``401`` (an invalid-but-present token) -- both
                are the "auth failure" this adapter's docstring and
                sprint.md's SUC-008 require ``pipeline.run()``'s
                existing per-source isolation to catch, matching
                ``teams/sources/tba.py``'s explicit-401-raise
                precedent. A non-401 probe failure (bad status,
                unparseable body) degrades to "assume 1 page" instead,
                matching ``adapters/localist.py``'s graceful-degrade
                convention for every other kind of probe failure.
        """
        api_base = source.config.get("api_base") or config.get_robotevents_url()
        season_ids = [int(s) for s in source.config.get("season_ids") or []]
        region = source.config.get("region", "")
        event_types = source.config.get("event_types", DEFAULT_EVENT_TYPES)
        start = source.config.get("start") or date.today().isoformat()
        per_page = int(source.config.get("per_page", DEFAULT_PER_PAGE))

        probe_url = _events_url(api_base, season_ids, region, event_types, start, page=1, per_page=1)
        probe = fetcher.get(probe_url, headers=_auth_headers(), **acquisition_kwargs(source))

        if probe.status == 401:
            raise RuntimeError(
                f"RobotEvents auth failed (401) for {probe_url}; check ROBOTEVENTS_KEY"
            )

        total_pages = 1
        if probe.status == 200:
            try:
                data = json.loads(probe.body)
                total_pages = max(1, int((data.get("meta") or {}).get("last_page", 1)))
            except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
                logger.warning(
                    "RobotEvents probe for %s returned unparseable JSON; assuming 1 page",
                    api_base,
                )
        else:
            logger.warning(
                "RobotEvents probe for %s returned status %s; assuming 1 page",
                api_base,
                probe.status,
            )

        return [
            EventRef(
                url=_events_url(api_base, season_ids, region, event_types, start, page, per_page)
            )
            for page in range(1, total_pages + 1)
        ]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        response = fetcher.get(ref.url, headers=_auth_headers(), **acquisition_kwargs(source))
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "RobotEvents page fetch %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning("RobotEvents page %s returned unparseable JSON; skipping", raw.ref.url)
            return []

        if not isinstance(data, dict):
            logger.warning(
                "RobotEvents page %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        events: list[Event] = []
        for record in data.get("data") or []:
            if not isinstance(record, dict):
                continue
            try:
                event = _extract_one(record, source)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed RobotEvents event record on %s: %s", raw.ref.url, exc
                )
                continue
            events.append(event)

        return events
