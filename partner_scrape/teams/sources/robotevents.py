"""RobotEvents API v2 VEX source (``teams.sources.robotevents``).

VEX Robotics Competition (CA Region 4: San Diego/Imperial -- V5RC + VIQRC,
roughly a dozen local tournaments per season plus two ~96-team regional
championships) is entirely absent from the teams pipeline before this
ticket -- FIRST (FTC/FRC/FLL) is the only league either pipeline has ever
ingested. This source pulls VEX team rosters from the same RobotEvents API
v2 sprint 016 ticket 004 already plumbed config access for
(``config.get_robotevents_api_key()``/``get_robotevents_url()``).

**No shared code with ``adapters/robotevents.py``.** That module (the
Opportunity-pipeline events adapter, ticket 004) and this one both call the
same external API with the same bearer token, but share only
``config.py``'s accessor -- matching ``teams/DESIGN.md``'s explicit
precedent ("Why FTCScout/TBA share no extraction code beyond the
``TeamSource`` protocol shape") and this sprint's own Design Rationale for
the same choice. See that module's own docstring for the ``/events``
request/response shape this one's sibling ``/teams`` shape below is
confirmed the same way.

**Endpoint shape, confirmed against RobotEvents' own published OpenAPI
schema, not a live authenticated probe.** No ``ROBOTEVENTS_KEY`` was
available during this ticket's execution either (see ticket 004's own
Notes -- no RobotEvents account exists for this project yet), so, exactly
matching ticket 004's sourcing method, the exact ``/teams`` shape below is
taken from the actively-maintained, open-source ``robotevents`` npm client
(https://github.com/brenapp/robotevents), whose TypeScript types are
generated directly from RobotEvents' own OpenAPI spec (fetched directly
from GitHub during this ticket's execution, not from memory):

- ``GET {base}/teams`` takes ``id[]`` (int, repeatable), ``number[]``
  (str, repeatable), ``event[]`` (int, repeatable -- filter by events a
  team has attended), ``registered`` (bool), ``program[]`` (int,
  repeatable -- program IDs), ``grade[]`` (``"College"``/``"High
  School"``/``"Middle School"``/``"Elementary School"``), ``country[]``
  (str, repeatable). **Confirmed there is no city- or region-scoped
  query parameter on this endpoint at all** -- unlike ``/events``'
  ``region`` filter (ticket 004's adapter), or FTCScout's
  ``region=USCASD`` search. This is structurally the same situation
  ``sources/tba.py`` is already in (TBA's ``/api/v3/teams/{page}``
  enumerates its *entire* global roster with no region parameter either)
  -- not FTCScout's, whose region-scoped search only needs a residual
  denylist for stragglers. See ``discover()``/``extract()`` below and
  :data:`SD_COUNTY_CITIES` for how this source follows TBA's precedent,
  not FTCScout's, for the same underlying reason.
- The response envelope is ``{"meta": {...page fields, including
  "last_page"...}, "data": [...]}`` -- the same ``PaginatedTeam`` shape
  ``adapters/robotevents.py``'s ``PaginatedEvent`` already documents,
  confirmed identical for teams in the same generated schema file
  (``components.schemas.PaginatedTeam``).
- Each ``data[]`` element (``components.schemas.Team``) carries ``id``
  (int), **``number`` (already a ``str``** in RobotEvents' own schema,
  e.g. ``"90210A"`` -- this is *why* this ticket widens
  ``teams/model.py``'s ``Team.number`` to ``str``, not an artifact of
  this adapter's own choice), ``team_name``, ``robot_name``,
  ``organization`` (a plain string, no ``"Family/Community"``-style
  sentinel the way FTCScout's ``schoolName`` has -- an unaffiliated team
  simply reports an empty string, mapped the same way ``sources/tba.py``
  already maps its own no-sentinel case), ``location`` (the identical
  ``{venue, address_1, address_2, city, region, postcode, country,
  coordinates}`` shape ``adapters/robotevents.py``'s own
  ``_extract_location`` already documents for events), ``registered``,
  ``program`` (``{id, name, code}``, the same ``IdInfo`` shape as
  events' ``program`` field), ``grade``.
- Auth: ``Authorization: Bearer <token>`` (see
  ``config.get_robotevents_api_key()``), identical to
  ``adapters/robotevents.py``/``teams/sources/tba.py``.

**``program`` distinguishes V5RC vs. VIQRC per record without this module
inventing a code-to-label mapping.** RobotEvents hosts several VEX-family
programs on one platform (V5RC, VIQRC, VEX U, ADC, ...); a San Diego
County VEX team's own ``program.name`` field (e.g. ``"VEX Robotics
Competition"`` vs. ``"VEX IQ Challenge"``) already says which program it
competes in, verbatim -- this source stores that string directly into
``Team.program``, per record, exactly like ``adapters/robotevents.py``
already does for ``Event.categories`` (Design Rationale: "``program.name``
... program name, verbatim, not this adapter's own scoping"). Guessing at
RobotEvents' internal numeric ``program.id``/``program.code`` values (to
build a ``V5RC``/``VIQRC`` constant table the way ``sources/ftcscout.py``'s
``PROGRAM`` module constant works for one single-program source) was
considered and rejected -- unlike FTCScout/TBA (one program each, so one
constant each), this source's whole point is two programs on one
platform, and no token was available to confirm real ``program.id``/
``program.code`` values live. ``Team.league`` stays the single value
``"VEX"`` for every record this source produces -- the sprint's Design
Rationale widens ``League`` by exactly one new value, not two
(``model.py``'s own docstring).

**Region scoping: a client-side San Diego County allowlist, matching
``sources/tba.py``'s exact precedent, not FTCScout's denylist.**
Confirmed against the schema above: ``/teams`` has no city/region query
parameter, only ``country[]`` -- the same "global roster, no region
filter" situation ``sources/tba.py``'s own module docstring documents for
``/api/v3/teams/{page}``, and for the identical reason that module's
docstring gives (``teams/DESIGN.md``'s Constraints: "TBA's ... has no
region parameter at all ... so ``sources/tba.py`` must actively select
[San Diego County teams], both by ... and by city matching this
allowlist"). :data:`SD_COUNTY_CITIES` below duplicates ``sources/tba.py``'s
own allowlist content (same real San Diego County place names) rather than
importing it -- matching ``teams/DESIGN.md``'s "no shared extraction code"
precedent between sources -- and this source deliberately does *not*
additionally normalize/check ``location.region`` (TBA's ``_normalize_state``
table) the way TBA does: TBA needed that because a same-named city collision
outside California is a real, measured risk on TBA's roster
(``tests/teams/test_sources_tba.py``'s "San Diego, Texas" fixture record);
no such collision has been measured for RobotEvents (no token available this
ticket to measure one), so adding a ~50-entry state-name-normalization table
on pure speculation would be exactly the "speculative generality with no
second evidenced case" sprint.md's own Design Rationale (the ``ical.py``
TTL fix) explicitly rejects elsewhere in this same sprint. A future ticket
with live data showing a real false-positive city-name collision is the
right trigger for adding that check here, not this one.

An operator-configurable ``country`` value (``source.config["country"]``,
a single free string sent as one ``country[]`` query value) is supported,
unset by default, mirroring ``adapters/robotevents.py``'s own
``season_ids``/``region`` optional-narrowing-knob convention exactly: this
source is correct (if broad -- pagination spans RobotEvents' entire global
roster) with no configuration, and an operator can narrow the real query
once a live token confirms the right value, without a code change.

**``discover()`` raises on any probe failure; it does not degrade
gracefully the way ``adapters/robotevents.py``'s own ``/events`` probe
does (assume 1 page on a non-401 failure).** This ticket's own acceptance
criteria call for "matching ``sources/tba.py``'s exact isolation
contract," not ``adapters/robotevents.py``'s -- see that module's
docstring for the full rationale (no sane page-count fallback for a
credential failure; raising here is exactly what lets
``teams.pipeline.run_teams()``'s existing per-source ``try``/``except``
isolate it, degrading a ``teams`` run to non-VEX-only output, never
aborting it).

Sprint 023 ticket 001: a missing ``ROBOTEVENTS_KEY``
(``config.get_robotevents_api_key()``) and a live 401 from the
``/teams`` probe below both now raise ``config.CredentialError``
specifically (not a bare ``RuntimeError``), mirroring
``sources/tba.py``'s identical treatment -- see that class's own
docstring for why. Every other probe failure (non-200 non-401,
unparseable JSON, an invalid ``meta.last_page``) still raises plain
``RuntimeError``, unchanged.
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
SOURCE_NAME = "robotevents"

#: Short league code -- see ``teams/model.py``'s ``League`` docstring.
#: Unlike FTCScout/TBA (one ``PROGRAM`` module constant each), this
#: source's ``Team.program`` varies per record (V5RC vs. VIQRC) -- see
#: this module's own docstring.
LEAGUE = "VEX"

#: Default page size for the paginated ``/teams`` request. Matches
#: ``adapters/robotevents.py``'s own ``DEFAULT_PER_PAGE`` magnitude --
#: no live token was available to confirm RobotEvents' real page-size
#: cap for either endpoint.
DEFAULT_PER_PAGE = 50

#: San Diego County cities/communities this source filters RobotEvents'
#: global VEX roster down to. **Deliberately duplicates
#: ``sources/tba.py``'s ``SD_COUNTY_CITIES`` content**, not imported --
#: see this module's own docstring ("Region scoping") for why: the two
#: sources are independently-changing modules by this project's own
#: "no shared extraction code beyond the TeamSource protocol shape"
#: precedent, even though the underlying real-world place list they
#: both need happens to be the same San Diego County geography.
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


def _teams_url(api_base: str, country: str, page: int, per_page: int) -> str:
    query = [f"page={page}", f"per_page={per_page}"]
    if country:
        query.append(f"country[]={country}")
    return f"{api_base.rstrip('/')}/teams?{'&'.join(query)}"


def _auth_headers() -> dict[str, str]:
    """Build the Bearer-auth header RobotEvents API v2 requires.

    Reads the token fresh on every call via
    ``config.get_robotevents_api_key()`` rather than caching it on the
    source instance -- source instances are constructed fresh per
    ``sources.base.run()`` call, matching ``sources/tba.py``'s and
    ``adapters/robotevents.py``'s ``_auth_headers()`` exactly. Raises
    ``config.CredentialError`` (uncaught here) when ``ROBOTEVENTS_KEY``
    is unset -- this is deliberate: it is the "config-read failure"
    ``teams.pipeline.run_teams()``'s existing per-source isolation must
    catch, matching ``sources/tba.py``'s documented rationale for why
    this propagates rather than being caught locally.
    """
    return {"Authorization": f"Bearer {config.get_robotevents_api_key()}"}


def _clean_city(raw: str | None) -> str:
    """Normalize a raw RobotEvents ``location.city`` string for the
    :data:`SD_COUNTY_CITIES` lookup -- strip and title-case, matching
    ``sources/ftcscout.py``'s and ``sources/tba.py``'s ``_clean_city`` so
    every source treats a place name identically."""
    if not raw:
        return ""
    return raw.strip().title()


def _extract_one(record: dict[str, Any]) -> Team | None:
    """Map one RobotEvents ``/teams`` record into a ``Team``, or ``None``
    if it falls outside San Diego County (filtered, not an error) --
    mirroring ``sources/tba.py``'s ``_extract_one`` contract exactly.

    Raises:
        ValueError: the record has no usable ``number``/``team_name`` --
            left uncaught here so the caller (``extract()``) can isolate
            it as a whole-record failure, matching every other structured
            source's convention.
    """
    number = (record.get("number") or "").strip()
    name = (record.get("team_name") or "").strip()
    if not number or not name:
        raise ValueError("RobotEvents team record has no usable number or team_name")

    location = record.get("location")
    if not isinstance(location, dict):
        location = {}
    city = _clean_city(location.get("city"))
    if city not in SD_COUNTY_CITIES:
        return None

    program = record.get("program")
    if not isinstance(program, dict):
        program = {}
    program_name = (program.get("name") or "").strip()

    organization = (record.get("organization") or "").strip()
    org_type = "school" if organization else "unknown"

    postal_code = (location.get("postcode") or "").strip()

    return Team(
        team_id=f"{LEAGUE.lower()}-{number}",
        league=LEAGUE,
        program=program_name,
        number=number,
        name=name,
        organization=organization,
        org_type=org_type,
        city=city,
        postal_code=postal_code,
        sources=[SOURCE_NAME],
    )


class VexTeamSource:
    """``TeamSource`` for RobotEvents API v2's keyed ``/teams`` endpoint."""

    def discover(self, source: SourceConfig, fetcher: Fetcher) -> list[TeamRef]:
        """Probe ``page=1`` with a cheap ``per_page=1`` request to learn
        the real query's page count, then enumerate one ``TeamRef`` per
        real (configured ``per_page``) page.

        Raises:
            config.CredentialError: a missing/invalid ``ROBOTEVENTS_KEY``
                (propagated uncaught from ``_auth_headers()``, before
                any request is sent) or a live 401 response from the
                probe -- sprint 023 ticket 001's credential-specific
                cases, mirroring ``sources/tba.py``'s identical
                treatment.
            RuntimeError: every other probe failure -- a non-200
                non-401 status, unparseable JSON, or a missing/invalid
                ``meta.last_page`` -- unchanged, still a plain
                ``RuntimeError``. Matches ``sources/tba.py``'s exact
                "raise on any probe failure, never degrade" contract --
                see this module's own docstring for why that (not
                ``adapters/robotevents.py``'s graceful degrade) is the
                right contract here.
        """
        api_base = source.config.get("api_base") or config.get_robotevents_url()
        country = source.config.get("country") or ""
        per_page = int(source.config.get("per_page", DEFAULT_PER_PAGE))

        probe_url = _teams_url(api_base, country, page=1, per_page=1)
        response = fetcher.get(probe_url, headers=_auth_headers())

        if response.status == 401:
            raise config.CredentialError(
                f"RobotEvents auth failed (401) for {probe_url}; check ROBOTEVENTS_KEY"
            )
        if response.status != 200:
            raise RuntimeError(
                f"RobotEvents teams probe {probe_url} returned status {response.status}"
            )

        try:
            data = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"RobotEvents teams probe {probe_url} returned unparseable JSON"
            ) from exc

        last_page = (data.get("meta") or {}).get("last_page") if isinstance(data, dict) else None
        if not isinstance(last_page, int) or last_page < 1:
            raise RuntimeError(
                f"RobotEvents teams probe {probe_url} returned an invalid "
                f"meta.last_page: {last_page!r}"
            )

        return [
            TeamRef(url=_teams_url(api_base, country, page, per_page))
            for page in range(1, last_page + 1)
        ]

    def fetch(self, ref: TeamRef, fetcher: Fetcher) -> RawTeamResponse:
        response = fetcher.get(ref.url, headers=_auth_headers())
        return RawTeamResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawTeamResponse, source: SourceConfig) -> Iterable[Team]:
        if raw.status != 200:
            logger.warning(
                "RobotEvents teams page %s returned status %s; skipping", raw.ref.url, raw.status
            )
            return []

        try:
            data = json.loads(raw.body)
        except json.JSONDecodeError:
            logger.warning(
                "RobotEvents teams page %s returned unparseable JSON; skipping", raw.ref.url
            )
            return []

        if not isinstance(data, dict):
            logger.warning(
                "RobotEvents teams page %s returned an unexpected JSON shape; skipping",
                raw.ref.url,
            )
            return []

        records = data.get("data")
        if not isinstance(records, list):
            logger.warning(
                "RobotEvents teams page %s has no usable data[] array; skipping", raw.ref.url
            )
            return []

        teams: list[Team] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            try:
                team = _extract_one(record)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping malformed RobotEvents team record on %s: %s", raw.ref.url, exc
                )
                continue
            if team is not None:
                teams.append(team)
        return teams
