"""Tests for partner_scrape.teams.model: the Team dataclass.

This module lives under ``tests/teams/`` (with its own ``__init__.py``)
rather than flat under ``tests/`` like every other test module in this
project -- deliberately, per the sprint's Test Strategy ("New tests
live under tests/ mirroring partner_scrape/teams/'s layout"). The
``__init__.py`` is required, not decorative: without it, pytest's
default "prepend" import mode would register this file as top-level
module ``test_model``, colliding with the existing
``tests/test_model.py`` (which tests ``partner_scrape.model.Event``)
and failing collection with an "import file mismatch" error.
"""

from __future__ import annotations

import dataclasses

from partner_scrape.teams.model import VALID_LEAGUES, Team


class TestTeamDefaults:
    def test_bare_team_is_constructible_with_sane_empty_defaults(self):
        team = Team()

        assert team.team_id == ""
        assert team.league == ""
        assert team.program == ""
        # Sprint 016 ticket 005: widened from int to str -- VEX
        # designations are alphanumeric (e.g. "90210A").
        assert team.number == ""
        assert team.name == ""
        assert team.organization == ""
        assert team.org_type == ""
        assert team.city == ""
        assert team.postal_code == ""
        assert team.latitude is None
        assert team.longitude is None
        assert team.location_precision == "none"
        assert team.in_region is True
        assert team.website == ""
        assert team.website_status == ""
        assert team.organization_website == ""
        assert team.rookie_year is None
        assert team.active is True
        assert team.last_season is None
        assert team.sponsors == []
        assert team.sponsor_provenance == {}
        assert team.org_key == ""
        assert team.sibling_team_ids == []
        assert team.sources == []

    def test_default_list_fields_are_not_shared_between_instances(self):
        a = Team()
        b = Team()

        a.sponsors.append("Qualcomm")
        a.sponsor_provenance["Qualcomm"] = "structured"
        a.sibling_team_ids.append("frc-1622")
        a.sources.append("ftcscout")

        assert b.sponsors == []
        assert b.sponsor_provenance == {}
        assert b.sibling_team_ids == []
        assert b.sources == []

    def test_all_documented_fields_are_settable_via_constructor(self):
        team = Team(
            team_id="ftc-1622",
            league="FTC",
            program="FIRST Tech Challenge",
            number="1622",
            name="Team Spyder",
            organization="Poway High School",
            org_type="school",
            city="Poway",
            postal_code="92064",
            latitude=32.98,
            longitude=-117.04,
            location_precision="school",
            in_region=True,
            website="https://example.org",
            website_status="live",
            organization_website="https://powayusd.com",
            rookie_year=2007,
            active=True,
            last_season=2026,
            sponsors=["BAE Systems", "PTC", "Qualcomm"],
            sponsor_provenance={
                "BAE Systems": "structured",
                "PTC": "structured",
                "Qualcomm": "structured",
            },
            org_key="poway-high-school",
            sibling_team_ids=["frc-1622"],
            sources=["ftcscout"],
        )

        assert team.team_id == "ftc-1622"
        assert team.number == "1622"
        assert team.sponsors == ["BAE Systems", "PTC", "Qualcomm"]
        assert team.sponsor_provenance == {
            "BAE Systems": "structured",
            "PTC": "structured",
            "Qualcomm": "structured",
        }
        assert team.sibling_team_ids == ["frc-1622"]


class TestValidLeagues:
    """Sprint 036 ticket 001: `League` widens to also include the two
    non-robotics competition types ticket 002 migrates
    (`"SCIOLY"`, `"CYBERPATRIOT"`); `VALID_LEAGUES` is derived via
    `get_args()`, the same drift-proof pattern `directory.model.
    VALID_CLUB_TYPES` uses for `ClubType`. Ticket 006 widens it a third
    time to `"MATHCOUNTS"`/`"TARC"`, the two new competition types
    ticket 005's research found a real San Diego roster for."""

    def test_valid_leagues_contains_exactly_the_widened_value_set(self):
        assert VALID_LEAGUES == {
            "FTC",
            "FRC",
            "FLL",
            "VEX",
            "SCIOLY",
            "CYBERPATRIOT",
            "MATHCOUNTS",
            "TARC",
        }

    def test_existing_robotics_leagues_are_still_valid(self):
        assert {"FTC", "FRC", "FLL", "VEX"} <= VALID_LEAGUES


class TestNoEmailField:
    """A structural guarantee (see model.py's module docstring), not
    just an omission to remember -- there must be nowhere on this
    dataclass to put a team's or a coach's email address.
    """

    def test_no_field_named_or_resembling_email_exists(self):
        field_names = {f.name.lower() for f in dataclasses.fields(Team)}

        assert not any("email" in name for name in field_names)

    def test_team_has_no_email_attribute_at_all(self):
        team = Team()

        assert not hasattr(team, "email")
        assert not hasattr(team, "contact_email")
        assert not hasattr(team, "coach_email")
