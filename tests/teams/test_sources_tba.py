"""Tests for partner_scrape.teams.sources.tba: The Blue Alliance source.

``tests/fixtures/teams/tba_status.json`` + ``tba_teams_page0.json`` +
``tba_teams_page1.json`` are a hand-authored (not live-captured -- no
network access during this ticket's build) but realistic-scale corpus:
``max_team_page = 1`` (2 pages), page 0 carries the issue's measured 59
San-Diego-County FRC records (built from this project's own historical
FRC roster, ``data/robot-teams.json``, plus a small synthetic tail --
see ``gen_tba_fixture.py``'s comments for provenance) plus a couple of
CA-but-not-San-Diego noise records, and page 1 is entirely
out-of-state/international noise -- so both the state_prov filter and
the San Diego County city allowlist are exercised on real page
boundaries. ``tba_teams_malformed.json`` is small and hand-authored
(mirroring ``ftcscout_search_malformed.json``'s convention) to exercise
per-record error isolation.

Every test drives the source through a fixture Fetcher returning these
canned bodies -- no test here opens a real network socket.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape import config
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef, run
from partner_scrape.teams.sources.tba import (
    SD_COUNTY_CITIES,
    TBASource,
    _auth_headers,
    _clean_city,
    _status_url,
    _teams_page_url,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"
TEAMS_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "registry"
)

STATUS_URL = _status_url(config.DEFAULT_TBA_URL)
PAGE0_URL = _teams_page_url(config.DEFAULT_TBA_URL, 0)
PAGE1_URL = _teams_page_url(config.DEFAULT_TBA_URL, 1)


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


def _source(config_dict: dict | None = None) -> SourceConfig:
    return SourceConfig(
        source_id="frc-sd",
        org_name="FIRST Robotics Competition -- San Diego County",
        adapter_type="tba",
        config=config_dict or {},
    )


def _full_fetcher() -> FixtureFetcher:
    return FixtureFetcher(
        {
            STATUS_URL: _response(_read_fixture("tba_status.json")),
            PAGE0_URL: _response(_read_fixture("tba_teams_page0.json")),
            PAGE1_URL: _response(_read_fixture("tba_teams_page1.json")),
        }
    )


def _extract_real_fixture(monkeypatch) -> list[Team]:
    monkeypatch.setenv("TBA_KEY", "fixture-test-key")
    return run(_source(), TBASource(), _full_fetcher())


@pytest.fixture(autouse=True)
def _tba_key(monkeypatch):
    """Every test in this module gets a valid TBA_KEY by default --
    tests that specifically exercise a missing/invalid key override
    this explicitly."""
    monkeypatch.setenv("TBA_KEY", "fixture-test-key")


class TestAuthHeaders:
    def test_builds_x_tba_auth_key_header(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", "my-secret-key")
        assert _auth_headers() == {"X-TBA-Auth-Key": "my-secret-key"}

    def test_raises_when_key_is_unset(self, monkeypatch):
        monkeypatch.delenv("TBA_KEY", raising=False)
        with pytest.raises(RuntimeError):
            _auth_headers()


class TestDiscover:
    def test_probes_status_then_returns_one_ref_per_page(self):
        source_obj = TBASource()
        fetcher = _full_fetcher()

        refs = source_obj.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE0_URL, PAGE1_URL]
        assert fetcher.calls[0][0] == STATUS_URL

    def test_status_probe_includes_auth_header(self):
        source_obj = TBASource()
        fetcher = _full_fetcher()

        source_obj.discover(_source(), fetcher)

        assert fetcher.calls[0][1] == {"X-TBA-Auth-Key": "fixture-test-key"}

    def test_missing_key_raises_before_any_fetch(self, monkeypatch):
        monkeypatch.delenv("TBA_KEY", raising=False)
        source_obj = TBASource()
        fetcher = _full_fetcher()

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

        assert fetcher.calls == []  # never even attempted the status probe

    def test_401_status_raises(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("{}", status=401)})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_non_200_non_401_status_raises(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("", status=500)})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_unparseable_status_body_raises(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("not json {")})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_missing_max_team_page_raises(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response('{"current_season": 2026}')})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_config_overrides_api_base(self):
        source_obj = TBASource()
        source = _source({"api_base": "https://custom.example.org"})
        fetcher = FixtureFetcher(
            {"https://custom.example.org/api/v3/status": _response('{"max_team_page": 0}')}
        )

        refs = source_obj.discover(source, fetcher)

        assert refs == [TeamRef(url="https://custom.example.org/api/v3/teams/0")]


class TestFetch:
    def test_fetch_includes_auth_header(self):
        source_obj = TBASource()
        fetcher = _full_fetcher()

        source_obj.fetch(TeamRef(url=PAGE0_URL), fetcher)

        assert fetcher.calls == [(PAGE0_URL, {"X-TBA-Auth-Key": "fixture-test-key"})]


class TestEndToEndCount:
    def test_produces_59_san_diego_county_teams(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert len(teams) == 59

    def test_every_team_id_is_unique_and_frc_prefixed(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        team_ids = [t.team_id for t in teams]
        assert len(set(team_ids)) == 59
        assert all(tid.startswith("frc-") for tid in team_ids)

    def test_every_team_has_league_and_program_set(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.league == "FRC" for t in teams)
        assert all(t.program == "FIRST Robotics Competition" for t in teams)

    def test_every_team_carries_tba_provenance(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.sources == ["tba"] for t in teams)

    def test_measured_field_coverage(self, monkeypatch):
        # The issue's own measured coverage of the 59 SD-county FRC
        # teams: website 43/59, postal_code 49/59, school_name 54/59,
        # rookie_year 59/59, nickname (Team.name) 59/59.
        teams = _extract_real_fixture(monkeypatch)

        assert sum(1 for t in teams if t.website) == 43
        assert sum(1 for t in teams if t.postal_code) == 49
        assert sum(1 for t in teams if t.organization) == 54
        assert sum(1 for t in teams if t.rookie_year is not None) == 59
        assert sum(1 for t in teams if t.name) == 59


class TestCaAndSanDiegoCountyFilter:
    def test_non_california_records_are_dropped(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.number not in (300, 301, 302, 303) for t in teams)

    def test_california_but_not_san_diego_records_are_dropped(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.number not in (100, 200) for t in teams)

    def test_out_of_state_page_contributes_zero_teams(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = FixtureFetcher(
            {PAGE1_URL: _response(_read_fixture("tba_teams_page1.json"))}
        )
        source_obj = TBASource()

        raw = source_obj.fetch(TeamRef(url=PAGE1_URL), fetcher)
        teams = list(source_obj.extract(raw, _source()))

        assert teams == []


class TestExactSchoolNamedTeam:
    """Team 1622, "Team Spyder" -- Poway High School. Real historical
    data (data/robot-teams.json), and the same team number FTC 1622
    ("Team Spyder", also Poway High School) uses -- proving this
    source's extraction is correct independent of any cross-league
    linking, which is teams.merge's job, not this source's.
    """

    def test_maps_documented_fields(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        spyder = next(t for t in teams if t.number == 1622)
        assert spyder.team_id == "frc-1622"
        assert spyder.name == "Team Spyder"
        assert spyder.organization == "Poway High School"
        assert spyder.org_type == "school"
        assert spyder.city == "Poway"
        assert spyder.rookie_year == 2005
        assert spyder.website == "https://teamspyder.org"


class TestUnknownOrganizationTeam:
    """A community/no-school FRC team (no TBA ``Family/Community``
    sentinel exists -- TBA simply reports an empty ``school_name``) --
    org_type "unknown", organization "", the same "never group" bucket
    teams.merge.py gives FTCScout's Family/Community sentinel."""

    def test_empty_school_name_maps_to_empty_organization(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        quantum_leap = next(t for t in teams if t.number == 4444)
        assert quantum_leap.organization == ""
        assert quantum_leap.org_type == "unknown"


class TestTbaIsNotAGeocodingSource:
    """TBA's lat/lng/address/location_name/gmaps_place_id are
    documented in its own OpenAPI spec as "Will be NULL, for future
    development" -- confirmed NULL for all 59 SD teams. This source
    must never read them, present-but-null or otherwise; Team.latitude/
    longitude stay at their dataclass default (None) here."""

    def test_present_but_null_lat_lng_never_populates_team_coordinates(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.latitude is None for t in teams)
        assert all(t.longitude is None for t in teams)
        assert all(t.location_precision == "none" for t in teams)

    def test_raw_fixture_records_do_carry_explicit_null_lat_lng_fields(self):
        # Sanity check on the fixture itself: this test's point only
        # holds if the raw JSON actually has lat/lng present-but-null
        # (not merely absent) -- otherwise the extraction test above
        # would pass trivially.
        page0 = json.loads(_read_fixture("tba_teams_page0.json"))
        assert all("lat" in record and record["lat"] is None for record in page0)
        assert all("lng" in record and record["lng"] is None for record in page0)


class TestMalformedRecordIsolation:
    def test_records_missing_team_number_are_skipped_valid_ones_survive(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = FixtureFetcher(
            {
                STATUS_URL: _response('{"max_team_page": 0}'),
                PAGE0_URL: _response(_read_fixture("tba_teams_malformed.json")),
            }
        )

        teams = run(_source(), TBASource(), fetcher)

        numbers = {t.number for t in teams}
        assert numbers == {1622, 2827}
        assert len(teams) == 2


class TestExtractRobustness:
    def test_non_200_status_returns_no_teams_without_raising(self):
        source_obj = TBASource()
        raw = RawTeamResponse(ref=TeamRef(url=PAGE0_URL), status=500, body="")

        assert list(source_obj.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_teams_without_raising(self):
        source_obj = TBASource()
        raw = RawTeamResponse(ref=TeamRef(url=PAGE0_URL), status=200, body="not json {")

        assert list(source_obj.extract(raw, _source())) == []

    def test_non_list_json_shape_returns_no_teams_without_raising(self):
        source_obj = TBASource()
        raw = RawTeamResponse(
            ref=TeamRef(url=PAGE0_URL), status=200, body='{"unexpected": "shape"}'
        )

        assert list(source_obj.extract(raw, _source())) == []


class TestCleanCityAndAllowlist:
    def test_clean_city_helper_handles_none_and_empty(self):
        assert _clean_city(None) == ""
        assert _clean_city("") == ""
        assert _clean_city("   ") == ""

    def test_clean_city_strips_and_title_cases(self):
        assert _clean_city("  san diego ") == "San Diego"

    def test_allowlist_includes_poway_and_la_jolla(self):
        assert "Poway" in SD_COUNTY_CITIES
        assert "La Jolla" in SD_COUNTY_CITIES

    def test_allowlist_excludes_los_angeles(self):
        assert "Los Angeles" not in SD_COUNTY_CITIES


class TestRegistryConfig:
    """AC: partner_scrape/teams/registry/frc-sd.toml registers the TBA
    source, reusing registry.schema.SourceConfig /
    registry.loader.load_active_sources verbatim (no new schema).
    """

    def test_frc_sd_toml_loads_via_load_active_sources(self):
        sources = load_active_sources(TEAMS_REGISTRY_DIR)
        frc_sd = next(s for s in sources if s.source_id == "frc-sd")

        assert frc_sd.adapter_type == "tba"
        assert frc_sd.enabled is True

    def test_loaded_source_config_drives_discover_to_the_real_status_url(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        source = next(
            s for s in load_active_sources(TEAMS_REGISTRY_DIR) if s.source_id == "frc-sd"
        )
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response('{"max_team_page": 0}')})

        refs = source_obj.discover(source, fetcher)

        assert fetcher.calls[0][0] == STATUS_URL
        assert refs == [TeamRef(url=PAGE0_URL)]
