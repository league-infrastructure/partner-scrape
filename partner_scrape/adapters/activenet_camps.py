"""The ``activenet_camps`` Adapter: camp sessions hosted on
``campscui.active.com`` (ActiveNet's "Camps CUI" registration platform).

Sprint 028 ticket 005 (issue 29): the first of issue 29's two in-scope
platform adapters -- see ``adapters/DESIGN.md``'s sprint 028 section
("``activenet_camps``/``campbrain``: platform adapters sharing the LLM
family's own intermediate shape") for the full architecture write-up.
``ActiveNetCampsAdapter`` shares ``ProgramPageAdapter``'s exact
``discover()``/``fetch()`` shape -- one registered ``config.url`` per
organization (the platform's per-org camp-listing endpoint), one
``EventRef``, no probe-then-paginate step -- and differs only in
``extract()``: a deterministic JSON parse is attempted first
(:data:`CONFIDENCE_STRUCTURED_PLATFORM`, mirroring the Structured API
family's own confidence convention); if the fetched body does not parse
as ActiveNet's own sessions-list JSON shape, ``extract()`` falls back to
``extract.reduce_html_to_text()`` plus ``ProgramLLMClient.
extract_programs()`` -- the exact same call ``program_page_multi``
already makes, via :func:`partner_scrape.adapters.program_page.
_extract_many_programs`, reused unmodified. Either path produces a
``list[ProgramExtractionResult]``, mapped onto ``Event``s via the
existing :func:`partner_scrape.adapters.program_page._map_result_to_event`
-- no new mapping code, per this ticket's own explicit design.

**Live verification (2026-09-01).** Issue 29 called ActiveNet
"HTML-ish," not confirmed. Live investigation of both named orgs'
registration links found a third case beyond "clean JSON" or "plain
HTML prose": ``campscui.active.com`` is a client-side single-page
application (a RequireJS-based bundle) gated by a JavaScript
fingerprint/cookie challenge (an ``e4rt=Safetynet``-tagged redirect
chain) -- a plain static GET (``PoliteFetcher``'s ``urllib`` transport)
receives only a content-free bootstrap shell or a bare ``403``, never
the rendered session list. The org's real session data (name, dates,
price, remaining capacity) is only reachable once the SPA's own
JavaScript executes and calls its private ``/external/json/seasons``
and ``/external/json/seasons/{id}/sessions`` (or ``/sessions/group``)
endpoints -- confirmed via a headless-browser network-tab capture
against both San Diego Air & Space Museum's and Helen Woodward Animal
Center's real ActiveNet org pages, using a *custom* script (a longer
``wait_until="networkidle"`` navigation plus several extra seconds of
settle time). This project already has a headless-capable ``Fetcher``
(``fetch/headless.py``'s ``PlaywrightFetcher``, wired in by
``pipeline.run()`` for any source with ``acquisition_policy.
fetch_strategy = "headless"``), so every ``activenet_camps``
registration sets that flag -- **no credential or API key is needed**
(the gate is a browser-fingerprint challenge, not an auth token, so no
``config.py`` accessor pair is added, per this ticket's own "add the
accessor only if a credential is confirmed necessary" instruction).

**However**, a real end-to-end dry run through this project's *own*
``PlaywrightFetcher.get()`` (its fixed ``wait_until="load"`` navigation
with no additional settle wait before ``page.content()`` -- shared by
every headless-flagged source in the registry, not owned by
``adapters/``) found that wait strategy insufficient for this
particular heavy SPA: the body it captures is still the pre-render
loading shell, not the rendered session list a longer wait reaches (see
``registry/sources/helen-woodward-camps.toml``'s and
``sandiego-air-space-camps.toml``'s own comments for the live
evidence). Both named orgs are therefore registered ``enabled = false``
for now, pending a follow-up fix to ``fetch/headless.py``'s wait
strategy -- out of this ticket's own scope, since that module is shared
across every headless source, not something ``adapters/activenet_camps``
owns. Once that lands, ``raw.body`` will be the fully JS-rendered page's
HTML (``page.content()``) -- real dated/priced session text is present
in the DOM once fully rendered (confirmed live), but it is rendered
*markup*, not the underlying JSON the SPA itself called;
:func:`_try_parse_activenet_sessions_json` therefore correctly declines
to match it, and every current ``activenet_camps`` registration is
designed to exercise the LLM-fallback path in practice. The
deterministic-JSON path is still implemented and tested (against the
real ``{"count": ..., "sessions": [...]}`` shape captured from both
orgs' own ``/external/json/seasons/{id}/sessions`` responses) because
the *adapter contract* itself must support a future ActiveNet
integration (or ``config.url`` pointed directly at a JSON endpoint)
that does expose clean JSON without the SPA wrapper -- see this
module's own Design note below.

**Design note: reusing ``_map_result_to_event`` unmodified.** Per this
ticket's explicit instruction, both extraction paths share the *exact*
mapping helper ``program_page_multi`` already uses, which unconditionally
stamps every LLM-shaped field via ``program_llm.PROGRAM_LLM_SOURCE``/
``PROGRAM_LLM_CONFIDENCE`` (0.9), and stamps a ``config.opportunity_type``
override via ``program_page.SOURCE_NAME`` ("program_page")/
``CONFIDENCE_CONFIG_OVERRIDE`` (1.0). :data:`CONFIDENCE_STRUCTURED_PLATFORM`
(1.0) is defined here, matching ``adapters/DESIGN.md``'s own Interfaces
entry for it and the Structured API family's ``CONFIDENCE = 1.0``
convention that the deterministic-parse path conceptually follows, but
-- because reusing ``_map_result_to_event`` verbatim is the ticket's own
"zero new mapping code" requirement -- it is not currently threaded into
any ``Event.set()`` call; a deterministically-parsed session's fields are
recorded at the same 0.9 confidence a real LLM call would use. This is a
deliberate, documented simplification (this module makes no attempt to
special-case provenance for a path that, per the Live Verification note
above, no current registration actually exercises), not an oversight --
matching this codebase's convention (see e.g. ``program_llm.py``'s own
"is_open reads oddly for a camp session" note) of writing down an
accepted rough edge rather than adding mapping-layer complexity to avoid
it before real need is demonstrated.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from partner_scrape.adapters.base import EventRef, RawResponse, acquisition_kwargs
from partner_scrape.adapters.program_cache import ProgramExtractionCache
from partner_scrape.adapters.program_llm import (
    AnthropicProgramLLMClient,
    ProgramExtractionResult,
    ProgramLLMClient,
)
from partner_scrape.adapters.program_page import _extract_many_programs, _map_result_to_event, _resolve_program_kind
from partner_scrape.fetch import Fetcher
from partner_scrape.model import Event
from partner_scrape.registry.schema import SourceConfig

logger = logging.getLogger(__name__)

#: Confidence recorded on a session field recovered by the deterministic
#: JSON-parse path, mirroring every Structured API adapter's own
#: ``CONFIDENCE = 1.0`` convention (``adapters/DESIGN.md``'s Interfaces
#: entry for this constant). See this module's docstring's Design note
#: for why it is not currently threaded through ``Event.set()`` --
#: reusing ``_map_result_to_event`` unmodified means every mapped field
#: is recorded at ``program_llm.PROGRAM_LLM_CONFIDENCE`` (0.9) regardless
#: of which extraction path produced it.
CONFIDENCE_STRUCTURED_PLATFORM = 1.0


def _activenet_date_to_iso(value: Any) -> str:
    """Convert one ActiveNet structured date object (``{"year": 2026,
    "month": 10, "day": 26, ...}``) to an ISO ``YYYY-MM-DD`` string.

    Returns ``""`` (matching ``ProgramExtractionResult``'s own "not
    stated" convention) for anything that isn't a dict with the three
    required integer keys -- logged, never raised, so one malformed date
    on an otherwise-good session never drops the whole page's other
    sessions (this module's own instance of ``adapters/DESIGN.md``'s
    per-record error-isolation invariant).
    """
    if not isinstance(value, dict):
        return ""
    try:
        year, month, day = int(value["year"]), int(value["month"]), int(value["day"])
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (KeyError, TypeError, ValueError):
        logger.warning("ActiveNet session date %r is not a well-formed date object; leaving unset", value)
        return ""


def _activenet_session_cost(session: dict[str, Any]) -> str:
    """Return a short cost string from a session's first ``tuitions``
    entry's ``price`` (e.g. ``"$103.02"``), or ``""`` if the session
    carries no tuition/price at all -- matching
    ``ProgramExtractionResult.cost``'s own "not stated" convention.

    A real ActiveNet session can carry more than one tuition option
    (e.g. a "Daily" price and a waitlist entry at the same price, both
    seen live on Helen Woodward's own response) -- the first is used, the
    same "one representative value, not every option" simplification
    this project's other adapters already make for free-text cost
    fields.
    """
    tuitions = session.get("tuitions")
    if not isinstance(tuitions, list) or not tuitions:
        return ""
    first = tuitions[0]
    if not isinstance(first, dict):
        return ""
    price = first.get("allInclusivePrice", first.get("price"))
    if not isinstance(price, (int, float)):
        return ""
    return f"${price:,.2f}"


def _activenet_session_is_open(session: dict[str, Any]) -> bool:
    """Return whether a session still has open capacity.

    ActiveNet's live response carries both a session-level
    ``availableQuantity`` and a large sentinel (``999999999``) for an
    unlimited-capacity session -- only a *non-negative, finite-looking*
    zero or below is treated as sold out; a missing/non-numeric value
    defaults to ``True`` (open), matching ``ProgramExtractionResult.
    is_open``'s own documented default for "no clear signal either way."
    """
    available = session.get("availableQuantity")
    if isinstance(available, (int, float)):
        return available > 0
    return True


def _try_parse_activenet_sessions_json(body: str) -> list[ProgramExtractionResult] | None:
    """Attempt a deterministic parse of ``body`` as ActiveNet's own
    ``{"count": ..., "sessions": [...]}`` JSON shape (captured live from
    both San Diego Air & Space Museum's and Helen Woodward Animal
    Center's real ``/external/json/seasons/{id}/sessions``(``/group``)
    responses -- see this module's docstring).

    Returns ``None`` -- never raises -- for anything that isn't valid
    JSON, or is valid JSON but not this shape (a dict with a
    list-valued ``"sessions"`` key), so :meth:`ActiveNetCampsAdapter.
    extract` can fall back to the LLM-extraction path unconditionally.
    One malformed session dict inside an otherwise-good list is skipped
    (logged), never aborting the whole page's other sessions.
    """
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        return None

    results: list[ProgramExtractionResult] = []
    for session in data["sessions"]:
        if not isinstance(session, dict) or not session.get("name"):
            logger.warning("ActiveNet session entry missing a name; skipping: %r", session)
            continue
        results.append(
            ProgramExtractionResult(
                program_name=session["name"],
                date_start=_activenet_date_to_iso(session.get("startDate")),
                date_end=_activenet_date_to_iso(session.get("endDate")),
                cost=_activenet_session_cost(session),
                is_open=_activenet_session_is_open(session),
                opportunity_type="Camps",
            )
        )
    return results


class ActiveNetCampsAdapter:
    """``Adapter`` for one organization's ``campscui.active.com`` camp
    registration endpoint (``activenet_camps``).

    Same constructor-injection deviation as the ``program_page`` family
    (``adapters/DESIGN.md``'s §3) -- the deterministic-parse path needs
    no LLM client at all, but the constructor shape stays uniform across
    the whole LLM-extraction/camp-platform family so a source can be
    registered either way with no adapter-selection logic anywhere else.
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
        """Return exactly one ``EventRef`` for the source's configured
        camp-listing endpoint.

        Identical to ``ProgramPageAdapter.discover()`` -- an
        ``activenet_camps`` source is always one fixed per-organization
        URL, no probe-then-paginate step.

        Raises:
            KeyError: ``source.config`` has no ``url`` key.
        """
        return [EventRef(url=source.config["url"])]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        """Standard single-page GET, matching every other adapter's
        ``fetch()``.

        The injected ``fetcher`` is whichever ``Fetcher``
        ``pipeline.run()`` chose for this source -- for every
        ``activenet_camps`` registration that is the headless
        (Playwright-backed) ``Fetcher``, via ``acquisition_policy.
        fetch_strategy = "headless"``, since ``campscui.active.com``'s
        real session data is only present once the platform's own
        JavaScript executes (see this module's docstring's Live
        Verification note). This adapter itself has no opinion about
        which ``Fetcher`` it is given -- it never constructs one, per
        ``adapters/DESIGN.md``'s §3 invariant.
        """
        response = fetcher.get(ref.url, **acquisition_kwargs(source))
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        """Map one fetched ActiveNet camp-listing response into zero or
        more canonical ``Event``s.

        A non-200 fetch is logged and skipped (``[]``), matching every
        other adapter's convention. Otherwise, ``raw.body`` is first
        tried as ActiveNet's own sessions-list JSON
        (:func:`_try_parse_activenet_sessions_json`); on a match, each
        session is mapped directly via ``program_page._map_result_to_event``
        with no cache lookup and no LLM call (the parse is deterministic
        and cheap, mirroring every Structured API adapter's own
        ``CONFIDENCE = 1.0`` path). Otherwise ``extract()`` falls back to
        :func:`partner_scrape.adapters.program_page._extract_many_programs`
        unmodified -- the exact same reduce-then-cache-then-LLM-call
        logic ``program_page_multi`` already uses, including its own
        non-200 handling (redundant with the check above, but keeps this
        function's own status check symmetric with every other adapter's
        ``extract()``), per-ref LLM-exception isolation, and
        ``config.program_kind`` gating.
        """
        if raw.status != 200:
            logger.warning(
                "ActiveNet camps fetch %s returned status %s; skipping",
                raw.ref.url,
                raw.status,
            )
            return []

        results = _try_parse_activenet_sessions_json(raw.body)
        if results is not None:
            program_kind = _resolve_program_kind(raw.ref.url, source)
            if program_kind is None:
                return []
            return [
                _map_result_to_event(result, source, program_kind, raw.ref.url) for result in results
            ]

        return _extract_many_programs(raw, source, self.llm_client, self.cache)
