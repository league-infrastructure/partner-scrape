"""The Blue Alliance v3 source (``teams.sources.tba``).

The Blue Alliance (``www.thebluealliance.com/api/v3``) is a keyed,
third-party FRC statistics API -- richer than FTCScout but global in
scope: its ``/api/v3/teams/{page_num}`` endpoint enumerates *every*
FRC team on file, worldwide, ~500 per page, with no region-filtered
search endpoint the way FTCScout has. Confirmed live: ``GET
/api/v3/status`` reports ``max_team_page`` (23 at time of measurement)
for callers to enumerate every page; the full roster is ~9,163 teams,
496 of them in California, of which **59** are in San Diego County
cities (:data:`SD_COUNTY_CITIES`) -- this source's whole job is
fetching every page and filtering down to that 59.

**Auth.** Every request (including the ``/status`` probe) requires the
``X-TBA-Auth-Key`` header (401 without it) -- see
``config.get_tba_api_key()``. Read fresh on every call via
``_auth_headers()``, never cached on the source instance, matching
``adapters/leaguesync.py::_auth_headers``'s pattern exactly (source
instances are constructed fresh per run -- see ``sources/base.py``'s
``TeamSource`` docstring).

**``discover()`` fails loudly; it does not degrade gracefully.**
Unlike ``adapters/tec.py``'s pagination probe (which falls back to
"assume 1 page" on a bad probe response), a failed ``/status`` probe
here -- a missing/invalid ``TBA_KEY``, a non-200 status, or an
unparseable body -- raises. There is no sane page-count fallback for a
credential failure: guessing a page count would still 401 on every
subsequent fetch, just less honestly. Raising here is exactly what
lets ``teams.pipeline.run_teams()``'s existing per-source
try/except (ticket 011-002) isolate it -- log, skip this source,
continue with whatever FTCScout already contributed -- with **no
special-casing for TBA** in ``pipeline.py`` beyond registering this
source. This is the mechanism sprint.md's Migration Concerns and this
ticket's acceptance criteria call "isolated the way ``pipeline.run()``
isolates any source failure": a missing/401 ``TBA_KEY`` degrades a
``teams`` run to FTC-only output, never aborts it.

**TBA is not a geocoding source.** ``lat``/``lng``/``address``/
``location_name``/``gmaps_place_id`` are documented in TBA's own
OpenAPI spec as "Will be NULL, for future development" -- confirmed
NULL for all 59 San Diego teams. This source therefore never reads
those fields at all (not even to check they're null) -- ``Team.
latitude``/``Team.longitude`` are left at their dataclass defaults
(``None``) here; ``teams/geo.py`` (ticket 011-004) is the only stage
that ever sets them.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from partner_scrape import config
from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef

logger = logging.getLogger(__name__)

#: This source's provenance name, recorded on every Team it produces
#: (``Team.sources``).
SOURCE_NAME = "tba"

#: Short league code and human-readable program name -- see
#: ``teams/model.py``'s ``League``/``Team.program`` docstrings.
LEAGUE = "FRC"
PROGRAM = "FIRST Robotics Competition"

#: Note, unlike ``sources/ftcscout.py``'s ``DEFAULT_API_BASE`` module
#: constant: this source's ``api_base`` default is
#: ``config.get_tba_url()``, not a bare literal here -- see
#: ``discover()`` below. That way the same ``TBA_URL`` override that
#: redirects every other TBA call also redirects this source with no
#: registry-file edit needed.

#: San Diego County cities/communities this source filters TBA's
#: global roster down to. Sourced from the project's own historical
#: FRC roster (``data/robot-teams.json``, 44 real San Diego FRC teams
#: spanning incorporated cities and unincorporated/neighborhood names
#: school directories report, e.g. "Carmel Valley", "Rancho
#: Bernardo") plus every incorporated city in San Diego County. Unlike
#: ``sources/ftcscout.py``'s ``OUT_OF_REGION_CITIES`` (a denylist,
#: because FTCScout's ``region=USCASD`` search already pre-filters to
#: a rough geographic box), this **must** be an allowlist: TBA's
#: ``/api/v3/teams/{page}`` enumerates the entire global roster with
#: no region parameter at all, so an unrecognized city is excluded,
#: not defaulted in. A real San Diego city missing from this list is a
#: silent undercount -- ``meta.by_league`` in the exported
#: ``teams.json`` (``teams/export.py``) makes that undercount visible
#: as a lower-than-expected FRC total, and this list is the first
#: place to check when it drifts from the measured 59.
SD_COUNTY_CITIES = frozenset(
    {
        "San Diego",
        "Chula Vista",
        "Oceanside",
        "Escondido",
        "Carlsbad",
        "El Cajon",
        "Vista",
        "San Marcos",
        "Encinitas",
        "National City",
        "La Mesa",
        "Santee",
        "Poway",
        "Coronado",
        "Imperial Beach",
        "Lemon Grove",
        "Solana Beach",
        "Del Mar",
        "Fallbrook",
        "Bonita",
        "Ramona",
        "Alpine",
        "Spring Valley",
        "Rancho Santa Fe",
        "La Jolla",
        "Rancho Bernardo",
        "Rancho Penasquitos",
        "Jamul",
        "Lakeside",
        "Valley Center",
        "Julian",
        "Borrego Springs",
        "Pauma Valley",
        "Bonsall",
        "Carmel Valley",
        "Pacific Highlands Ranch",
        "Torrey Hills",
        "Santaluz",
        "Descanso",
        "Pine Valley",
        "Potrero",
        "Campo",
        "Boulevard",
        "Jacumba",
        "Warner Springs",
        "Pala",
        "Palomar Mountain",
    }
)


def _status_url(api_base: str) -> str:
    return f"{api_base.rstrip('/')}/api/v3/status"


def _teams_page_url(api_base: str, page: int) -> str:
    return f"{api_base.rstrip('/')}/api/v3/teams/{page}"


def _auth_headers() -> dict[str, str]:
    """Build the ``X-TBA-Auth-Key`` header The Blue Alliance requires.

    Reads the key fresh on every call via ``config.get_tba_api_key()``
    rather than caching it on the source instance -- source instances
    are constructed fresh per ``sources.base.run()`` call, matching
    ``adapters/leaguesync.py``'s ``_auth_headers()`` docstring ("no
    adapter-instance state to inject into"). Raises ``RuntimeError``
    (uncaught here) when ``TBA_KEY`` is unset -- see this module's own
    docstring for why that propagates all the way to
    ``teams.pipeline.run_teams()``'s per-source isolation rather than
    being caught locally.
    """
    return {"X-TBA-Auth-Key": config.get_tba_api_key()}


def _clean_city(raw: str | None) -> str:
    """Normalize a raw TBA ``city`` string for the :data:`SD_COUNTY_CITIES`
    lookup -- strip and title-case, matching ``sources/ftcscout.py``'s
    ``_clean_city`` so both sources treat a place name identically."""
    if not raw:
        return ""
    return raw.strip().title()


def _extract_one(record: dict[str, Any]) -> Team | None:
    """Map one TBA team record into a ``Team``, or ``None`` if it falls
    outside California + San Diego County (filtered, not an error).

    Raises:
        ValueError: the record has no usable ``team_number`` -- left
            uncaught here so the caller (``extract()``) can isolate it
            as a whole-record failure, matching every other structured
            source's convention.
    """
    number = record.get("team_number")
    if not isinstance(number, int):
        raise ValueError("TBA team record has no usable team_number")

    state_prov = (record.get("state_prov") or "").strip()
    city = _clean_city(record.get("city"))
    if state_prov != "CA" or city not in SD_COUNTY_CITIES:
        return None

    nickname = (record.get("nickname") or "").strip()
    name = nickname or (record.get("name") or "").strip()

    school_name = (record.get("school_name") or "").strip()
    if school_name:
        organization = school_name
        org_type = "school"
    else:
        organization = ""
        org_type = "unknown"

    website = (record.get("website") or "").strip()
    postal_code = (record.get("postal_code") or "").strip()

    rookie_year = record.get("rookie_year")

    return Team(
        team_id=f"{LEAGUE.lower()}-{number}",
        league=LEAGUE,
        program=PROGRAM,
        number=number,
        name=name,
        organization=organization,
        org_type=org_type,
        city=city,
        postal_code=postal_code,
        website=website,
        rookie_year=rookie_year if isinstance(rookie_year, int) else None,
        sources=[SOURCE_NAME],
    )


class TBASource:
    """``TeamSource`` for The Blue Alliance's keyed v3 API."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[TeamRef]:
        """Probe ``/api/v3/status`` for ``max_team_page``, then return
        one ``TeamRef`` per page (``0..max_team_page`` inclusive).

        Raises ``RuntimeError`` -- deliberately, not caught here -- on
        a missing/invalid credential, a non-200 probe response, an
        unparseable body, or a missing/invalid ``max_team_page``. See
        this module's docstring for why raising (not degrading) is the
        right contract for TBA specifically.
        """
        api_base = source.config.get("api_base") or config.get_tba_url()
        status_url = _status_url(api_base)
        response = fetcher.get(status_url, headers=_auth_headers())

        if response.status == 401:
            raise RuntimeError(
                f"TBA auth failed (401) for {status_url}; check TBA_KEY"
            )
        if response.status != 200:
            raise RuntimeError(
                f"TBA status probe {status_url} returned status {response.status}"
            )

        try:
            data = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"TBA status probe {status_url} returned unparseable JSON"
            ) from exc

        max_team_page = data.get("max_team_page") if isinstance(data, dict) else None
        if not isinstance(max_team_page, int) or max_team_page < 0:
            raise RuntimeError(
                f"TBA status probe {status_url} returned an invalid "
                f"max_team_page: {max_team_page!r}"
            )

        return [
            TeamRef(url=_teams_page_url(api_base, page))
            for page in range(max_team_page + 1)
        ]

    def fetch(self, ref: TeamRef, fetcher: Fetcher) -> RawTeamResponse:
        response = fetcher.get(ref.url, headers=_auth_headers())
        return RawTeamResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawTeamResponse, source: SourceConfig) -> Iterable[Team]:
        if raw.status != 200:
            logger.warning(
                "TBA teams page %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            records = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning(
                "TBA teams page %s returned unparseable JSON; skipping", raw.ref.url
            )
            return []

        if not isinstance(records, list):
            logger.warning(
                "TBA teams page %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        teams: list[Team] = []
        for record in records:
            try:
                team = _extract_one(record)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed TBA team record on %s: %s", raw.ref.url, exc
                )
                continue
            if team is not None:
                teams.append(team)
        return teams
