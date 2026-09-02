"""The ``program_page``/``program_listing`` Adapters: LLM-extracted program pages.

Sprint 027 tickets 003/004. See ``adapters/DESIGN.md``'s sprint 027
section and sprint.md's SUC-031/SUC-032: given one registered program
page URL (a paid summer research placement, an internship, a
scholarship, or similar application-window program) -- or, for
``program_listing``, a listing page whose cards each link to one such
page -- fetch it and call the ticket-002 LLM extraction client
(``program_llm.py``) to turn its raw prose into a canonical ``Event``
carrying deadline-first fields -- ``kind``, ``start``/``end``,
``eligibility``, ``opportunity_type`` -- that no structured API publishes
and no deterministic ``extract/`` ladder rung could recover.

Structurally parallel to every other single-page adapter in this package
(``greenhouse.py``/``lever.py``'s "no probe-then-paginate" ``discover()``,
``listing_html.py``'s "fetch, map, construct one Event" ``extract()``),
substituting one LLM extraction call plus a content-hash cache lookup for
the structured-API JSON parse / HTML ladder those adapters use instead.
``ProgramPageAdapter`` and ``ProgramListingAdapter`` are the ``program_page``/
``listing_html`` pair's own analogue: identical fetch/extract, differing
only in ``discover()`` -- see :func:`_extract_one_program`, the shared
helper both classes' ``extract()`` calls, mirroring
``generic_html.py``/``listing_html.py``'s shared ``extract.ladder.
extract_fields()`` extraction step.

**Constructor-injection deviation** (documented in ``adapters/DESIGN.md``'s
§3): unlike every other adapter, these adapters accept optional
``llm_client``/``cache`` overrides so tests can substitute
``program_llm.FixtureProgramLLMClient`` without touching a network socket.
``get_adapter()``'s zero-arg construction (``base.py``, unchanged) still
produces a fully-working production instance -- the defaults construct a
real ``AnthropicProgramLLMClient``/``ProgramExtractionCache``.

**No ``description`` field.** ``ProgramExtractionResult`` (ticket 002)
carries no ``description`` output -- only ``program_name``,
``audience_grades``, ``date_start``, ``date_end``, ``cost``,
``eligibility``, ``is_open``, and ``opportunity_type``. Neither adapter
invents one; ``Event.description`` is simply left unset for these records.

**A closed page is still emitted.** ``result.is_open is False`` is not
checked here -- filtering "is this program still current" happens at
export time via ``export.writer.is_current_or_upcoming()``, not at
extraction time (see ``normalize/DESIGN.md``'s sprint 027 addendum). This
module's job is only to map the LLM's structured output onto an ``Event``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

from partner_scrape.adapters.base import EventRef, RawResponse, acquisition_kwargs
from partner_scrape.adapters.program_cache import ProgramExtractionCache
from partner_scrape.adapters.program_llm import (
    PROGRAM_LLM_CONFIDENCE,
    PROGRAM_LLM_SOURCE,
    AnthropicProgramLLMClient,
    ProgramLLMClient,
)
from partner_scrape.fetch import Fetcher
from partner_scrape.model import PROGRAM_EXTRACTION_KINDS, Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: This adapter's own provenance source name -- recorded only for fields
#: *this adapter* decides directly (an operator-curated
#: ``config.opportunity_type`` override), never for fields sourced from
#: the LLM extraction result itself (those use ``PROGRAM_LLM_SOURCE``).
SOURCE_NAME = "program_page"

#: Confidence recorded for an operator-curated ``config`` override -- a
#: known, hand-authored value, not a guess, matching ``listing_html.py``'s
#: ``CONFIDENCE_DEFAULT_LOCATION`` convention for the same kind of
#: registry-authored-override field.
CONFIDENCE_CONFIG_OVERRIDE = 1.0


def _parse_program_date(value: str, field_name: str, url: str) -> datetime | None:
    """Parse one of ``ProgramExtractionResult``'s ISO date strings.

    Returns ``None`` for an empty string (the LLM found no such date on
    the page) or an unparseable non-empty value -- logged, never raised,
    so one bad date never drops the whole page's ``Event`` (matching this
    module's general per-page, not per-field, error-isolation stance).
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.warning(
            "Program page %s: could not parse %s=%r as an ISO date; leaving unset",
            url,
            field_name,
            value,
        )
        return None


def _extract_one_program(
    raw: RawResponse,
    source: SourceConfig,
    llm_client: ProgramLLMClient,
    cache: ProgramExtractionCache,
) -> list[Event]:
    """Map one fetched program page into zero or one canonical ``Event``.

    Shared by ``ProgramPageAdapter.extract()`` and
    ``ProgramListingAdapter.extract()`` -- both adapter types fetch a URL
    and turn it into an ``Event`` via the identical fetch+cache+LLM-
    extract+map-to-Event logic once a URL is in hand; only ``discover()``
    differs between them (see this module's docstring, and
    ``generic_html.py``/``listing_html.py``'s identical relationship via
    ``extract.ladder.extract_fields()``).

    A non-200 fetch is logged and skipped (``[]``), matching
    ``listing_html.py``'s convention. Otherwise: check the program
    extraction cache by URL + content hash; on a miss, call the injected
    ``ProgramLLMClient`` and store the result. The source's
    ``config.program_kind`` (required; ``"internship"`` or ``"program"``)
    sets ``Event.kind`` -- a missing or invalid value is logged and
    skipped, never raised, matching this module's general per-record
    error-isolation stance.
    """
    if raw.status != 200:
        logger.warning(
            "Program page fetch %s returned status %s; skipping",
            raw.ref.url,
            raw.status,
        )
        return []

    result = cache.lookup(raw.ref.url, raw.body)
    if result is None:
        result = llm_client.extract_program(raw.ref.url, raw.body)
        cache.store(raw.ref.url, raw.body, result)

    program_kind = source.config.get("program_kind")
    if program_kind not in PROGRAM_EXTRACTION_KINDS:
        logger.warning(
            "Program page %s has an invalid/missing config.program_kind=%r "
            "(expected one of %s); skipping",
            raw.ref.url,
            program_kind,
            sorted(PROGRAM_EXTRACTION_KINDS),
        )
        return []

    event = Event(kind=program_kind, source_id=source.source_id, url=raw.ref.url)

    if result.program_name:
        event.set(
            "title", result.program_name, source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE
        )

    start = _parse_program_date(result.date_start, "date_start", raw.ref.url)
    if start is not None:
        event.set("start", start, source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE)

    end = _parse_program_date(result.date_end, "date_end", raw.ref.url)
    if end is not None:
        event.set("end", end, source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE)

    if result.eligibility:
        event.set(
            "eligibility",
            result.eligibility,
            source=PROGRAM_LLM_SOURCE,
            confidence=PROGRAM_LLM_CONFIDENCE,
        )

    if result.cost:
        event.set("cost", result.cost, source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE)

    # opportunity_type: an explicit config override (an
    # operator-curated, known value, e.g. the SD Foundation
    # Scholarship's "Funding Opportunities") always wins over the
    # LLM's own classification -- see adapters/DESIGN.md's sprint
    # 027 "Kind, not opportunity_type, is this mechanism's
    # discriminator" note. Either way, kind == "internship" still
    # gets its opportunity_type forced to "Work-based Learning"
    # downstream by normalize/run.py, unconditionally.
    opportunity_type_override = source.config.get("opportunity_type")
    if opportunity_type_override:
        event.set(
            "opportunity_type",
            opportunity_type_override,
            source=SOURCE_NAME,
            confidence=CONFIDENCE_CONFIG_OVERRIDE,
        )
    elif result.opportunity_type:
        event.set(
            "opportunity_type",
            result.opportunity_type,
            source=PROGRAM_LLM_SOURCE,
            confidence=PROGRAM_LLM_CONFIDENCE,
        )

    # registration_url: an explicit config.apply_url override (a
    # program whose application form lives at a different URL than
    # the page this adapter read) wins; otherwise the page's own
    # URL is the apply link.
    apply_url = source.config.get("apply_url") or raw.ref.url
    event.set(
        "registration_url", apply_url, source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE
    )

    return [event]


class ProgramPageAdapter:
    """``Adapter`` for one individually-registered program page (``program_page``).

    See this module's docstring for the constructor-injection deviation
    from every other adapter's "no instance state" invariant.
    """

    def __init__(
        self,
        llm_client: ProgramLLMClient | None = None,
        cache: ProgramExtractionCache | None = None,
    ) -> None:
        self.llm_client: ProgramLLMClient = (
            llm_client if llm_client is not None else AnthropicProgramLLMClient()
        )
        self.cache = cache if cache is not None else ProgramExtractionCache()

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Return exactly one ``EventRef`` for the source's configured page.

        No probe-then-paginate step -- a ``program_page`` source is
        always a single fixed URL, matching ``greenhouse.py``'s/
        ``lever.py``'s shape.

        Raises:
            KeyError: ``source.config`` has no ``url`` key.
        """
        return [EventRef(url=source.config["url"])]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        """Standard single-page GET, matching every other adapter's ``fetch()``."""
        response = fetcher.get(ref.url, **acquisition_kwargs(source))
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        """Map one fetched program page into zero or one canonical ``Event``.

        Delegates to :func:`_extract_one_program`, the helper shared with
        ``ProgramListingAdapter``. See that function's docstring for the
        full extraction/caching behavior.
        """
        return _extract_one_program(raw, source, self.llm_client, self.cache)


class ProgramListingAdapter:
    """``Adapter`` for a program-listing page whose cards each link to one
    curated program page (``program_listing``).

    Structurally identical to ``ProgramPageAdapter`` apart from
    ``discover()`` -- see this module's docstring, and
    ``listing_html.py``'s identical relationship to ``generic_html.py``.
    Each discovered card is fetched and extracted independently, one LLM
    extraction call per program, so no two discovered programs ever share
    an audience/grade/deadline/eligibility value.
    """

    def __init__(
        self,
        llm_client: ProgramLLMClient | None = None,
        cache: ProgramExtractionCache | None = None,
    ) -> None:
        self.llm_client: ProgramLLMClient = (
            llm_client if llm_client is not None else AnthropicProgramLLMClient()
        )
        self.cache = cache if cache is not None else ProgramExtractionCache()

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[EventRef]:
        """Resolve ``source`` into one ``EventRef`` per matched card/detail
        link via listing-page discovery -- no discovery logic of its own.

        Delegates entirely to ``discovery.listing.discover_via_listing``,
        the exact mechanism ``ListingHtmlAdapter.discover()`` already
        uses -- requires ``source.config["listing_urls"]`` and
        ``source.config["site_url"]``, the identical config shape
        ``listing_html`` sources already use.

        The import is deferred to call time to break the import cycle
        between ``adapters`` (whose package ``__init__`` eagerly imports
        every adapter, including this one) and ``discovery.listing``
        (which imports ``EventRef`` from ``adapters.base``) -- matching
        ``ListingHtmlAdapter.discover()``'s existing import-cycle
        workaround.
        """
        from partner_scrape.discovery.listing import discover_via_listing

        return discover_via_listing(source, fetcher)

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        """Standard single-page GET, matching every other adapter's ``fetch()``."""
        response = fetcher.get(ref.url, **acquisition_kwargs(source))
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        """Map one fetched discovered program card's detail page into zero
        or one canonical ``Event``.

        Delegates to :func:`_extract_one_program`, the helper shared with
        ``ProgramPageAdapter`` -- identical logic, called once per
        discovered card by ``adapters.run()``'s own fetch/extract loop,
        so a fetch failure on one card is isolated (logged, skipped) and
        never prevents the rest of the listing's cards from still
        yielding their own ``Event``s.
        """
        return _extract_one_program(raw, source, self.llm_client, self.cache)
