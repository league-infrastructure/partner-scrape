"""FTCScout REST source (``teams.sources.ftcscout``).

FTCScout (``api.ftcscout.org``) is a free, unauthenticated, third-party
FTC statistics API. Its REST search endpoint,
``GET /rest/v1/teams/search?region=<code>``, returns every team
FTCScout has on file for a region as a flat JSON array -- confirmed
live (2026-08-27) that ``region=USCASD`` returns exactly 152 San Diego
FTC teams, matching the issue's measured count
(``clasi/issues/robot-teams-scrape-locate-and-publish-san-diego-first-
teams.md``).

**REST, not GraphQL.** FTCScout also exposes a GraphQL endpoint with
richer querying, but this source deliberately uses the REST search
endpoint instead: ``fetch.Fetcher`` (``fetch/fetcher.py``) is GET-only,
and adding a ``post()`` method to support GraphQL would ripple into
every ``FixtureFetcher`` test double in the whole suite for this one
source's benefit.

**No website data.** FTCScout's ``website`` field exists on every
record but was measured null for all 152 San Diego teams (and 0 of
3,412 nationally, across nine regions checked). This source therefore
never sets ``Team.website`` -- there is nothing to set it from. Ticket
011-003's TBA source is the first real populator (measured 72% website
coverage).

``tests/fixtures/teams/ftcscout_search.json`` is a real, live-captured
response (2026-08-27) -- all 152 records, unmodified beyond JSON
pretty-printing -- so field-mapping tests exercise the real API shape,
not a synthetic approximation.
``tests/fixtures/teams/ftcscout_search_malformed.json`` is hand-authored
(the real feed has no malformed records) to exercise per-record error
isolation, matching ``adapters/tec.py``'s and ``adapters/leaguesync.py``'s
test convention.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from partner_scrape.fetch import Fetcher
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef

logger = logging.getLogger(__name__)

#: This source's provenance name, recorded on every Team it produces
#: (``Team.sources``).
SOURCE_NAME = "ftcscout"

#: Short league code and human-readable program name -- see
#: ``teams/model.py``'s ``League``/``Team.program`` docstrings.
LEAGUE = "FTC"
PROGRAM = "FIRST Tech Challenge"

#: Defaults, overridable per-source via ``SourceConfig.config`` (see
#: ``registry/ftc-sd.toml``) -- matching ``adapters/leaguesync.py``'s
#: ``config.get("api_base") or <default>`` fallback convention.
DEFAULT_API_BASE = "https://api.ftcscout.org"
DEFAULT_REGION = "USCASD"

#: The sentinel FTCScout's ``schoolName`` field uses for a team with no
#: sponsoring school -- a "home team" fielded by a family or community
#: group. Measured live: 58 of 152 San Diego FTC teams (38%).
FAMILY_COMMUNITY = "Family/Community"

#: Cities confirmed, by live measurement (2026-08-27, the issue's own
#: capture), to fall outside San Diego County among the
#: ``region=USCASD`` result set -- FTCScout's region filter is a loose
#: geographic box, not a strict county boundary. 6 of 152 teams: two in
#: Ensenada (Mexico, just south of the border), one each in San
#: Clemente and Agoura Hills (further up the CA coast), and one each in
#: Louisville and San Antonio (out of state -- likely a relocated team
#: or a data-entry quirk on FTCScout's side).
#:
#: A denylist, not an allowlist, deliberately: an unrecognized new city
#: name defaults to ``in_region=True``. That is the safer failure mode
#: -- a real San Diego community not yet seen in this measurement
#: should never be silently flagged out-of-region because it's missing
#: from a hand-maintained list. Per the issue's "never drop" rule, an
#: out-of-region team is flagged (``Team.in_region = False``), not
#: excluded (see ``_extract_one`` below).
OUT_OF_REGION_CITIES = frozenset(
    {
        "Ensenada",
        "San Clemente",
        "San Antonio",
        "Louisville",
        "Agoura Hills",
    }
)


def _search_url(api_base: str, region: str) -> str:
    return f"{api_base.rstrip('/')}/rest/v1/teams/search?region={region}"


def _clean_city(raw: str | None) -> str:
    """Normalize a raw FTCScout ``city`` string.

    Measured live: 27 distinct raw city strings for what is really only
    24 distinct places -- trailing whitespace (``"La Jolla "``) and
    inconsistent casing (``"carlsbad"`` vs ``"Carlsbad"``, ``"san
    diego"`` vs ``"San Diego"``) duplicate a place FTCScout already
    reports correctly elsewhere in the same response. Stripping and
    title-casing collapses every dirty variant actually observed onto
    its clean counterpart without a lookup table -- good enough for
    this ticket's "city-level data at minimum"; ticket 011-004's
    ``teams/geo.py`` does the real place-name matching against CDE/NCES
    school directories.
    """
    if not raw:
        return ""
    return raw.strip().title()


def _extract_one(record: dict[str, Any]) -> Team:
    """Map one FTCScout search-result record into a ``Team``.

    Raises:
        ValueError: the record has no usable ``number`` or ``name`` --
            left uncaught here so the caller (``extract()``) can
            isolate it as a whole-record failure, matching every other
            structured source's convention (see
            ``adapters/leaguesync.py``'s ``_extract_class``).
    """
    number = record.get("number")
    name = (record.get("name") or "").strip()
    if not isinstance(number, int) or not name:
        raise ValueError("FTCScout team record has no usable number or name")

    school_name = (record.get("schoolName") or "").strip()
    if school_name and school_name != FAMILY_COMMUNITY:
        organization = school_name
        org_type = "school"
    elif school_name == FAMILY_COMMUNITY:
        organization = ""
        org_type = "family_community"
    else:
        organization = ""
        org_type = "unknown"

    city = _clean_city(record.get("city"))
    # Out-of-region is flagged, never dropped -- see
    # OUT_OF_REGION_CITIES's docstring. A team with no city at all
    # (not observed live, but the field's presence isn't guaranteed by
    # the API contract) is treated as in-region rather than penalized
    # for missing data teams/geo.py hasn't had a chance to resolve yet.
    in_region = city not in OUT_OF_REGION_CITIES

    sponsors_raw = record.get("sponsors")
    sponsors = list(sponsors_raw) if isinstance(sponsors_raw, list) else []
    # Sprint 013 ticket 005: every sponsor this structured API reports
    # carries "structured" provenance from the moment it is created --
    # not backfilled later -- so `teams.sponsor_extract.extract_sponsors()`
    # can tell a pre-existing structured claim from a scraped one when it
    # merges the two (`sponsor_provenance[name]`'s dedup contract).
    sponsor_provenance = {name: "structured" for name in sponsors}

    rookie_year = record.get("rookieYear")

    return Team(
        team_id=f"{LEAGUE.lower()}-{number}",
        league=LEAGUE,
        program=PROGRAM,
        number=number,
        name=name,
        organization=organization,
        org_type=org_type,
        city=city,
        rookie_year=rookie_year if isinstance(rookie_year, int) else None,
        sponsors=sponsors,
        sponsor_provenance=sponsor_provenance,
        sources=[SOURCE_NAME],
        in_region=in_region,
    )


class FTCScoutSource:
    """``TeamSource`` for FTCScout's free, unauthenticated REST search endpoint."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[TeamRef]:
        """Return exactly one ``TeamRef`` -- the region search request.

        No probing needed: unlike TEC/Localist's paginated REST APIs,
        FTCScout's search endpoint returns every matching team in one
        response (confirmed live: 152 objects, no pagination
        parameters in the response or the documented contract).
        """
        api_base = source.config.get("api_base") or DEFAULT_API_BASE
        region = source.config.get("region") or DEFAULT_REGION
        return [TeamRef(url=_search_url(api_base, region))]

    def fetch(self, ref: TeamRef, fetcher: Fetcher) -> RawTeamResponse:
        response = fetcher.get(ref.url)
        return RawTeamResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawTeamResponse, source: SourceConfig) -> Iterable[Team]:
        if raw.status != 200:
            logger.warning(
                "FTCScout search %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            records = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning(
                "FTCScout search %s returned unparseable JSON; skipping", raw.ref.url
            )
            return []

        if not isinstance(records, list):
            logger.warning(
                "FTCScout search %s returned an unexpected JSON shape; skipping", raw.ref.url
            )
            return []

        teams: list[Team] = []
        for record in records:
            try:
                teams.append(_extract_one(record))
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed FTCScout team record on %s: %s", raw.ref.url, exc
                )
        return teams
