"""Tests for partner_scrape.teams.sources.ftcscout: the FTCScout REST source.

``tests/fixtures/teams/ftcscout_search.json`` is a real response
captured live from ``GET api.ftcscout.org/rest/v1/teams/search?
region=USCASD`` (2026-08-27) -- all 152 San Diego FTC team records,
unmodified beyond JSON pretty-printing, matching the issue's own
measured count and characteristics (0/152 websites, 58/152
Family/Community, 27 distinct-but-dirty raw city strings, 6 teams
outside San Diego County). ``ftcscout_search_malformed.json`` is
hand-authored to exercise per-record error isolation, matching
``adapters/leaguesync.py``'s test convention.

Every test drives the source through a fixture Fetcher returning these
canned bodies -- no test here opens a real network socket.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef, run
from partner_scrape.teams.sources.ftcscout import (
    DEFAULT_API_BASE,
    DEFAULT_REGION,
    FAMILY_COMMUNITY,
    OUT_OF_REGION_CITIES,
    FTCScoutSource,
    _clean_city,
    _search_url,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"
TEAMS_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "registry"
)

SEARCH_URL = _search_url(DEFAULT_API_BASE, DEFAULT_REGION)


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if the source under test fetches something it shouldn't.
    """

    responses: dict[str, FetchResponse]
    calls: list[tuple[str, dict[str, str] | None]] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append((url, headers))
        return self.responses[url]


def _source(config: dict | None = None) -> SourceConfig:
    return SourceConfig(
        source_id="ftc-sd",
        org_name="FIRST Tech Challenge -- San Diego County",
        adapter_type="ftcscout",
        config=config or {},
    )


def _real_fetcher() -> FixtureFetcher:
    return FixtureFetcher({SEARCH_URL: _response(_read_fixture("ftcscout_search.json"))})


def _extract_real_fixture() -> list[Team]:
    return run(_source(), FTCScoutSource(), _real_fetcher())


class TestDiscover:
    def test_returns_exactly_one_ref_for_the_region_search_endpoint(self):
        source_obj = FTCScoutSource()

        refs = list(source_obj.discover(_source(), fetcher=None))

        assert len(refs) == 1
        assert refs[0].url == SEARCH_URL

    def test_no_fetcher_call_is_made_by_discover(self):
        source_obj = FTCScoutSource()

        class ExplodingFetcher:
            def get(self, url, headers=None):
                raise AssertionError("discover() must not call fetcher.get()")

        source_obj.discover(_source(), ExplodingFetcher())

    def test_config_overrides_api_base_and_region(self):
        source_obj = FTCScoutSource()
        source = _source({"api_base": "https://custom.example.org", "region": "USTXHO"})

        refs = list(source_obj.discover(source, fetcher=None))

        assert refs[0].url == "https://custom.example.org/rest/v1/teams/search?region=USTXHO"


class TestEndToEndCount:
    def test_produces_152_teams_from_the_live_captured_fixture(self):
        # The issue's own measured count -- material drift here means
        # FTCScout's data changed and should fail loudly, not silently
        # shrink the directory.
        teams = _extract_real_fixture()

        assert len(teams) == 152

    def test_every_team_id_is_unique_and_ftc_prefixed(self):
        teams = _extract_real_fixture()

        team_ids = [t.team_id for t in teams]
        assert len(set(team_ids)) == 152
        assert all(tid.startswith("ftc-") for tid in team_ids)

    def test_every_team_has_league_and_program_set(self):
        teams = _extract_real_fixture()

        assert all(t.league == "FTC" for t in teams)
        assert all(t.program == "FIRST Tech Challenge" for t in teams)

    def test_every_team_carries_ftcscout_provenance(self):
        teams = _extract_real_fixture()

        assert all(t.sources == ["ftcscout"] for t in teams)

    def test_no_team_has_a_website_ftcscout_reports_none(self):
        # Measured live: 0/152 records have a non-null website. This
        # source must never fabricate one.
        teams = _extract_real_fixture()

        assert all(t.website == "" for t in teams)


class TestExactSchoolNamedTeam:
    """Team 1622, "Team Spyder" -- a real sponsoring school, real
    sponsors, clean city string. The straightforward case.
    """

    def test_maps_all_documented_fields(self):
        teams = _extract_real_fixture()

        spyder = next(t for t in teams if t.number == 1622)
        assert spyder.team_id == "ftc-1622"
        assert spyder.name == "Team Spyder"
        assert spyder.organization == "Poway High School"
        assert spyder.org_type == "school"
        assert spyder.city == "Poway"
        assert spyder.rookie_year == 2007
        assert spyder.sponsors == ["BAE Systems", "PTC", "Qualcomm"]
        assert spyder.sponsor_provenance == {
            "BAE Systems": "structured",
            "PTC": "structured",
            "Qualcomm": "structured",
        }
        assert spyder.in_region is True


class TestFamilyCommunityTeam:
    """Team 4216, "Rise of Hephaestus" -- FTCScout's schoolName ==
    "Family/Community" sentinel: a home team with no sponsoring school.
    """

    def test_maps_to_empty_organization_and_family_community_org_type(self):
        teams = _extract_real_fixture()

        rise = next(t for t in teams if t.number == 4216)
        assert rise.organization == ""
        assert rise.org_type == "family_community"
        assert rise.city == "Santee"
        assert rise.sponsors == [
            "RISE-Robotics Inspiring Science and Engineering",
            "DoD STEM",
        ]

    def test_58_teams_in_the_fixture_are_family_community(self):
        teams = _extract_real_fixture()

        family_community = [t for t in teams if t.org_type == "family_community"]
        assert len(family_community) == 58
        assert all(t.organization == "" for t in family_community)

    def test_family_community_sentinel_is_never_leaked_into_organization(self):
        teams = _extract_real_fixture()

        assert all(t.organization != FAMILY_COMMUNITY for t in teams)


class TestDirtyCityNormalization:
    """Measured live: 27 raw distinct city strings for 24 real places --
    trailing whitespace and inconsistent casing. Team 3650 has a
    trailing-space city; 8097 and 31800 have all-lowercase cities.
    """

    def test_trailing_whitespace_city_is_stripped(self):
        teams = _extract_real_fixture()

        limited_liability = next(t for t in teams if t.number == 3650)
        assert limited_liability.city == "La Jolla"

    def test_lowercase_carlsbad_is_title_cased(self):
        teams = _extract_real_fixture()

        botcats = next(t for t in teams if t.number == 8097)
        assert botcats.city == "Carlsbad"

    def test_lowercase_san_diego_is_title_cased(self):
        teams = _extract_real_fixture()

        control_alt_defeat = next(t for t in teams if t.number == 31800)
        assert control_alt_defeat.city == "San Diego"

    def test_dirty_and_clean_variants_collapse_to_one_city_string(self):
        teams = _extract_real_fixture()

        san_diego_variants = {t.city for t in teams if t.city.lower() == "san diego"}
        carlsbad_variants = {t.city for t in teams if t.city.lower() == "carlsbad"}
        assert san_diego_variants == {"San Diego"}
        assert carlsbad_variants == {"Carlsbad"}

    def test_clean_city_helper_handles_none_and_empty(self):
        assert _clean_city(None) == ""
        assert _clean_city("") == ""
        assert _clean_city("   ") == ""


class TestOutOfRegionTeams:
    """Ensenada (Mexico), San Clemente, San Antonio, Louisville, Agoura
    Hills -- 6 of 152 teams outside San Diego County. Per the issue:
    flagged with in_region=False, never dropped.
    """

    def test_ensenada_teams_are_flagged_out_of_region_not_dropped(self):
        teams = _extract_real_fixture()

        ensenada_teams = [t for t in teams if t.city == "Ensenada"]
        assert len(ensenada_teams) == 2
        assert all(t.in_region is False for t in ensenada_teams)
        # Confirmed present in the output, not silently excluded.
        assert {t.number for t in ensenada_teams} == {9164, 10793}

    def test_exactly_6_teams_are_flagged_out_of_region(self):
        teams = _extract_real_fixture()

        out_of_region = [t for t in teams if t.in_region is False]
        assert len(out_of_region) == 6
        assert {t.city for t in out_of_region} == OUT_OF_REGION_CITIES

    def test_146_teams_remain_in_region(self):
        teams = _extract_real_fixture()

        assert len([t for t in teams if t.in_region is True]) == 146

    def test_san_diego_county_teams_are_not_flagged(self):
        teams = _extract_real_fixture()

        spyder = next(t for t in teams if t.number == 1622)
        assert spyder.in_region is True


class TestSponsors:
    def test_49_teams_have_a_populated_sponsors_list(self):
        teams = _extract_real_fixture()

        with_sponsors = [t for t in teams if t.sponsors]
        assert len(with_sponsors) == 49

    def test_teams_with_no_sponsors_get_an_empty_list_not_none(self):
        teams = _extract_real_fixture()

        rancho = next(t for t in teams if t.number == 7696)  # "Singularity"
        assert rancho.sponsors == []

    def test_every_sponsor_carries_structured_provenance(self):
        # Sprint 013 ticket 005: every sponsor this structured API
        # reports is "structured" from the moment it is created -- not
        # backfilled by a later pipeline stage.
        teams = _extract_real_fixture()

        with_sponsors = [t for t in teams if t.sponsors]
        assert with_sponsors  # sanity: the fixture actually exercises this
        for team in with_sponsors:
            assert set(team.sponsor_provenance) == set(team.sponsors)
            assert all(provenance == "structured" for provenance in team.sponsor_provenance.values())

    def test_teams_with_no_sponsors_get_an_empty_provenance_dict(self):
        teams = _extract_real_fixture()

        rancho = next(t for t in teams if t.number == 7696)  # "Singularity"
        assert rancho.sponsor_provenance == {}


class TestMalformedRecordIsolation:
    def test_records_missing_number_or_name_are_skipped_valid_ones_survive(self):
        fetcher = FixtureFetcher(
            {SEARCH_URL: _response(_read_fixture("ftcscout_search_malformed.json"))}
        )

        teams = run(_source(), FTCScoutSource(), fetcher)

        names = {t.name for t in teams}
        assert names == {"Team Spyder", "Rise of Hephaestus"}
        assert len(teams) == 2


class TestExtractRobustness:
    def test_non_200_status_returns_no_teams_without_raising(self):
        source_obj = FTCScoutSource()
        raw = RawTeamResponse(ref=TeamRef(url=SEARCH_URL), status=500, body="")

        assert list(source_obj.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_teams_without_raising(self):
        source_obj = FTCScoutSource()
        raw = RawTeamResponse(ref=TeamRef(url=SEARCH_URL), status=200, body="not json {")

        assert list(source_obj.extract(raw, _source())) == []

    def test_non_list_json_shape_returns_no_teams_without_raising(self):
        source_obj = FTCScoutSource()
        raw = RawTeamResponse(
            ref=TeamRef(url=SEARCH_URL), status=200, body='{"unexpected": "shape"}'
        )

        assert list(source_obj.extract(raw, _source())) == []


class TestFetch:
    def test_fetch_issues_a_plain_get_with_no_auth_headers(self):
        source_obj = FTCScoutSource()
        fetcher = _real_fetcher()

        source_obj.fetch(TeamRef(url=SEARCH_URL), fetcher)

        assert fetcher.calls == [(SEARCH_URL, None)]


class TestRegistryConfig:
    """AC: partner_scrape/teams/registry/ftc-sd.toml registers the
    FTCScout source, reusing registry.schema.SourceConfig /
    registry.loader.load_active_sources verbatim (no new schema).
    """

    def test_ftc_sd_toml_loads_via_load_active_sources(self):
        # Ticket 011-003 added a sibling `frc-sd.toml` to this same
        # directory, so this asserts the ftc-sd entry specifically
        # rather than assuming it is the directory's only file --
        # matching test_sources_tba.py::TestRegistryConfig's precedent.
        sources = load_active_sources(TEAMS_REGISTRY_DIR)
        source = next(s for s in sources if s.source_id == "ftc-sd")

        assert source.adapter_type == "ftcscout"
        assert source.enabled is True
        assert source.config.get("region") == DEFAULT_REGION

    def test_loaded_source_config_drives_discover_to_the_real_search_url(self):
        sources = load_active_sources(TEAMS_REGISTRY_DIR)
        source = next(s for s in sources if s.source_id == "ftc-sd")
        source_obj = FTCScoutSource()

        refs = list(source_obj.discover(source, fetcher=None))

        assert refs[0].url == SEARCH_URL
