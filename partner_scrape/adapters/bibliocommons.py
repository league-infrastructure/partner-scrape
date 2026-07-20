"""BiblioCommons library-system events API adapter.

BiblioCommons is the shared events/catalog platform behind San Diego
County Library (``sdcl.bibliocommons.com``) and San Diego Public
Library (``sandiego.bibliocommons.com``) -- confirmed live (2026-07-19)
by probing ``https://sdpl.bibliocommons.com/info/select_library``'s
library-picker dropdown, which lists both as ``<option value="sdcl">San
Diego County Library</option>`` and ``<option value="sandiego">San
Diego Public Library</option>``. Per ``dev/SCRAPER_GUIDELINES.md``
Section 3, SDCL alone accounted for ~1,173 dated events in the earlier
HTML-scrape analysis -- the single biggest event-volume source this
project handles.

**Endpoint used**: the structured JSON gateway API, not the HTML
fallback ``dev/SCRAPER_GUIDELINES.md`` Section 3 describes. Live
probing found the current BiblioCommons front end
(``{subdomain}.bibliocommons.com/events/search``) redirects (200) to a
client-rendered ``/v2/events`` React SPA shell with no server-rendered
event markup at all -- the CSS-selector approach that guideline
documents (``.event-summary-title``, ``<time datetime>``, etc.)
predates this SPA rewrite and no longer applies to either library. The
real data source **is** the JSON gateway both the SPA and the old HTML
approach ultimately read from::

    GET https://gateway.bibliocommons.com/v2/libraries/{subdomain}/events?page={page}&limit={limit}

confirmed live against ``sdcl`` (HTTP 200, structured JSON, thousands
of dated upcoming events, no past events observed across a full-range
sample -- the endpoint already scopes to current/upcoming without an
explicit date filter, matching ``tec_rest``'s ``start_date=now``
convention but for free). Pagination is page/limit-based, with
``events.pagination.pages`` telling the client how many pages exist --
the same probe-then-paginate shape ``tec.py``/``localist.py`` already
use.

**SDPL's events feature is confirmed disabled** on BiblioCommons: the
same gateway call against ``sandiego`` returns HTTP 403 with
``{"error": {"message": "The Events feature is not available at San
Diego Public Library"}}`` -- SDPL evidently runs its real events
program through a different system (``dev/SCRAPER_GUIDELINES.md``
Section 3's separately-documented "Drupal Events (sandiego.gov)"
extractor targets exactly this). SDPL is still registered here
(``registry/sources/sdpl.toml``, ``config.subdomain = "sandiego"``)
with a real, confirmed subdomain rather than omitted, because this
adapter's existing non-200 handling (below,
identical to ``tec_rest``/``localist``'s "probe fails -> degrade to one
page; non-200 page -> log and yield zero events, never raise") already
copes with this source correctly and for free: it will yield zero
events today without crashing the run, and will start working with no
code changes the day BiblioCommons enables Events for SDPL. Zero
results from a real, reachable source is a legitimate non-error state,
matching this registry's existing convention for a company's genuinely
empty Greenhouse board (see ``boundlessbio.toml``).

**Field-mapping decisions** (implementer's call, documented per this
project's convention):
- ``eventTypes`` -> ``Event.categories`` (mirrors ``tags``/
  ``categories`` conventions elsewhere: BiblioCommons' "type" taxonomy
  -- "Storytime", "STEAM", "Book Club", etc. -- is the closest match to
  what TEC/Localist call categories).
- ``eventAudiences`` -> ``Event.age_grade_level`` -- BiblioCommons'
  audience taxonomy ("Kids", "Teens", "Birth to Five", "Older Adults
  55+", ...) is an explicit, first-party age/audience signal, exactly
  what this field is for.
- ``eventPrograms`` (an event's optional named program, e.g. "Summer at
  Your Library") -> ``Event.tags``, kept a separate list from
  categories per the existing tags/categories split.
- No ``cost`` mapping: BiblioCommons event records carry no cost field
  at all (library programs are free; there is nothing analogous to
  TEC's ``cost``/``cost_details``), so ``Event.cost`` is simply never
  set by this adapter.
- ``registration_url`` is always the constructed BiblioCommons event
  detail page (``https://{subdomain}.bibliocommons.com/events/{id}``,
  confirmed live to 200 and render that event's title), regardless of
  ``registrationInfo.provider`` -- BiblioCommons' own event page
  surfaces registration UI (or the external link) for every provider
  value observed live (``EXTERNAL``, ``BIBLIO_EVENTS``, ``None``), so
  it is the one registration/detail URL guaranteed to resolve.

**Per-occurrence rows, and why no id-collapsing dedup is needed** (the
task's "dedupe recurring instances (like Localist)" concern):
unlike Localist -- which repeats the *same* event ``id`` once per
matching calendar day within a query window -- BiblioCommons already
gives every future occurrence of a recurring series its own distinct
``id`` (only ``seriesId`` is shared). A live sample confirmed the same
``seriesId`` legitimately appearing multiple times on one page with
different ``id``s and different ``start`` dates (e.g. "Tai Chi Exercise
Class" on both 2026-10-29 and 2026-12-29) -- these are genuinely
different bookable occurrences, not duplicate rows of the same one, so
each is correctly emitted as its own ``Event``. :func:`extract` still
keeps a defensive within-page ``seen_ids`` guard (matching
``localist.py``'s convention) in case the same ``id`` were ever repeated
within one page's ``items`` list, but it is not expected to trigger in
practice.
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
SOURCE_NAME = "bibliocommons"

#: BiblioCommons' gateway API is a structured, first-party feed -- every
#: field this adapter sets is maximally trusted, matching
#: tec_rest/localist's convention.
CONFIDENCE = 1.0

#: Events per page for the paginated fetches, matching tec_rest/
#: localist's default page size. Also the probe's page size -- see
#: ``discover()`` for why this differs from TEC/Localist's cheap
#: ``per_page=1``/``pp=1`` probes.
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
    """Strip HTML tags and decode the common entities BiblioCommons
    descriptions use. Same small, proven approach as ``tec.py``'s
    ``_strip_html`` -- duplicated rather than imported, matching this
    project's existing per-adapter convention (see ``greenhouse.py``'s
    docstring note on the same choice).
    """
    stripped = _TAG_RE.sub(" ", text)
    stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
    for entity, replacement in _HTML_ENTITIES.items():
        stripped = stripped.replace(entity, replacement)
    return stripped


def _parse_datetime(value: str) -> datetime | None:
    """Parse a BiblioCommons ``definition.start``/``definition.end`` string.

    BiblioCommons emits two shapes: a full local datetime
    (``"2026-07-20T11:00"``) for timed events, and a bare date
    (``"2026-12-03"``) for all-day ones -- ``datetime.fromisoformat``
    (Python 3.11+) parses both directly. Returns ``None`` for an
    absent/empty value. Raises ``ValueError`` on an unparseable
    non-empty value -- left uncaught here so the caller
    (``_extract_one``) can isolate it as a whole-record failure, matching
    ``tec.py``/``localist.py``'s convention.
    """
    if not value:
        return None
    return datetime.fromisoformat(value)


def _is_all_day(raw_start: str) -> bool:
    """A bare-date ``start`` (no ``T``) is BiblioCommons' all-day signal.

    BiblioCommons has no explicit ``all_day`` boolean field (unlike
    TEC) -- the date-only vs. full-datetime string shape is the only
    signal available, confirmed live: all-day-looking records
    ("Digital Literacy and Tech Support") consistently use the bare
    ``"2026-12-03"`` shape for both ``start`` and ``end``.
    """
    return bool(raw_start) and "T" not in raw_start


def _extract_location(raw_definition: dict[str, Any], locations: dict[str, Any]) -> str:
    """Build a single display string from branch name + room details.

    Mirrors ``localist.py``'s ``location_name, room_number`` combining
    convention: BiblioCommons' ``branchLocationId`` resolves to a
    branch name via the response's own ``entities.locations`` map (no
    second API call needed), and ``locationDetails`` (e.g. "Community
    Room") is that branch's specific room, when given.
    """
    branch_id = raw_definition.get("branchLocationId")
    branch_name = ""
    if branch_id is not None:
        branch = locations.get(str(branch_id)) or {}
        branch_name = (branch.get("name") or "").strip()
    room = (raw_definition.get("locationDetails") or "").strip()
    if branch_name and room:
        return f"{branch_name}, {room}"
    return branch_name or room


def _names_for_ids(ids: Iterable[Any], catalog: dict[str, Any]) -> list[str]:
    """Resolve a list of entity ids against a ``{id: {"name": ...}}`` catalog.

    Shared helper for ``eventTypes``/``eventAudiences``/``eventPrograms``
    lookups -- all three are the same "id -> {'name': ...}" shape in
    ``entities``. Ids absent from the catalog (never observed live, but
    not impossible) are silently skipped rather than raising.
    """
    names = []
    for entity_id in ids or []:
        entry = catalog.get(str(entity_id))
        if entry and entry.get("name"):
            names.append(entry["name"])
    return names


def _registration_url(subdomain: str, event_id: str) -> str:
    """BiblioCommons' own event detail page -- see module docstring."""
    return f"https://{subdomain}.bibliocommons.com/events/{event_id}"


def _extract_one(
    raw_event: dict[str, Any], source: SourceConfig, subdomain: str, entities: dict[str, Any]
) -> Event:
    """Map one raw BiblioCommons event record into a canonical ``Event``.

    Raises:
        ValueError: the record has no usable title.
        ValueError: a ``start``/``end`` value is present but
            unparseable.

    Both are caught by the caller (``extract()``) and treated as a
    per-record skip -- never fatal to the rest of the page.
    """
    definition = raw_event.get("definition") or {}
    title = (definition.get("title") or "").strip()
    if not title:
        raise ValueError("event record has no title")

    event_id = str(raw_event.get("id") or "")

    event = Event(kind="event", source_id=source.source_id)
    event.external_id = event_id

    event.set("title", title, source=SOURCE_NAME, confidence=CONFIDENCE)

    description = _strip_html(definition.get("description") or "")
    if description:
        event.set("description", description, source=SOURCE_NAME, confidence=CONFIDENCE)

    raw_start = definition.get("start") or ""
    start = _parse_datetime(raw_start)
    if start is not None:
        event.set("start", start, source=SOURCE_NAME, confidence=CONFIDENCE)

    end = _parse_datetime(definition.get("end") or "")
    if end is not None:
        event.set("end", end, source=SOURCE_NAME, confidence=CONFIDENCE)

    event.set("all_day", _is_all_day(raw_start), source=SOURCE_NAME, confidence=CONFIDENCE)

    location = _extract_location(definition, entities.get("locations") or {})
    if location:
        event.set("location", location, source=SOURCE_NAME, confidence=CONFIDENCE)

    if event_id:
        event.set(
            "registration_url",
            _registration_url(subdomain, event_id),
            source=SOURCE_NAME,
            confidence=CONFIDENCE,
        )

    image_id = definition.get("featuredImageId")
    if image_id:
        image = (entities.get("images") or {}).get(str(image_id)) or {}
        image_url = (image.get("url") or "").strip()
        if image_url:
            event.set("image_url", image_url, source=SOURCE_NAME, confidence=CONFIDENCE)

    categories = _names_for_ids(definition.get("typeIds"), entities.get("eventTypes") or {})
    if categories:
        event.set("categories", categories, source=SOURCE_NAME, confidence=CONFIDENCE)

    age_grade_level = _names_for_ids(
        definition.get("audienceIds"), entities.get("eventAudiences") or {}
    )
    if age_grade_level:
        event.set("age_grade_level", age_grade_level, source=SOURCE_NAME, confidence=CONFIDENCE)

    program_id = definition.get("programId")
    tags = _names_for_ids([program_id] if program_id else [], entities.get("eventPrograms") or {})
    if tags:
        event.set("tags", tags, source=SOURCE_NAME, confidence=CONFIDENCE)

    return event


def _page_url(api_base: str, limit: int, page: int) -> str:
    return f"{api_base}?page={page}&limit={limit}"


class BiblioCommonsAdapter:
    """``Adapter`` for the BiblioCommons library events API (``bibliocommons``)."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Probe ``page=1`` at the real configured ``limit`` to learn
        ``events.pagination.pages``, then enumerate one ``EventRef`` per
        page at that same ``limit`` -- matching TEC/Localist's
        probe-then-paginate shape, with one deliberate difference: the
        probe reuses the *real* ``limit`` rather than a cheap
        ``limit=1``. Live verification (2026-07-19) confirmed
        BiblioCommons' ``events.pagination.pages`` scales with the
        requested ``limit`` (``limit=1`` on SDCL returned
        ``pages=7287``, one per event; ``limit=50`` correctly returned
        ``pages=146``) -- a ``limit=1`` probe would silently generate
        one ``EventRef`` per *event* rather than per page, wildly
        over-fetching. Reusing the real ``limit`` costs a slightly
        larger probe request than TEC/Localist's, but is the only value
        confirmed correct for this API.

        A probe that fails to fetch or parse (including SDPL's live
        "Events feature not available" 403) is treated as "exactly one
        page" rather than raising -- per-source failure isolation
        belongs to the Pipeline; this adapter degrades gracefully
        rather than crashing the whole run.
        """
        subdomain = source.config["subdomain"]
        limit = int(source.config.get("limit", PAGE_SIZE))
        api_base = f"https://gateway.bibliocommons.com/v2/libraries/{subdomain}/events"

        probe_url = _page_url(api_base, limit, page=1)
        probe = fetcher.get(probe_url)

        total_pages = 1
        if probe.status == 200:
            try:
                data = json.loads(probe.body)
                total_pages = max(1, int(data["events"]["pagination"]["pages"]))
            except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                logger.warning(
                    "BiblioCommons probe for %s returned unparseable JSON; assuming 1 page",
                    api_base,
                )
        else:
            logger.warning(
                "BiblioCommons probe for %s returned status %s; assuming 1 page",
                api_base,
                probe.status,
            )

        return [
            EventRef(url=_page_url(api_base, limit, page)) for page in range(1, total_pages + 1)
        ]

    def fetch(self, ref: EventRef, fetcher: Fetcher) -> RawResponse:
        response = fetcher.get(ref.url)
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        if raw.status != 200:
            logger.warning(
                "BiblioCommons page fetch %s returned status %s; skipping",
                raw.ref.url,
                raw.status,
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning(
                "BiblioCommons page %s returned unparseable JSON; skipping", raw.ref.url
            )
            return []

        if not isinstance(data, dict) or "events" not in data or "entities" not in data:
            logger.warning(
                "BiblioCommons page %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        subdomain = source.config["subdomain"]
        entities = data.get("entities") or {}
        raw_events = entities.get("events") or {}

        events: list[Event] = []
        seen_ids: set[str] = set()
        for event_id in (data.get("events") or {}).get("items") or []:
            if event_id in seen_ids:
                # Defensive within-page dedup, matching localist.py's
                # convention -- see module docstring on why this is not
                # expected to trigger for BiblioCommons in practice.
                continue

            raw_event = raw_events.get(event_id)
            if not raw_event:
                continue

            try:
                event = _extract_one(raw_event, source, subdomain, entities)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed BiblioCommons event record on %s: %s", raw.ref.url, exc
                )
                continue

            seen_ids.add(event_id)
            events.append(event)

        return events
