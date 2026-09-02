"""The ``campbrain`` Adapter: camp sessions hosted on CampBrain
(``*.campbrainregistration.com``, BrainRunner Inc.'s family camp
registration platform).

Sprint 028 ticket 006 (issue 29): the second of issue 29's two in-scope
platform adapters -- see ``adapters/DESIGN.md``'s sprint 028 section
("``activenet_camps``/``campbrain``: platform adapters sharing the LLM
family's own intermediate shape") for the full architecture write-up.
``CampBrainAdapter`` is structurally identical to ticket 005's
``ActiveNetCampsAdapter`` (itself sharing ``ProgramPageAdapter``'s
``discover()``/``fetch()`` shape): one registered ``config.url`` per
organization (the platform's per-org registration-portal root), one
``EventRef``, no probe-then-paginate step -- and differs only in
``extract()``: a deterministic JSON parse is attempted first
(:data:`CONFIDENCE_STRUCTURED_PLATFORM`, matching the Structured API
family's own confidence convention and ``activenet_camps.py``'s
identical convention); if the fetched body does not parse as
CampBrain's own session-list JSON shape, ``extract()`` falls back to
``extract.reduce_html_to_text()`` plus
``ProgramLLMClient.extract_programs()`` -- the exact same call
``program_page_multi``/``activenet_camps`` already make, via
:func:`partner_scrape.adapters.program_page._extract_many_programs`,
reused unmodified. Either path produces a
``list[ProgramExtractionResult]``, mapped onto ``Event``s via the
existing :func:`partner_scrape.adapters.program_page._map_result_to_event`
-- no new mapping code, matching this ticket's own explicit design (and
``activenet_camps.py``'s).

**Live verification (2026-09-02).** Issue 29 named CampBrain as its
second-priority platform with no further detail on its response shape
(``adapters/DESIGN.md``'s own §6 Open Question left this unconfirmed at
architecture-authoring time, same as it did for ActiveNet). Live
investigation of both named organizations' registration links --
``https://coastalrootsfarm.campbrainregistration.com/`` (Coastal Roots
Farm, per issue 29) and ``https://watersportscamp.campbrainregistration.com/``
(The Watersports Camp at Mission Bay Aquatic Center, linked from
watersportscamp.com's own "Register Now!" button) -- found a *more
restrictive* gate than ActiveNet's JS-fingerprint challenge. Both
organizations' CampBrain root serves a Vue/Vite single-page app
(BrainRunner Inc.'s ``2026.8.0.0`` build) whose default route, and
*every* other client-side route probed (``/programs``, ``/catalog``,
``/sessions``, ``/camps``, ``/register``, ``/session-select``,
``/select-camper``), renders to the identical page: a family **account
login form** (page title ``"Login | <Org Name>"``, backed by
``api.campbrainregistration.com/api/Home/LoginScreen`` plus a reCAPTCHA
challenge on submit) -- confirmed via a full headless render
(``wait_until="networkidle"`` plus a multi-second settle wait) of both
orgs' real pages, not merely the pre-render bootstrap shell a plain
``PoliteFetcher`` GET alone returns (also confirmed separately: a plain
static GET returns only a ~1KB Vite `index.html` shell with a
``<noscript>`` fallback, no session content at any layer). This
module's own fixture (see below) reproduces the captured, fully-
rendered DOM: a sign-in form and a new-account sign-up form, nothing
else. No camp name, date, price, or availability field is present
anywhere in either org's rendered DOM or in the JSON responses
(``api.campbrainregistration.com/api/Settings/SiteSettings``, ``.../
api/Home/LoginScreen``) captured during that render.

Unlike ActiveNet -- where headless rendering (once ``fetch/headless.py``'s
own wait-strategy gap is fixed, per ``helen-woodward-camps.toml``'s/
``sandiego-air-space-camps.toml``'s own comments) reaches a real,
public session list -- CampBrain's platform requires a **family user
account** (email + password, created via the same page's own "New User
Sign-Up" form) before any session data is served at all, for every
route probed. This is an authentication wall, not a bot-detection
challenge: no amount of headless-rendering improvement recovers session
data here, because the platform's own server-side authorization -- not
its client-side JavaScript -- is what withholds it. The League has no
CampBrain family account for either organization, and no institutional
API-key equivalent exists for this consumer-facing product (unlike
``leaguesync``'s/``robotevents``'s ``config.py`` accessor-pair
credential shape, which is an organization-level token, not a
per-family login) -- provisioning one is out of this ticket's scope,
per ``adapters/DESIGN.md``'s own sprint 028 note ("no credential or
API-key dependency was added ... pending each registration's own live
verification; if verification finds a required API key, that ticket
adds a ``config.py`` accessor pair ... not designed in advance of
evidence requiring it") -- a family login is a different kind of
credential than that note anticipated, and not one this pipeline should
provision on a specific family's behalf even if it could.

Both named organizations are therefore registered ``enabled = false``,
following the sprint 027 tickets 005/006 and this sprint's own ticket
005 precedent for "design against the best available evidence, register
``enabled = false`` with a documented reason" when live verification
finds a source blocked -- see ``registry/sources/watersports-camp-campbrain.toml``
for the registration and its own comment. Coastal Roots Farm's own
CampBrain-hosted registration data was evaluated as the working
alternative ``sprint.md``'s SUC-043 asks this ticket to check for its
already-registered (also-disabled) marketing page
(``coastal-roots-farm-camp.toml``, ticket 004): CampBrain is *not* a
better path for that org -- it is strictly worse, since the marketing
page's session data is at least human-legible prose the LLM currently
mis-blends, whereas CampBrain serves this pipeline literally zero
accessible fields. Coastal Roots Farm's ticket-004 marketing-page
registration is therefore left unchanged -- no ``campbrain`` entry is
added for it, avoiding the exact dual-registration risk this sprint's
own Design Rationale names for Air & Space Museum/Helen Woodward.

**Design note: the deterministic-JSON path is unconfirmed, by
necessity.** :func:`_try_parse_campbrain_sessions_json` mirrors
``activenet_camps._try_parse_activenet_sessions_json``'s shape (a dict
with a list-valued ``"sessions"`` key) for adapter-contract consistency
and future-proofing -- a future authenticated integration, or a
CampBrain-hosted organization whose registration portal turns out to
expose a public catalog, could exercise it with zero further adapter
code. Unlike ActiveNet's deterministic-JSON shape (captured live from a
real, if not-yet-reachable-via-this-project's-fetcher, endpoint), this
shape is **not** confirmed against any real CampBrain response --
live verification found no reachable endpoint to capture one from (see
above). It is deliberately kept structurally parallel to
``activenet_camps.py``'s own confirmed shape (same field names read:
``name``, start/end dates, a ``tuitions``-style price list,
``availableQuantity``) as the most defensible placeholder absent any
real evidence either way, documented here as speculative rather than
silently presented as verified.
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
#: entry for it, and ``activenet_camps.CONFIDENCE_STRUCTURED_PLATFORM``'s
#: identical constant). Not currently threaded through ``Event.set()`` --
#: see this module's docstring's Design note and
#: ``activenet_camps.py``'s own identical "reusing
#: ``_map_result_to_event`` unmodified" note for why: every mapped field
#: is recorded at ``program_llm.PROGRAM_LLM_CONFIDENCE`` (0.9) regardless
#: of which extraction path produced it.
CONFIDENCE_STRUCTURED_PLATFORM = 1.0


def _campbrain_date_to_iso(value: Any) -> str:
    """Convert one CampBrain structured date object (``{"year": 2026,
    "month": 10, "day": 26, ...}``) to an ISO ``YYYY-MM-DD`` string.

    Mirrors ``activenet_camps._activenet_date_to_iso`` exactly -- see
    that function's docstring. Returns ``""`` (matching
    ``ProgramExtractionResult``'s own "not stated" convention) for
    anything that isn't a dict with the three required integer keys --
    logged, never raised, so one malformed date on an otherwise-good
    session never drops the whole page's other sessions.
    """
    if not isinstance(value, dict):
        return ""
    try:
        year, month, day = int(value["year"]), int(value["month"]), int(value["day"])
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (KeyError, TypeError, ValueError):
        logger.warning("CampBrain session date %r is not a well-formed date object; leaving unset", value)
        return ""


def _campbrain_session_cost(session: dict[str, Any]) -> str:
    """Return a short cost string from a session's first ``tuitions``
    entry's price, or ``""`` if the session carries no tuition/price at
    all -- matching ``ProgramExtractionResult.cost``'s own "not stated"
    convention and ``activenet_camps._activenet_session_cost``'s
    identical shape.
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


def _campbrain_session_is_open(session: dict[str, Any]) -> bool:
    """Return whether a session still has open capacity.

    Mirrors ``activenet_camps._activenet_session_is_open``: only a
    non-negative, finite-looking zero or below is treated as sold out; a
    missing/non-numeric value defaults to ``True`` (open), matching
    ``ProgramExtractionResult.is_open``'s own documented default for "no
    clear signal either way."
    """
    available = session.get("availableQuantity")
    if isinstance(available, (int, float)):
        return available > 0
    return True


def _try_parse_campbrain_sessions_json(body: str) -> list[ProgramExtractionResult] | None:
    """Attempt a deterministic parse of ``body`` as a CampBrain
    ``{"count": ..., "sessions": [...]}`` JSON shape.

    See this module's docstring's Design note: this shape is not
    confirmed against any real CampBrain response (live verification
    found every route authentication-gated, with no reachable endpoint
    to capture a payload from) -- it exists for adapter-contract
    consistency and future-proofing, structurally parallel to
    ``activenet_camps._try_parse_activenet_sessions_json``'s confirmed
    shape.

    Returns ``None`` -- never raises -- for anything that isn't valid
    JSON, or is valid JSON but not this shape (a dict with a
    list-valued ``"sessions"`` key), so :meth:`CampBrainAdapter.extract`
    can fall back to the LLM-extraction path unconditionally. One
    malformed session dict inside an otherwise-good list is skipped
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
            logger.warning("CampBrain session entry missing a name; skipping: %r", session)
            continue
        results.append(
            ProgramExtractionResult(
                program_name=session["name"],
                date_start=_campbrain_date_to_iso(session.get("startDate")),
                date_end=_campbrain_date_to_iso(session.get("endDate")),
                cost=_campbrain_session_cost(session),
                is_open=_campbrain_session_is_open(session),
                opportunity_type="Camps",
            )
        )
    return results


class CampBrainAdapter:
    """``Adapter`` for one organization's CampBrain registration-portal
    endpoint (``campbrain``).

    Same constructor-injection deviation as the ``program_page`` family
    and ``activenet_camps`` (``adapters/DESIGN.md``'s §3) -- the
    deterministic-parse path needs no LLM client at all, but the
    constructor shape stays uniform across the whole LLM-extraction/
    camp-platform family so a source can be registered either way with
    no adapter-selection logic anywhere else.
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
        CampBrain registration-portal URL.

        Identical to ``ActiveNetCampsAdapter.discover()``/
        ``ProgramPageAdapter.discover()`` -- a ``campbrain`` source is
        always one fixed per-organization URL, no probe-then-paginate
        step.

        Raises:
            KeyError: ``source.config`` has no ``url`` key.
        """
        return [EventRef(url=source.config["url"])]

    def fetch(self, ref: EventRef, fetcher: Fetcher, source: SourceConfig) -> RawResponse:
        """Standard single-page GET, matching every other adapter's
        ``fetch()``.

        The injected ``fetcher`` is whichever ``Fetcher``
        ``pipeline.run()`` chose for this source -- every currently
        registered ``campbrain`` source sets ``fetch_strategy =
        "headless"`` (``campbrainregistration.com`` is a client-side SPA;
        a plain static GET returns only the pre-render bootstrap shell,
        see this module's docstring), even though live verification
        found headless rendering alone does not clear this platform's
        authentication wall. This adapter itself has no opinion about
        which ``Fetcher`` it is given -- it never constructs one, per
        ``adapters/DESIGN.md``'s §3 invariant.
        """
        response = fetcher.get(ref.url, **acquisition_kwargs(source))
        return RawResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawResponse, source: SourceConfig) -> Iterable[Event]:
        """Map one fetched CampBrain registration-portal response into
        zero or more canonical ``Event``s.

        A non-200 fetch is logged and skipped (``[]``), matching every
        other adapter's convention. Otherwise, ``raw.body`` is first
        tried as CampBrain's own sessions-list JSON shape
        (:func:`_try_parse_campbrain_sessions_json`); on a match, each
        session is mapped directly via
        ``program_page._map_result_to_event`` with no cache lookup and
        no LLM call. Otherwise ``extract()`` falls back to
        :func:`partner_scrape.adapters.program_page._extract_many_programs`
        unmodified -- the exact same reduce-then-cache-then-LLM-call
        logic ``program_page_multi``/``activenet_camps`` already use,
        including its own non-200 handling (redundant with the check
        above, but keeps this function's own status check symmetric with
        every other adapter's ``extract()``), per-ref LLM-exception
        isolation, and ``config.program_kind`` gating. In practice,
        every currently-registered ``campbrain`` source's real fetched
        body is an authentication-gated login page (see this module's
        docstring's Live Verification note), so this path correctly
        yields zero ``Event``s rather than an error or a hallucinated
        session -- proven by this module's own LLM-fallback test fixture.
        """
        if raw.status != 200:
            logger.warning(
                "CampBrain fetch %s returned status %s; skipping",
                raw.ref.url,
                raw.status,
            )
            return []

        results = _try_parse_campbrain_sessions_json(raw.body)
        if results is not None:
            program_kind = _resolve_program_kind(raw.ref.url, source)
            if program_kind is None:
                return []
            return [
                _map_result_to_event(result, source, program_kind, raw.ref.url) for result in results
            ]

        return _extract_many_programs(raw, source, self.llm_client, self.cache)
