"""Tests for partner_scrape.teams.sources.robotevents: the VEX
RobotEvents ``TeamSource``.

``tests/fixtures/teams/robotevents_teams_page{0,1}.json`` are
hand-authored, not live-captured -- no ``ROBOTEVENTS_KEY`` was available
during this ticket's execution (see ``sources/robotevents.py``'s own
module docstring; confirmed absent from the shell environment, ``.env``,
and every layer under ``config/`` again during this ticket, matching
ticket 004's identical finding). Built directly from RobotEvents' own
published OpenAPI schema (fetched from the open-source ``robotevents``
npm client's generated TypeScript types during this ticket's execution)
and, where possible, from ticket 004's own committed
``tests/fixtures/robotevents/events_page1.json`` program objects
(``{"id": 1, "name": "VEX Robotics Competition", "code": "VRC"}`` /
``{"id": 41, "name": "VEX IQ Robotics Competition", "code": "VIQRC"}``)
for consistency across both tickets' fixtures, not a coincidence.

``robotevents_teams_page0.json`` models six records: a same-organization
alphanumeric-suffix pair (``90210A``/``90210B``, Poway High School --
this ticket's own explicit acceptance criterion, "no team_id collision"),
one VIQRC home team with no organization, one V5RC team outside San
Diego County (Los Angeles -- real noise proving the client-side
allowlist filter is load-bearing, matching
``tests/teams/test_sources_tba.py``'s ``100``/``8353`` noise-record
convention), and one more VIQRC team. ``robotevents_teams_page1.json``
adds a sixth in-county record on a second page, exercising pagination.
``robotevents_teams_malformed.json`` reuses one good record plus two
broken ones (empty ``number``, empty ``team_name``) and one non-dict
array element, matching ``tba_teams_malformed.json``'s convention.

Every test drives the source through a fixture ``Fetcher`` returning
these canned bodies -- no test here opens a real network socket.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape import config
from partner_scrape.config import CredentialError
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.schema import SourceConfig
from partner_scrape.teams.model import Team
from partner_scrape.teams.sources.base import RawTeamResponse, TeamRef, run
from partner_scrape.teams.sources.robotevents import (
    DEFAULT_PER_PAGE,
    SD_COUNTY_CITIES,
    VexTeamSource,
    _auth_headers,
    _clean_city,
    _teams_url,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "teams"
TEAMS_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "registry"
)

API_BASE = config.DEFAULT_ROBOTEVENTS_URL
PROBE_URL = _teams_url(API_BASE, "", page=1, per_page=1)
PAGE1_URL = _teams_url(API_BASE, "", page=1, per_page=DEFAULT_PER_PAGE)
PAGE2_URL = _teams_url(API_BASE, "", page=2, per_page=DEFAULT_PER_PAGE)


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
        source_id="vex-sd",
        org_name="VEX Robotics Competition (V5RC/VIQRC) -- San Diego County",
        adapter_type="robotevents",
        config=config_dict or {},
    )


def _full_fetcher() -> FixtureFetcher:
    page0_body = _read_fixture("robotevents_teams_page0.json")
    return FixtureFetcher(
        {
            # The probe (per_page=1) only needs a parseable meta.last_page
            # -- reusing page0's body is fine, matching
            # tests/test_adapters_robotevents.py's identical convention.
            PROBE_URL: _response(page0_body),
            PAGE1_URL: _response(page0_body),
            PAGE2_URL: _response(_read_fixture("robotevents_teams_page1.json")),
        }
    )


def _extract_real_fixture(monkeypatch) -> list[Team]:
    monkeypatch.setenv("ROBOTEVENTS_KEY", "fixture-test-key")
    return run(_source(), VexTeamSource(), _full_fetcher())


@pytest.fixture(autouse=True)
def _robotevents_key(monkeypatch):
    """Every test in this module gets a valid ROBOTEVENTS_KEY by
    default -- tests that specifically exercise a missing/invalid key
    override this explicitly, matching
    ``tests/teams/test_sources_tba.py``'s identical convention."""
    monkeypatch.setenv("ROBOTEVENTS_KEY", "fixture-test-key")


class TestAuthHeaders:
    def test_builds_bearer_header(self, monkeypatch):
        monkeypatch.setenv("ROBOTEVENTS_KEY", "my-secret-key")
        assert _auth_headers() == {"Authorization": "Bearer my-secret-key"}

    def test_raises_when_key_is_unset(self, monkeypatch):
        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        with pytest.raises(RuntimeError):
            _auth_headers()

    def test_raises_credential_error_specifically_when_key_is_unset(self, monkeypatch):
        # Sprint 023 ticket 001: this propagates
        # config.get_robotevents_api_key()'s own CredentialError, not
        # just any RuntimeError.
        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        with pytest.raises(CredentialError):
            _auth_headers()


class TestDiscover:
    def test_probes_page_one_then_returns_one_ref_per_page(self):
        source_obj = VexTeamSource()
        fetcher = _full_fetcher()

        refs = source_obj.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL, PAGE2_URL]
        assert fetcher.calls[0][0] == PROBE_URL

    def test_probe_includes_auth_header(self):
        source_obj = VexTeamSource()
        fetcher = _full_fetcher()

        source_obj.discover(_source(), fetcher)

        assert fetcher.calls[0][1] == {"Authorization": "Bearer fixture-test-key"}

    def test_missing_key_raises_before_any_fetch(self, monkeypatch):
        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        source_obj = VexTeamSource()
        fetcher = _full_fetcher()

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

        assert fetcher.calls == []  # never even attempted the probe

    def test_missing_key_raises_credential_error_specifically(self, monkeypatch):
        # Sprint 023 ticket 001 AC.
        monkeypatch.delenv("ROBOTEVENTS_KEY", raising=False)
        source_obj = VexTeamSource()
        fetcher = _full_fetcher()

        with pytest.raises(CredentialError):
            source_obj.discover(_source(), fetcher)

    def test_401_status_raises(self):
        source_obj = VexTeamSource()
        fetcher = FixtureFetcher({PROBE_URL: _response("{}", status=401)})

        with pytest.raises(RuntimeError, match="auth failed"):
            source_obj.discover(_source(), fetcher)

    def test_401_status_raises_credential_error_specifically(self):
        # Sprint 023 ticket 001 AC: the 401 branch, and only the 401
        # branch, raises the dedicated CredentialError subclass.
        source_obj = VexTeamSource()
        fetcher = FixtureFetcher({PROBE_URL: _response("{}", status=401)})

        with pytest.raises(CredentialError):
            source_obj.discover(_source(), fetcher)

    def test_non_200_non_401_status_raises(self):
        # Deliberately does NOT degrade to "assume 1 page" the way
        # adapters/robotevents.py's own /events probe does -- matches
        # sources/tba.py's exact isolation contract (this module's own
        # docstring; this ticket's acceptance criteria).
        source_obj = VexTeamSource()
        fetcher = FixtureFetcher({PROBE_URL: _response("", status=500)})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_non_200_non_401_status_raises_plain_runtime_error_not_credential_error(self):
        # Sprint 023 ticket 001 AC: every non-401 probe failure stays a
        # plain RuntimeError, not the new CredentialError subclass.
        source_obj = VexTeamSource()
        fetcher = FixtureFetcher({PROBE_URL: _response("", status=500)})

        with pytest.raises(RuntimeError) as exc_info:
            source_obj.discover(_source(), fetcher)
        assert not isinstance(exc_info.value, CredentialError)

    def test_unparseable_probe_body_raises(self):
        source_obj = VexTeamSource()
        fetcher = FixtureFetcher({PROBE_URL: _response("not json {")})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_unparseable_probe_body_raises_plain_runtime_error_not_credential_error(self):
        source_obj = VexTeamSource()
        fetcher = FixtureFetcher({PROBE_URL: _response("not json {")})

        with pytest.raises(RuntimeError) as exc_info:
            source_obj.discover(_source(), fetcher)
        assert not isinstance(exc_info.value, CredentialError)

    def test_missing_last_page_raises(self):
        source_obj = VexTeamSource()
        fetcher = FixtureFetcher({PROBE_URL: _response('{"meta": {}, "data": []}')})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_missing_last_page_raises_plain_runtime_error_not_credential_error(self):
        source_obj = VexTeamSource()
        fetcher = FixtureFetcher({PROBE_URL: _response('{"meta": {}, "data": []}')})

        with pytest.raises(RuntimeError) as exc_info:
            source_obj.discover(_source(), fetcher)
        assert not isinstance(exc_info.value, CredentialError)

    def test_config_overrides_api_base_and_country(self):
        source_obj = VexTeamSource()
        source = _source({"api_base": "https://custom.example.org", "country": "USA"})
        custom_probe = _teams_url("https://custom.example.org", "USA", page=1, per_page=1)
        custom_page1 = _teams_url("https://custom.example.org", "USA", page=1, per_page=DEFAULT_PER_PAGE)
        fetcher = FixtureFetcher(
            {custom_probe: _response('{"meta": {"last_page": 1}, "data": []}')}
        )

        refs = source_obj.discover(source, fetcher)

        assert refs == [TeamRef(url=custom_page1)]

    def test_config_overrides_per_page(self):
        source_obj = VexTeamSource()
        source = _source({"per_page": 5})
        custom_page1 = _teams_url(API_BASE, "", page=1, per_page=5)
        fetcher = FixtureFetcher(
            {PROBE_URL: _response('{"meta": {"last_page": 1}, "data": []}')}
        )

        refs = source_obj.discover(source, fetcher)

        assert refs == [TeamRef(url=custom_page1)]


class TestFetch:
    def test_fetch_includes_auth_header(self):
        source_obj = VexTeamSource()
        fetcher = _full_fetcher()

        source_obj.fetch(TeamRef(url=PAGE1_URL), fetcher)

        assert fetcher.calls == [(PAGE1_URL, {"Authorization": "Bearer fixture-test-key"})]


class TestAlphanumericSuffixNoCollision:
    """This ticket's own explicit acceptance criterion: a same-
    organization alphanumeric-suffix pair produces two distinct Teams
    with distinct team_ids -- no collision."""

    def test_90210a_and_90210b_are_distinct_teams(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)
        by_id = {t.team_id: t for t in teams}

        assert "vex-90210A" in by_id
        assert "vex-90210B" in by_id
        assert by_id["vex-90210A"] is not by_id["vex-90210B"]
        assert by_id["vex-90210A"].number == "90210A"
        assert by_id["vex-90210B"].number == "90210B"
        assert by_id["vex-90210A"].organization == by_id["vex-90210B"].organization == "Poway High School"

    def test_every_team_id_is_unique_and_vex_prefixed(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        team_ids = [t.team_id for t in teams]
        assert len(set(team_ids)) == len(team_ids)
        assert all(tid.startswith("vex-") for tid in team_ids)


class TestSanDiegoCountyFilter:
    def test_out_of_county_record_is_dropped(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.number != "5555Z" for t in teams)
        assert "Los Angeles" not in {t.city for t in teams}

    def test_every_surviving_team_is_in_san_diego_county(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.city in SD_COUNTY_CITIES for t in teams)

    def test_second_page_contributes_its_in_county_record(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert any(t.number == "6789Y" for t in teams)


class TestProgramDistinguishesV5RCAndVIQRC:
    def test_v5rc_and_viqrc_records_carry_their_own_program_name(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)
        by_number = {t.number: t for t in teams}

        assert by_number["90210A"].program == "VEX Robotics Competition"
        assert by_number["4321X"].program == "VEX IQ Robotics Competition"
        assert by_number["90210A"].league == "VEX"
        assert by_number["4321X"].league == "VEX"

    def test_every_team_carries_robotevents_provenance(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.sources == ["robotevents"] for t in teams)


class TestOrganizationMapping:
    def test_named_organization_maps_to_school_org_type(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)
        aftershock = next(t for t in teams if t.number == "90210A")

        assert aftershock.organization == "Poway High School"
        assert aftershock.org_type == "school"

    def test_empty_organization_maps_to_unknown_org_type(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)
        home_team = next(t for t in teams if t.number == "4321X")

        assert home_team.organization == ""
        assert home_team.org_type == "unknown"


class TestMalformedRecordIsolation:
    def test_records_missing_number_or_team_name_are_skipped_valid_ones_survive(self, monkeypatch):
        monkeypatch.setenv("ROBOTEVENTS_KEY", "fixture-test-key")
        raw = RawTeamResponse(
            ref=TeamRef(url=PAGE1_URL),
            status=200,
            body=_read_fixture("robotevents_teams_malformed.json"),
        )

        teams = list(VexTeamSource().extract(raw, _source()))

        assert len(teams) == 1
        assert teams[0].number == "90210A"

    def test_non_dict_array_element_is_skipped(self, monkeypatch):
        # robotevents_teams_malformed.json's data[] also carries a bare
        # string element -- extract() must not crash on it.
        monkeypatch.setenv("ROBOTEVENTS_KEY", "fixture-test-key")
        raw = RawTeamResponse(
            ref=TeamRef(url=PAGE1_URL),
            status=200,
            body=_read_fixture("robotevents_teams_malformed.json"),
        )

        teams = list(VexTeamSource().extract(raw, _source()))

        assert all(isinstance(t, Team) for t in teams)


class TestExtractRobustness:
    def test_non_200_status_returns_no_teams_without_raising(self):
        raw = RawTeamResponse(ref=TeamRef(url=PAGE1_URL), status=500, body="")
        assert list(VexTeamSource().extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_teams_without_raising(self):
        raw = RawTeamResponse(ref=TeamRef(url=PAGE1_URL), status=200, body="not json {")
        assert list(VexTeamSource().extract(raw, _source())) == []

    def test_non_dict_json_shape_returns_no_teams_without_raising(self):
        raw = RawTeamResponse(ref=TeamRef(url=PAGE1_URL), status=200, body="[1, 2, 3]")
        assert list(VexTeamSource().extract(raw, _source())) == []

    def test_missing_data_array_returns_no_teams_without_raising(self):
        raw = RawTeamResponse(
            ref=TeamRef(url=PAGE1_URL), status=200, body=json.dumps({"meta": {}})
        )
        assert list(VexTeamSource().extract(raw, _source())) == []


class TestCleanCityAndAllowlist:
    def test_clean_city_helper_handles_none_and_empty(self):
        assert _clean_city(None) == ""
        assert _clean_city("") == ""

    def test_clean_city_strips_and_title_cases(self):
        assert _clean_city("  poway ") == "Poway"

    def test_allowlist_includes_poway_and_la_jolla(self):
        assert "Poway" in SD_COUNTY_CITIES
        assert "La Jolla" in SD_COUNTY_CITIES

    def test_allowlist_excludes_los_angeles(self):
        assert "Los Angeles" not in SD_COUNTY_CITIES


class TestRegistryConfig:
    def test_vex_sd_toml_loads_via_load_active_sources(self):
        sources = load_active_sources(TEAMS_REGISTRY_DIR)
        vex_sources = [s for s in sources if s.source_id == "vex-sd"]

        assert len(vex_sources) == 1
        assert vex_sources[0].adapter_type == "robotevents"

    def test_loaded_source_config_drives_discover_to_the_real_teams_url(self, monkeypatch):
        # An end-to-end sanity check that the committed TOML's config
        # (no api_base/country override) really does resolve through
        # config.get_robotevents_url() the way discover() assumes --
        # matches tests/teams/test_sources_tba.py's identical convention.
        monkeypatch.setenv("ROBOTEVENTS_KEY", "fixture-test-key")
        sources = load_active_sources(TEAMS_REGISTRY_DIR)
        vex_source = next(s for s in sources if s.source_id == "vex-sd")
        fetcher = FixtureFetcher(
            {PROBE_URL: _response('{"meta": {"last_page": 1}, "data": []}')}
        )

        refs = VexTeamSource().discover(vex_source, fetcher)

        assert refs == [TeamRef(url=PAGE1_URL)]
