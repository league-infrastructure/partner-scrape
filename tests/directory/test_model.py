"""Tests for partner_scrape.directory.model: the `Place`/`Club`
dataclasses and their drift-proof value-set constants.
"""

from __future__ import annotations

from dataclasses import fields

from partner_scrape.directory.model import (
    Club,
    Place,
    VALID_CATEGORIES,
    VALID_CLUB_LOCATION_PRECISIONS,
    VALID_CLUB_STATUSES,
    VALID_CLUB_TYPES,
    VALID_LOCATION_PRECISIONS,
    VALID_STATUSES,
)


class TestBarePlaceIsConstructible:
    def test_bare_place_constructs_with_neutral_defaults(self):
        place = Place()

        assert place.place_id == ""
        assert place.name == ""
        assert place.category == ""
        assert place.latitude is None
        assert place.longitude is None
        assert place.location_precision == "none"
        assert place.needs_review is False
        assert place.status == "open"
        assert place.status_note == ""
        assert place.related_partner_id is None
        assert place.sources == []


class TestValueSetConstants:
    """VALID_CATEGORIES/VALID_STATUSES/VALID_LOCATION_PRECISIONS are
    derived from their respective Literal type via `typing.get_args`,
    matching `teams/export.py`'s `TEAMS_SCHEMA_FIELDS` drift-proof
    derivation pattern -- these tests pin the expected value sets so a
    typo in the Literal is caught here, not silently in a downstream
    validator."""

    def test_valid_categories_matches_issue_35s_six_named_categories(self):
        assert VALID_CATEGORIES == {
            "makerspace",
            "planetarium",
            "observatory",
            "tide-pool",
            "nature-center",
            "library-maker-lab",
        }

    def test_valid_statuses(self):
        assert VALID_STATUSES == {"open", "opening", "closed"}

    def test_valid_location_precisions(self):
        assert VALID_LOCATION_PRECISIONS == {"address", "zip", "city", "none"}

    def test_constants_are_never_empty(self):
        # Sanity check the typing.get_args() derivation itself isn't
        # vacuously true against an empty Literal.
        assert VALID_CATEGORIES
        assert VALID_STATUSES
        assert VALID_LOCATION_PRECISIONS


class TestNoSharedBaseWithTeam:
    """Sprint 018's Design Rationale: `Place` is a standalone flat
    dataclass, never a subclass of or sharing a base with
    `teams.model.Team`."""

    def test_place_does_not_subclass_team(self):
        from partner_scrape.teams.model import Team

        assert not issubclass(Place, Team)
        assert Place.__mro__[1] is object


class TestFieldSet:
    def test_sources_field_exists_for_provenance(self):
        names = {f.name for f in fields(Place)}
        assert "sources" in names

    def test_no_email_field(self):
        # Not a stated requirement for Places the way it is for Team
        # (no privacy-sensitive upstream export here -- see
        # sources/static_roster.py's own docstring), but a Place is a
        # public venue record and should never grow a contact-data
        # field either.
        names = {f.name for f in fields(Place)}
        assert "email" not in names


class TestBareClubIsConstructible:
    def test_bare_club_constructs_with_neutral_defaults(self):
        club = Club()

        assert club.club_id == ""
        assert club.name == ""
        assert club.club_type == ""
        assert club.host_school == ""
        assert club.latitude is None
        assert club.longitude is None
        assert club.location_precision == "none"
        assert club.matched_name == ""
        assert club.needs_review is False
        assert club.website == ""
        assert club.host_school_website == ""
        assert club.meeting_note == ""
        assert club.status == "active"
        assert club.status_note == ""
        assert club.sources == []


class TestClubValueSetConstants:
    """VALID_CLUB_TYPES/VALID_CLUB_LOCATION_PRECISIONS/
    VALID_CLUB_STATUSES are derived from their respective Literal type
    via `typing.get_args`, matching Place's own VALID_* drift-proof
    derivation pattern -- these tests pin the expected value sets so a
    typo in the Literal is caught here, not silently in a downstream
    validator."""

    def test_valid_club_types_is_hack_club_only_this_ticket(self):
        assert VALID_CLUB_TYPES == {"hack-club"}

    def test_valid_club_statuses(self):
        assert VALID_CLUB_STATUSES == {"active", "inactive"}

    def test_valid_club_location_precisions_matches_the_shared_ladders_precisions(self):
        # "school" replaces Place's "address" as Club's top rung -- see
        # directory/model.py's ClubLocationPrecision docstring.
        assert VALID_CLUB_LOCATION_PRECISIONS == {"school", "zip", "city", "none"}

    def test_constants_are_never_empty(self):
        assert VALID_CLUB_TYPES
        assert VALID_CLUB_STATUSES
        assert VALID_CLUB_LOCATION_PRECISIONS


class TestClubNoSharedBaseWithPlaceOrTeam:
    """Sprint 018's Design Rationale: `Club` is a standalone flat
    dataclass, never a subclass of or sharing a base with `Place` or
    `teams.model.Team`."""

    def test_club_does_not_subclass_place(self):
        assert not issubclass(Club, Place)

    def test_club_does_not_subclass_team(self):
        from partner_scrape.teams.model import Team

        assert not issubclass(Club, Team)

    def test_club_mro_has_no_shared_base_beyond_object(self):
        assert Club.__mro__[1] is object


class TestClubFieldSet:
    def test_sources_field_exists_for_provenance(self):
        names = {f.name for f in fields(Club)}
        assert "sources" in names

    def test_no_email_field(self):
        names = {f.name for f in fields(Club)}
        assert "email" not in names

    def test_website_and_host_school_website_are_both_present_and_distinct(self):
        # Mirrors Team.website vs. Team.organization_website's split --
        # see Club's own docstring for why these must never collapse
        # into one field.
        names = {f.name for f in fields(Club)}
        assert "website" in names
        assert "host_school_website" in names
