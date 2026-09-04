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
from typing import Literal, get_args

#: Short program/competition-circuit code. Only ``"FTC"`` is produced by
#: this ticket (``sources/ftcscout.py``); ``"FRC"`` arrives with ticket
#: 011-003's ``sources/tba.py``, ``"FLL"`` only with the deferred
#: follow-on sprint's static-roster import. ``"VEX"`` arrives with
#: sprint 016 ticket 005's ``sources/robotevents.py`` -- see
#: ``Team.number``'s docstring below for why that source is also what
#: forced ``number`` to widen from ``int`` to ``str``. Sprint 036 widens
#: this Literal a second time to ``"SCIOLY"`` (Science Olympiad) and
#: ``"CYBERPATRIOT"``, generalizing ``Team`` from "FIRST/VEX robotics
#: team" to "any STEM competition team" -- see ``teams/DESIGN.md``'s
#: sprint 036 Revision for the full Design Rationale (widen the
#: existing field rather than add a separate discriminator) this
#: docstring summarizes: ``league``/``program`` already function as
#: "short discriminator code" + "human-readable name," a semantics that
#: was never robotics-specific, only its value set was.
League = Literal["FTC", "FRC", "FLL", "VEX", "SCIOLY", "CYBERPATRIOT"]

#: Derived from :data:`League` rather than hand-listed a second time --
#: the same drift-proof pattern ``directory.model.VALID_CLUB_TYPES``
#: uses for ``ClubType``. Sprint 036 ticket 001 adds this: no prior
#: source ever needed to validate an untrusted ``league`` value (every
#: existing source -- ``ftcscout.py``/``tba.py``/``static_roster.py``/
#: ``robotevents.py`` -- hands ``league`` a single hard-coded literal it
#: controls itself), but the new generic ``team_static_roster.py``
#: reads ``league`` from untrusted TSV rows and needs something to
#: validate against, the same way ``club_static_roster.py`` validates
#: ``club_type`` against ``VALID_CLUB_TYPES``.
VALID_LEAGUES: frozenset[str] = frozenset(get_args(League))

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
    number: str = ""  # sprint 016 ticket 005: widened from int -- VEX team
    # designations are alphanumeric (e.g. "90210A"), a numeric prefix plus a
    # required letter suffix distinguishing sibling teams fielded by the same
    # organization ("90210A"/"90210B"/"90210C" are three distinct real
    # teams). Truncating to the numeric prefix would collide team_id for
    # every multi-team organization, and an `int | str` union would push a
    # type check onto every consumer for no benefit over one consistent
    # type -- see clasi/sprints/016-.../sprint.md's Design Rationale. Kept
    # a plain, untyped str (matching Team.league's existing convention)
    # rather than re-deriving a Literal/regex-constrained type here.
    # `teams/export.py`'s sort key and this repo's site/ Team-rendering
    # files use a natural-sort key (leading digit run as int, full string
    # as tiebreaker) instead of bare arithmetic comparison so existing
    # FTC/FRC/FLL purely-numeric values still sort numerically ("99"
    # before "100"), and VEX's alphanumeric siblings sort adjacently.
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
    social: list[str] = field(default_factory=list)  # team-declared social
    # URLs (Instagram/YouTube/Twitter/etc.), raw strings with no platform
    # label. Set by sprint 013 ticket 006's
    # teams.website_overrides.apply_website_overrides() from the
    # committed teams/data/discovered-websites.toml overlay -- empty for
    # any team absent from that overlay. Never derived from website_status
    # or any live fetch; this is curated, offline data only.
    description: str = ""  # sprint 021 ticket 004: an LLM-summarized,
    # 1-2 sentence "about this team" blurb, set by
    # teams.description_extract.extract_descriptions() from this team's
    # own confirmed website content (never invented, never carrying a
    # fact absent from the gathered page text). "" whenever
    # description_status != "generated".
    description_status: str = "none"  # "generated" (summarized
    # successfully) | "unavailable" (a confirmed fetch existed but this
    # stage could not produce a publishable description -- empty
    # gathered content, an empty LLM response, a no-email/length guard
    # rejection, or a caught cache/LLM failure; see
    # teams.description_extract's own module docstring for the full
    # per-case breakdown) | "none" (no confirmed fetch to extract from
    # at all -- this stage never even looked at this team; mirrors
    # website_status's own "none" vocabulary for "nothing attempted").
    # Deliberately independent of website_status above -- a
    # stem-ecosystem peer's planning-time refinement (sprint 021
    # sprint.md's Solution/Design Rationale): website_status answers
    # "was the site reachable" (the existing dead-link-guard concern,
    # unchanged by this sprint); description_status answers "did we
    # find anything worth showing," a genuinely different,
    # separately-true fact -- a reachable site can still have nothing
    # extractable. Do not collapse the two into one signal.
    description_provenance: str = ""  # "team_website" when
    # description_status == "generated", else "" -- a single scalar
    # (not a per-name dict like sponsor_provenance) since a Team has at
    # most one description.
    description_fetched_at: str = ""  # ISO-8601 UTC timestamp of when
    # `description` was generated, via an injectable `clock` parameter
    # to extract_descriptions() (matching EnrichmentCache's/
    # SponsorCache's own testable-clock convention). "" whenever no
    # description was generated.

    # Program metadata
    rookie_year: int | None = None
    active: bool = True
    last_season: int | None = None
    sponsors: list[str] = field(default_factory=list)
    sponsor_provenance: dict[str, str] = field(default_factory=dict)  # sprint 013
    # ticket 005: display sponsor name -> "structured" | "scraped", one
    # entry per name already present in `sponsors`. Purely additive
    # alongside the flat list -- never a restructured `list[SponsorRecord]`
    # -- so every existing `sponsors`-consuming call site (TeamCard, the
    # detail page, every pre-005 test/fixture) keeps working unchanged.
    # Set by `sources/ftcscout.py` (`"structured"`, for every sponsor its
    # structured API already reports) and by
    # `teams.sponsor_extract.extract_sponsors()` (`"scraped"`, for a name
    # lifted from a fetched team page and classified by the sponsor LLM).
    # See sprint.md's Design Rationale for why a parallel dict was chosen
    # over restructuring `sponsors` itself.

    # Cross-league identity -- set by teams/merge.py (ticket 011-003),
    # untouched by a single-source extraction.
    org_key: str = ""
    sibling_team_ids: list[str] = field(default_factory=list)

    # Provenance: which source(s) contributed to this record, e.g.
    # ["ftcscout"], or ["ftcscout", "tba"] after ticket 011-003's merge.
    sources: list[str] = field(default_factory=list)
