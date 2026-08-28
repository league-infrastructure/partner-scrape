"""The canonical Team record (``teams/model.py``).

A ``Team`` is a standing directory entity -- a FIRST robotics team
fielded by a school or a family/community group -- with no date, no
recurrence, and no relevance gate. It is deliberately a separate
dataclass from ``partner_scrape.model.Event``, not a widened ``Kind``:
``export/writer.py``'s current-and-upcoming filter would silently drop
every Team if it were routed through ``Opportunity``, and widening
``Kind`` would ripple into ``enrich/enricher.py``, ``normalize/run.py``,
and ``export/writer.py`` for no reuse (no date, no recurrence, no
taxonomy in common). See ``teams/DESIGN.md`` and
``clasi/sprints/011-robot-teams/sprint.md``'s Design Rationale.

Fields are populated directly by each source's ``extract()``
(``sources/ftcscout.py`` for this ticket; ``sources/tba.py`` in ticket
011-003), then progressively enriched by later pipeline stages this
ticket does not implement: ``merge.py`` (ticket 011-003) sets
``org_key``/``sibling_team_ids`` for cross-league identity;
``geo.py`` (ticket 011-004) sets ``latitude``/``longitude``/
``location_precision``/``organization_website``/``matched_name``/
``needs_review``. A freshly-extracted ``Team`` therefore has
``location_precision == "none"`` and no coordinates -- that is correct
for this ticket, not a bug: no geocoding rung has run yet.

**No ``email`` field, anywhere on this dataclass.** This is a
structural guarantee, not an omission to remember to avoid later: the
FLL seed a follow-on sprint may eventually ingest
(``data/robot-teams.json``) carries 40 email addresses, including six
volunteer coaches' personal Gmail accounts, and there must be nowhere
on this record to put one. Do not add one, even behind a flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

#: Short program code. Only ``"FTC"`` is produced by this ticket
#: (``sources/ftcscout.py``); ``"FRC"`` arrives with ticket 011-003's
#: ``sources/tba.py``, ``"FLL"`` only with the deferred follow-on
#: sprint's static-roster import.
League = Literal["FTC", "FRC", "FLL"]

#: Which rung of ``teams/geo.py``'s seven-rung offline ladder (ticket
#: 011-004) produced this Team's coordinates. ``"none"`` is the
#: honest default for a Team no geocoding pass has touched yet --
#: never a fabricated point. See ``teams/DESIGN.md``'s "Location
#: precision is a first-class, honestly-reported property" design
#: commitment.
LocationPrecision = Literal["school", "zip", "city", "none"]

#: What ``organization`` actually names. ``"school"`` when a source
#: reports a real sponsoring school; ``"family_community"`` for a home
#: team fielded by a family or community group with no school
#: (FTCScout's ``schoolName == "Family/Community"`` sentinel, ~38% of
#: San Diego FTC teams); ``"unknown"`` when a source reports neither.
OrgType = Literal["school", "family_community", "unknown"]


@dataclass
class Team:
    """One FIRST robotics team, from any league/program, any source.

    Every field defaults to an empty/neutral value so a bare ``Team()``
    is always constructible (matching ``partner_scrape.model.Event``'s
    convention) -- useful in tests and for progressive enrichment
    across pipeline stages that each set only the fields they own.
    """

    # Identity
    team_id: str = ""  # f"{league.lower()}-{number}" -- league prefix is
    # mandatory: FTC 1622 and FRC 1622 are different teams that happen
    # to share a number.
    league: str = ""
    program: str = ""  # human-readable program name, e.g. "FIRST Tech Challenge"
    number: int = 0
    name: str = ""

    # Organization
    organization: str = ""
    org_type: str = ""  # OrgType, kept as plain str (see registry/schema.py's
    # precedent: over-typing a field that different sources populate
    # differently isn't worth revisiting at every new source)

    # Location -- acquisition-time fields (city, postal_code) vs.
    # geocoding-time fields (latitude, longitude, location_precision,
    # in_region), the latter untouched until teams/geo.py (ticket
    # 011-004) runs.
    city: str = ""
    postal_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    location_precision: str = "none"  # LocationPrecision
    in_region: bool = True  # flagged false for a team outside San Diego
    # County, never dropped -- see sources/ftcscout.py's OUT_OF_REGION_CITIES.
    matched_name: str = ""  # geo.py (ticket 011-004): the real-world name
    # ("St. Pius X School", "ZIP 92037 centroid", "San Diego (city
    # centroid)") the resolver actually matched against -- set on every
    # resolved Team (school/zip/city precision alike), empty for
    # location_precision == "none". "Why is this team here?" always has
    # a string answer, never a silent guess.
    needs_review: bool = False  # geo.py (ticket 011-004): True when a
    # fuzzy school-name match scored below 0.85 -- surfaced rather than
    # published silently. Never set for an exact/override/zip/city
    # match (each of those is either human-verified or deterministic,
    # with no fuzzy score to distrust).

    # Web presence -- deliberately thin this ticket: FTCScout's own
    # `website` field is null for 0/152 San Diego FTC teams (measured
    # live, national too: 0/3,412 across nine regions), so
    # sources/ftcscout.py never sets these. Ticket 011-003's TBA source
    # (72% website coverage) is the first real populator.
    website: str = ""
    website_status: str = ""  # liveness-check result, not set this ticket
    organization_website: str = ""  # CDE-matched school's own WebSite
    # column, set by teams/geo.py (ticket 011-004) on a school-precision
    # public-school match only (NCES's private-school data carries no
    # website column). Deliberately a separate field from Team.website --
    # never presented as the team's own site.

    # Program metadata
    rookie_year: int | None = None
    active: bool = True
    last_season: int | None = None
    sponsors: list[str] = field(default_factory=list)

    # Cross-league identity -- set by teams/merge.py (ticket 011-003),
    # untouched by a single-source extraction.
    org_key: str = ""
    sibling_team_ids: list[str] = field(default_factory=list)

    # Provenance: which source(s) contributed to this record, e.g.
    # ["ftcscout"], or ["ftcscout", "tba"] after ticket 011-003's merge.
    sources: list[str] = field(default_factory=list)
