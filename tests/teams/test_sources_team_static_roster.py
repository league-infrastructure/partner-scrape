"""Tests for partner_scrape.teams.sources.team_static_roster: the
generic curated STEM-competition-team static-roster TeamSource.

Sprint 036 ticket 001 adds this module (and this test module) as the
`teams/`-side counterpart to `directory.sources.club_static_roster`'s
sprint-032 generalization -- see `teams/DESIGN.md`'s sprint 036
Revision. Ticket 001's own scope is "mechanism only, no new registry
entry or roster data file" (ticket 002 migrates the first real content
through it), so unlike `test_sources_club_static_roster.py`'s "drive
against the real committed roster" precedent, every test here drives
`TeamStaticRosterSource` against hand-authored fixture content -- there
is no real `team_static_roster` registry entry yet for this ticket to
point at.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef, run
from partner_scrape.teams.sources.team_static_roster import (
    DEFAULT_DATA_DIR,
    DEFAULT_ROSTER_PATH,
    TeamStaticRosterSource,
    _extract_one,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"

_GOOD_ROSTER_BODY = (
    "league\tprogram\tnumber\tname\torganization\torg_type\tcity\tpostal_code\twebsite\n"
    "SCIOLY\tScience Olympiad\tcanyon-crest-academy\t"
    "Science Olympiad Team at Canyon Crest Academy\tCanyon Crest Academy\tschool\t"
    "San Diego\t92130\t\n"
    "CYBERPATRIOT\tCyberPatriot\tdel-norte-high\t"
    "CyberPatriot Team at Del Norte High School\tDel Norte High School\tschool\t"
    "San Diego\t92127\thttps://cyberaegis.tech\n"
)


def _fixture_source(source_id: str = "test-roster", roster_path: str | None = None) -> SourceConfig:
    return SourceConfig(
        source_id=source_id,
        org_name="Test Roster",
        adapter_type="team_static_roster",
        config={"roster_path": roster_path} if roster_path else {},
    )


class _NeverCalledFetcher:
    """`Fetcher` double that raises on any call -- proves
    `TeamStaticRosterSource` never touches it, exercised through the
    full `sources.base.run()` chain, matching
    `test_sources_club_static_roster.py`'s / `test_sources_static_
    roster.py`'s identical precedent."""

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        raise AssertionError("TeamStaticRosterSource must never call the injected Fetcher")


class TestNeverTouchesFetcher:
    def test_run_never_calls_fetcher_get(self, tmp_path):
        roster = tmp_path / "roster.tsv"
        roster.write_text(_GOOD_ROSTER_BODY, encoding="utf-8")

        teams = run(
            _fixture_source(roster_path=str(roster)),
            TeamStaticRosterSource(),
            _NeverCalledFetcher(),
        )

        assert len(teams) == 2


class TestDiscover:
    def test_discover_returns_a_local_path_not_a_url(self):
        refs = TeamStaticRosterSource().discover(_fixture_source(), _NeverCalledFetcher())

        assert len(refs) == 1
        assert refs[0].url == str(DEFAULT_ROSTER_PATH)
        assert not refs[0].url.startswith("http")

    def test_discover_falls_back_to_default_roster_path_when_config_omits_it(self):
        source = SourceConfig(
            source_id="test-roster",
            org_name="Test Roster",
            adapter_type="team_static_roster",
            config={},
        )

        refs = TeamStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_ROSTER_PATH)

    def test_discover_resolves_a_relative_roster_path_against_data_dir(self):
        source = _fixture_source(roster_path="science-olympiad-sd.tsv")

        refs = TeamStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_DATA_DIR / "science-olympiad-sd.tsv")

    def test_discover_leaves_an_absolute_roster_path_untouched(self, tmp_path):
        absolute = tmp_path / "custom-roster.tsv"
        source = _fixture_source(roster_path=str(absolute))

        refs = TeamStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(absolute)


class TestFetch:
    def test_fetch_reads_the_file_directly_ignoring_fetcher(self, tmp_path):
        roster = tmp_path / "roster.tsv"
        roster.write_text(_GOOD_ROSTER_BODY, encoding="utf-8")
        ref = TeamRef(url=str(roster))

        raw = TeamStaticRosterSource().fetch(ref, _NeverCalledFetcher())

        assert raw.status == 200
        assert "canyon-crest-academy" in raw.body

    def test_fetch_raises_for_a_missing_file(self, tmp_path):
        ref = TeamRef(url=str(tmp_path / "does-not-exist.tsv"))

        with pytest.raises(OSError):
            TeamStaticRosterSource().fetch(ref, _NeverCalledFetcher())


class TestExtract:
    def _teams(self, source_id: str = "test-roster"):
        ref = TeamRef(url="fixture://roster")
        raw = RawTeamResponse(ref=ref, status=200, body=_GOOD_ROSTER_BODY)
        return list(TeamStaticRosterSource().extract(raw, _fixture_source(source_id=source_id)))

    def test_extracts_one_team_per_row(self):
        assert len(self._teams()) == 2

    def test_team_id_is_built_from_league_and_number_slug(self):
        teams = self._teams()

        assert {t.team_id for t in teams} == {"scioly-canyon-crest-academy", "cyberpatriot-del-norte-high"}

    def test_league_and_program_are_carried_through(self):
        teams = {t.team_id: t for t in self._teams()}

        sciolympiad = teams["scioly-canyon-crest-academy"]
        assert sciolympiad.league == "SCIOLY"
        assert sciolympiad.program == "Science Olympiad"
        assert sciolympiad.number == "canyon-crest-academy"

    def test_organization_city_postal_code_and_website_are_carried_through(self):
        teams = {t.team_id: t for t in self._teams()}

        cyberpatriot = teams["cyberpatriot-del-norte-high"]
        assert cyberpatriot.organization == "Del Norte High School"
        assert cyberpatriot.org_type == "school"
        assert cyberpatriot.city == "San Diego"
        assert cyberpatriot.postal_code == "92127"
        assert cyberpatriot.website == "https://cyberaegis.tech"

    def test_this_source_never_geocodes(self):
        for team in self._teams():
            assert team.latitude is None
            assert team.longitude is None
            assert team.location_precision == "none"
            assert team.matched_name == ""
            assert team.needs_review is False
            assert team.organization_website == ""


class TestProvenance:
    """AC: two registry entries with different `source_id`s produce
    distinguishable `Team.sources`."""

    def test_two_different_registry_entries_produce_two_different_provenance_values(self):
        ref = TeamRef(url="fixture://roster")
        raw = RawTeamResponse(ref=ref, status=200, body=_GOOD_ROSTER_BODY)

        teams_a = list(
            TeamStaticRosterSource().extract(raw, _fixture_source(source_id="science-olympiad-sd"))
        )
        teams_b = list(
            TeamStaticRosterSource().extract(raw, _fixture_source(source_id="cyberpatriot-sd"))
        )

        assert teams_a[0].sources == ["science-olympiad-sd"]
        assert teams_b[0].sources == ["cyberpatriot-sd"]
        assert teams_a[0].sources != teams_b[0].sources


class TestMalformedEntryIsolation:
    """`team_roster_malformed.tsv` (hand-authored) carries four broken
    rows plus one good row, matching `hack_club_malformed.tsv`'s /
    `fll_roster_malformed.tsv`'s per-record isolation precedent."""

    def test_malformed_rows_are_skipped_and_logged_not_raised(self, caplog):
        body = (FIXTURES_DIR / "team_roster_malformed.tsv").read_text()
        ref = TeamRef(url="team_roster_malformed.tsv")
        raw = RawTeamResponse(ref=ref, status=200, body=body)

        teams = TeamStaticRosterSource().extract(raw, _fixture_source())

        assert len(teams) == 1
        assert teams[0].team_id == "scioly-good-school"
        assert teams[0].name == "Team at Good School"


class TestExtractOne:
    def test_missing_number_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable number or name"):
            _extract_one({"league": "SCIOLY", "name": "X"}, "test-source")

    def test_missing_name_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable number or name"):
            _extract_one({"league": "SCIOLY", "number": "x"}, "test-source")

    def test_unrecognized_league_raises_value_error(self):
        with pytest.raises(ValueError, match="unrecognized league"):
            _extract_one({"league": "NOTALEAGUE", "number": "x", "name": "X"}, "test-source")

    def test_sources_field_carries_the_given_source_name(self):
        team = _extract_one(
            {"league": "SCIOLY", "number": "x", "name": "X"}, "science-olympiad-sd"
        )

        assert team.sources == ["science-olympiad-sd"]

    def test_never_sets_geocoding_fields(self):
        team = _extract_one({"league": "SCIOLY", "number": "x", "name": "X"}, "test-source")

        assert team.latitude is None
        assert team.longitude is None
        assert team.location_precision == "none"
