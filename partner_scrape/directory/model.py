"""The canonical Place, Club, and Offering records (``directory/model.py``).

A ``Place`` is a curated, standing "where to go any day" San Diego
STEM venue -- a makerspace, planetarium, observatory, tidepool site,
nature center, or library maker lab -- with no date, no recurrence,
and no relevance gate, following the same shape ``teams.model.Team``
already established for a standing directory entity (issue 35, sprint
018's Design Rationale: "Places and Clubs ... following the same shape
robot teams already proved needs its own model").

A ``Club`` (ticket 018-008) is the same kind of standing directory
entity for a San Diego club chapter -- Hack Club chapters are this
sprint's one proof-of-concept type (issue 35's other six named club
types are split to issue 35b, a future sprint). See :class:`Club`'s
own docstring below for its full rationale.

An ``Offering`` (sprint 030) is a third standing directory entity: an
undated, non-recurring "here's what this org offers and how to get it"
record, serving both issue 14 Strategy B (volunteer org profiles) and
issue 33 part 2 (free/Title I school-program records) through one model
with an ``offering_type`` discriminator. Unlike `Place`/`Club`, an
`Offering` carries **no location/geocoding fields at all** -- see
:class:`Offering`'s own docstring for the full rationale.

**Deliberately three separate flat dataclasses, not a shared base
class.** Per sprint.md's Design Rationale ("`Place` and `Club` are
separate flat dataclasses, not a shared base class"), a `Club` has
membership/program concerns a `Place` doesn't (and vice versa for
hours/category concerns) -- forcing a shared base would either grow
speculative optional fields on both or under-model one of them.
Field-name duplication with `Team` (``website``, location fields,
``sources``) is accepted, matching the existing `Team`/`Event`
precedent `teams/model.py`'s own docstring cites -- and the same
duplication is accepted among `Place`, `Club`, and `Offering`
themselves, for the identical reason (sprint 030 extends this
three-way, per this sprint's `directory/DESIGN.md` Revision).

Every field defaults to an empty/neutral value so a bare ``Place()``,
``Club()``, or ``Offering()`` is always constructible, matching
``Team``'s and ``Event``'s existing convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, get_args

#: The six "where to go any day" categories issue 35 named. Kept a
#: plain ``str`` on the dataclass itself (matching ``Team.org_type``'s
#: convention: over-typing a field a small, hand-curated dataset
#: already controls tightly isn't worth revisiting) -- this Literal
#: exists for documentation and for :data:`VALID_CATEGORIES`'s
#: drift-proof derivation, consulted by
#: ``sources/static_roster.py``'s per-entry validation.
Category = Literal[
    "makerspace",
    "planetarium",
    "observatory",
    "tide-pool",
    "nature-center",
    "library-maker-lab",
]

#: Derived from :data:`Category` rather than hand-listed a second time,
#: the same drift-proof pattern ``teams/export.py``'s
#: ``TEAMS_SCHEMA_FIELDS`` uses for ``dataclasses.fields()``.
VALID_CATEGORIES: frozenset[str] = frozenset(get_args(Category))

#: How confident this Place's coordinates are -- distinct from
#: ``geo_ladder.LocationMatch.location_precision`` (``"school"``/
#: ``"zip"``/``"city"``/``"none"``) because a Place is normally resolved
#: by hand from the venue's own published address, not matched against
#: a school directory. ``"address"`` is this module's own top rung,
#: stamped by the curated static-roster source itself
#: (``sources/static_roster.py``) whenever the roster entry carries a
#: hand-curated ``latitude``/``longitude`` -- never produced by the
#: shared ladder. ``"zip"``/``"city"``/``"none"`` are the shared
#: ``geo_ladder.GeoLadder``'s own rungs 5-7, used only as a fallback
#: (``directory/pipeline.py``'s ``_apply_geo_fallback``) for the rare
#: Place with no confidently-known exact address -- never a guess, and
#: never the ladder's organization-name school-matching rungs 1-4 (a
#: Place has no sponsoring organization to match).
LocationPrecision = Literal["address", "zip", "city", "none"]

#: Derived from :data:`LocationPrecision`, same drift-proof pattern as
#: :data:`VALID_CATEGORIES`.
VALID_LOCATION_PRECISIONS: frozenset[str] = frozenset(get_args(LocationPrecision))

#: Whether a Place is open to visit today. ``"opening"`` marks a venue
#: that is announced but not yet operating (e.g. Atlas Labs, opening
#: January 2027) -- included in the directory per issue 35's explicit
#: instruction, never presented as already operating.
#: :attr:`Place.status_note` should always carry the human-readable
#: detail whenever ``status != "open"``.
Status = Literal["open", "opening", "closed"]

#: Derived from :data:`Status`, same drift-proof pattern as
#: :data:`VALID_CATEGORIES`.
VALID_STATUSES: frozenset[str] = frozenset(get_args(Status))


@dataclass
class Place:
    """One curated San Diego "where to go any day" STEM place, from any
    category, any source.

    Populated directly by ``sources/static_roster.py``'s ``extract()``
    for every field except the location-fallback fields
    (``latitude``/``longitude``/``location_precision``/``matched_name``),
    which the static roster sets directly when it carries a hand-curated
    coordinate and otherwise leaves at their honest ``None``/``"none"``
    defaults for ``directory.pipeline._apply_geo_fallback`` (the shared
    ``geo_ladder.GeoLadder``'s ZIP/city-centroid rungs) to resolve
    afterward -- mirroring ``Team``'s "freshly-extracted, not yet
    geocoded" convention, except most ``Place`` rows never need the
    fallback at all (see ``teams/model.py``'s own docstring for the
    ``Team`` precedent this mirrors).
    """

    # Identity
    place_id: str = ""  # slug, e.g. "sdpl-idea-lab-central" -- also this
    # Place's stable URL slug. A single field doubling as both id and
    # slug, matching Team.team_id's convention: no separate
    # model.slugify() needed (teams.sources.static_roster's "No
    # slug/normalizer duplication" precedent applies identically here).
    name: str = ""
    category: str = ""  # Category, see this module's own docstring for
    # why this stays a plain str.
    description: str = ""

    # Location -- see LocationPrecision's own docstring for the
    # "address" (hand-curated) vs. "zip"/"city" (shared-ladder fallback)
    # vs. "none" (never guessed) distinction.
    address: str = ""
    city: str = ""
    postal_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    location_precision: str = "none"  # LocationPrecision
    matched_name: str = ""  # why is this place here? Set whenever
    # location_precision != "none" -- mirrors Team.matched_name's
    # existing convention ("why is this team here?" always has a string
    # answer). For an "address"-precision Place this is just `name`
    # (the curated source knows exactly which place it curated); for a
    # "zip"/"city" fallback match it is the ladder's own
    # "ZIP NNNNN centroid" / "City (city centroid)" string.
    needs_review: bool = False  # Always False for an "address"-precision
    # match (no fuzzy score involved) and for this ticket's curated
    # dataset overall -- no Place here is ever routed through the
    # ladder's fuzzy school-matching rungs (3/4). Kept on the dataclass,
    # not omitted, so a future fallback path that did need it would not
    # require a schema change.

    website: str = ""

    status: str = "open"  # Status
    status_note: str = ""  # Required (non-empty) whenever status !=
    # "open" -- e.g. "Opening January 2027 -- not yet operating." Never
    # left blank for a non-"open" status; see
    # sources/static_roster.py's own validation.

    related_partner_id: int | None = None  # site/src/data/partners.json's
    # own `id`, hand-copied -- never auto-joined (sprint.md's own
    # ticket-007 instruction: "do not attempt an automatic
    # cross-reference join this sprint... hand-copy the value"). `None`
    # when this Place's operating org has no confident partner-roster
    # match.

    # Provenance: which source(s) contributed to this record, e.g.
    # ["static_roster"] -- matches Team.sources's existing convention.
    sources: list[str] = field(default_factory=list)


#: Program/type this club chapter belongs to. Ticket 018-008 populated
#: only ``"hack-club"``; sprint 032 ticket 001 widened this Literal to
#: also include issue 35b's six remaining club types --
#: ``"cyberpatriot"``, ``"science-olympiad"``, ``"4-h"``,
#: ``"girls-who-code"``, ``"civil-air-patrol"``, and ``"sea-cadets"``.
#: **Sprint 036 ticket 002 narrows it a first time**, dropping
#: ``"science-olympiad"``/``"cyberpatriot"`` -- both are competition
#: teams, not clubs, per issue 47's meets-vs-competes rule, and have
#: migrated to ``teams.model.Team`` (``League`` values ``"SCIOLY"``/
#: ``"CYBERPATRIOT"``) via the new ``teams.sources.
#: team_static_roster.TeamStaticRosterSource``, preserving their
#: verified geocoding exactly -- see ``directory/DESIGN.md``'s sprint
#: 036 Revision for the migration detail and the diff-check gate that
#: proved it. Ticket 003 narrows this Literal a second time, dropping
#: ``"4-h"``/``"civil-air-patrol"``/``"sea-cadets"`` (organizations this
#: project has decided not to carry at all), landing at
#: ``Literal["hack-club", "girls-who-code"]``. Kept a plain ``str`` on
#: the dataclass itself, matching ``Place.category``'s/``Team.
#: org_type``'s own "don't over-type a field a small, hand-curated
#: dataset already controls tightly" convention -- this Literal exists
#: for documentation and for :data:`VALID_CLUB_TYPES`'s drift-proof
#: derivation, consulted by ``sources/club_static_roster.py``'s
#: per-entry validation.
ClubType = Literal[
    "hack-club",
    "4-h",
    "girls-who-code",
    "civil-air-patrol",
    "sea-cadets",
]

#: Derived from :data:`ClubType`, the same drift-proof pattern
#: :data:`VALID_CATEGORIES` uses for :data:`Category`.
VALID_CLUB_TYPES: frozenset[str] = frozenset(get_args(ClubType))

#: How confident this Club's coordinates are. Distinct from
#: :data:`LocationPrecision` (``Place``'s own top rung is
#: ``"address"``, a hand-curated venue coordinate) because a ``Club``
#: genuinely has a sponsoring organization -- its host school -- to run
#: through the shared ``geo_ladder.GeoLadder``'s *full* ladder
#: (``GeoLadder.locate()``, including the school-matching rungs 1-4),
#: mirroring ``teams.geo.SchoolIndex.resolve(team)`` exactly rather
#: than ``directory.pipeline._apply_geo_fallback()``'s Place-only
#: rungs-5-6-only shortcut. ``"school"`` replaces ``Place``'s
#: ``"address"`` as the top rung; ``"zip"``/``"city"``/``"none"`` are
#: the ladder's own rungs 5-7, unchanged.
ClubLocationPrecision = Literal["school", "zip", "city", "none"]

#: Derived from :data:`ClubLocationPrecision`, same drift-proof pattern
#: as :data:`VALID_LOCATION_PRECISIONS`.
VALID_CLUB_LOCATION_PRECISIONS: frozenset[str] = frozenset(get_args(ClubLocationPrecision))

#: Whether a Club chapter is still meeting. ``"active"`` is the only
#: value this ticket's curated Hack Club roster uses; ``"inactive"``
#: exists for a chapter a future curation pass finds has folded,
#: matching ``Place.Status``'s own "record the fact, don't delete the
#: row" convention. :attr:`Club.status_note` should always carry the
#: human-readable detail whenever ``status != "active"``.
ClubStatus = Literal["active", "inactive"]

#: Derived from :data:`ClubStatus`, same drift-proof pattern as
#: :data:`VALID_STATUSES`.
VALID_CLUB_STATUSES: frozenset[str] = frozenset(get_args(ClubStatus))


@dataclass
class Club:
    """One curated San Diego club chapter, from any program, any
    source.

    Populated directly by a ``ClubSource``'s ``extract()`` (e.g.
    ``sources/club_static_roster.py``) for every field
    except the geocoding-time fields (``latitude``/``longitude``/
    ``location_precision``/``matched_name``/``needs_review``/
    ``host_school_website``), which
    ``directory.pipeline._apply_club_geocoding()`` sets afterward by
    running ``host_school``/``city``/``postal_code`` through the
    shared ``geo_ladder.GeoLadder``'s full ladder -- the same
    "acquisition never geocodes" separation ``teams/sources/*.py``
    already establishes for ``Team`` (``teams.geo.geocode_teams()``
    runs after every source, never inside one). A freshly-extracted
    ``Club`` therefore has ``location_precision == "none"`` and no
    coordinates -- correct for a not-yet-geocoded record, not a bug.

    **``website`` vs. ``host_school_website``, mirroring
    ``Team.website`` vs. ``Team.organization_website`` exactly.**
    ``website`` is the chapter's own site/social, when the source
    curated one -- never fabricated (this ticket's curated Hack Club
    roster does not carry one; see that source's own docstring).
    ``host_school_website`` is the *school's* own website, copied from
    a school-precision match's ``geo_ladder.LocationMatch.website``
    only when the match is a public school (NCES's private-school data
    carries no website column, so this stays ``""`` for a
    private-school match) -- deliberately a separate field, never
    presented as the club's own site.
    """

    # Identity
    club_id: str = ""  # slug, e.g. "hack-club-university-city-high" --
    # also this Club's stable URL slug, matching Place.place_id's /
    # Team.team_id's "one field doubles as both id and slug" convention
    # (no separate model.slugify() needed).
    name: str = ""  # e.g. "Hack Club at University City High School"
    club_type: str = ""  # ClubType, see this module's own docstring
    # for why this stays a plain str.

    # Host organization -- the sponsoring school/org this chapter meets
    # at. This IS the `organization` argument
    # `directory.pipeline._apply_club_geocoding()` passes to the shared
    # `geo_ladder.GeoLadder.locate()`, mirroring `Team.organization`'s
    # identical role in `teams.geo.SchoolIndex.resolve()`.
    host_school: str = ""

    # Location -- acquisition-time (city, postal_code) vs.
    # geocoding-time (everything else), the latter untouched until
    # `directory.pipeline._apply_club_geocoding()` runs. See this
    # module's own docstring for why a Club (unlike a Place) runs
    # through the ladder's *full* school-matching ladder, not just the
    # ZIP/city rungs.
    city: str = ""
    postal_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    location_precision: str = "none"  # ClubLocationPrecision
    matched_name: str = ""  # why is this club here? Mirrors
    # Place.matched_name's / Team.matched_name's "always has a string
    # answer" convention -- the real-world school name the ladder
    # actually matched, or the ZIP/city centroid label, empty for
    # location_precision == "none".
    needs_review: bool = False  # True for a rung-3/4 fuzzy school-name
    # match scored below 0.85 -- mirrors Team.needs_review exactly
    # (same ladder, same threshold, same "flag it, don't silently
    # publish it" rule). Never set for a rung-1/2 exact/override match
    # or a rung-5/6 ZIP/city match.

    website: str = ""  # the chapter's own site/social, when curated --
    # see this module's own docstring for the split from
    # host_school_website below.
    host_school_website: str = ""  # the matched school's own WebSite
    # column, set by directory.pipeline._apply_club_geocoding() on a
    # school-precision public-school match only. See this module's own
    # docstring.

    meeting_note: str = ""  # human-readable meeting cadence, when the
    # source states one, e.g. "Meets Thursdays after school." Left ""
    # when the source doesn't say one -- never guessed. The curated
    # Hack Club roster does not carry a meeting schedule; see
    # sources/club_static_roster.py's own docstring.

    status: str = "active"  # ClubStatus
    status_note: str = ""  # Required (non-empty) whenever status !=
    # "active", mirroring Place.status_note's own validation
    # convention -- never left blank for a non-"active" status.

    # Provenance: which source(s) contributed to this record, e.g.
    # ["hack-club-sd"] (the registering SourceConfig.source_id) --
    # matches Place.sources's / Team.sources's existing convention.
    sources: list[str] = field(default_factory=list)


#: The two genres one `Offering` model serves (sprint 030): a standing
#: individual volunteer role (issue 14 Strategy B -- Fleet, SDZWA,
#: Birch, the Nat, ILACSD, San Diego River Park Foundation) or a
#: free/Title I school-program record (issue 33 part 2 -- Zoo FREE
#: field trips, the Nat's Museum Access Fund, Living Coast Title 1 aid,
#: Birch financial aid, Fleet discounted trips, Qualcomm Thinkabit Lab,
#: Biocom Life Science Station/Innov8Ed). Kept a plain ``str`` on the
#: dataclass itself, matching ``Place.category``'s/``Club.club_type``'s
#: own "don't over-type a field a small, hand-curated dataset already
#: controls tightly" convention -- this Literal exists for
#: documentation and for :data:`VALID_OFFERING_TYPES`'s drift-proof
#: derivation, consulted by
#: ``sources/offering_static_roster.py``'s per-entry validation. See
#: this sprint's `directory/DESIGN.md` Revision for the full "why one
#: model, not two" Design Rationale.
OfferingType = Literal["volunteer", "free_program"]

#: Derived from :data:`OfferingType`, the same drift-proof pattern
#: :data:`VALID_CATEGORIES`/:data:`VALID_CLUB_TYPES` use.
VALID_OFFERING_TYPES: frozenset[str] = frozenset(get_args(OfferingType))

#: Whether an Offering is still available as described. ``"seasonal"``
#: covers a program that only runs part of the year (e.g. a summer-only
#: field-trip window) without implying it is closed -- distinct from
#: both ``Place.Status``'s ``"opening"`` (not yet operating at all) and
#: ``Club.ClubStatus``'s ``"inactive"`` (folded). :attr:`Offering.
#: status_note` should always carry the human-readable detail whenever
#: ``status != "active"``, mirroring ``Place.status_note``'s/``Club.
#: status_note``'s existing validation rule exactly.
OfferingStatus = Literal["active", "seasonal", "closed"]

#: Derived from :data:`OfferingStatus`, same drift-proof pattern as
#: :data:`VALID_STATUSES`/:data:`VALID_CLUB_STATUSES`.
VALID_OFFERING_STATUSES: frozenset[str] = frozenset(get_args(OfferingStatus))


@dataclass
class Offering:
    """One curated, standing "here's what this org offers and how to
    get it" record -- an undated, non-recurring entity, serving both
    issue 14 Strategy B (volunteer org profiles) and issue 33 part 2
    (free/Title I school-program records) through one model with an
    :attr:`offering_type` discriminator, rather than two separate
    models. See this sprint's `directory/DESIGN.md` Revision (2026-09-02
    -- sprint 030 Offerings standing-entity type) for the full rationale
    this docstring summarizes.

    Populated directly by an ``OfferingSource``'s ``extract()`` (this
    ticket: ``sources/offering_static_roster.py``) for every field --
    unlike `Place`/`Club`, there is no separate geocoding-time stage:
    **`Offering` carries no location/geocoding fields at all**. An
    Offering is a program or role hosted by an already-locatable org
    (see :attr:`related_partner_id`), not a place you travel to in its
    own right -- giving it its own `latitude`/`longitude` would mean
    geocoding the same organization a second time for no reader
    benefit. `directory.pipeline.run_directory()`'s dispatch therefore
    has no fallback/geocoding stage for `Offering` at all, and no
    `GeoLadder` dependency is added for this addition.

    **`age_minimum` is a first-class typed field, never folded into
    free-text `eligibility`.** Issue 14's own instruction: "Note age
    minimums explicitly: Fleet 18+, SDZWA 18+, Birch 16+ -- it matters
    for the teen audience." `None` means "no individual-volunteer age
    minimum applies" (every free/Title-I school-program record's
    eligibility is about the *school*, not an individual's age) --
    never a guessed `0`.

    **`related_partner_id` reuses `Place`'s existing hand-verified-join
    convention exactly** -- never auto-derived; hand-copied against
    `site/src/data/partners.json`'s own `id` field at authoring time,
    same as `places.toml`'s existing rows.

    Every field defaults to an empty/neutral value so a bare
    ``Offering()`` is always constructible, matching `Place`'s/`Club`'s
    existing convention.
    """

    # Identity
    offering_id: str = ""  # slug, e.g. "fleet-science-center-volunteer"
    # -- also this Offering's stable URL slug, matching Place.place_id's
    # / Club.club_id's "one field doubles as both id and slug"
    # convention (no separate model.slugify() needed).
    org_name: str = ""  # the operating organization, e.g. "Fleet
    # Science Center" -- the counterpart to Place.name/Club.name for
    # "who is this," distinct from `title` below ("what is this,
    # specifically").
    title: str = ""  # the offering's own name, e.g. "Volunteer
    # Program" or "Museum Access Fund" -- what a reader clicks into,
    # scoped under `org_name`.
    offering_type: str = ""  # OfferingType, see this module's own
    # docstring for why this stays a plain str.
    description: str = ""

    eligibility: str = ""  # free-text, e.g. "Title I schools only" or
    # "High school students, San Diego County." Never used to carry an
    # age minimum -- see age_minimum below.
    age_minimum: int | None = None  # first-class typed field -- see
    # this dataclass's own docstring for why this is never folded into
    # `eligibility`. `None` means "no individual-volunteer age minimum
    # applies," never a guessed `0`.

    how_to_book: str = ""  # human-readable instructions for how to
    # actually get this offering -- apply, register, sign up, contact.
    link_url: str = ""  # link out to the org's own page for this
    # offering, matching Place.website's/Club.website's "never
    # fabricated" convention.

    last_verified: str = ""  # ISO date (YYYY-MM-DD) this record was
    # actually checked against the org's own current page -- never
    # guessed or left as a placeholder for a real curated row.

    status: str = "active"  # OfferingStatus
    status_note: str = ""  # Required (non-empty) whenever status !=
    # "active", mirroring Place.status_note's/Club.status_note's own
    # validation convention exactly -- never left blank for a
    # non-"active" status.

    related_partner_id: int | None = None  # site/src/data/partners.json's
    # own `id`, hand-copied -- never auto-joined. See this dataclass's
    # own docstring; reuses Place.related_partner_id's convention
    # exactly, including its join-integrity check discipline
    # (`directory.pipeline._check_related_partner_references()`).

    # Provenance: which source(s) contributed to this record, e.g.
    # ["offering_static_roster"] -- matches Place.sources's/Club.sources's
    # existing convention.
    sources: list[str] = field(default_factory=list)
