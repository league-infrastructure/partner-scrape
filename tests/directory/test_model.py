"""Tests for partner_scrape.directory.model: the `Place` dataclass and
its drift-proof value-set constants.
"""

from __future__ import annotations

from dataclasses import fields

from partner_scrape.directory.model import (
    Place,
    VALID_CATEGORIES,
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
