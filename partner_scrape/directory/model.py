"""The canonical Place record (``directory/model.py``).

A ``Place`` is a curated, standing "where to go any day" San Diego
STEM venue -- a makerspace, planetarium, observatory, tidepool site,
nature center, or library maker lab -- with no date, no recurrence,
and no relevance gate, following the same shape ``teams.model.Team``
already established for a standing directory entity (issue 35, sprint
018's Design Rationale: "Places and Clubs ... following the same shape
robot teams already proved needs its own model").

**Deliberately a separate flat dataclass from ``Team`` and the future
``Club`` (ticket 018-008), not a shared base class.** Per sprint.md's
Design Rationale ("`Place` and `Club` are separate flat dataclasses,
not a shared base class"), a `Club` has membership/program concerns a
`Place` doesn't (and vice versa for hours/category concerns) -- forcing
a shared base would either grow speculative optional fields on both or
under-model one of them. Field-name duplication with `Team`
(``website``, location fields, ``sources``) is accepted, matching the
existing `Team`/`Event` precedent `teams/model.py`'s own docstring
cites.

Every field defaults to an empty/neutral value so a bare ``Place()`` is
always constructible, matching ``Team``'s and ``Event``'s existing
convention.
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
