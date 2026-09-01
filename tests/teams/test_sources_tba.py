"""Tests for partner_scrape.teams.sources.tba: The Blue Alliance source.

``tests/fixtures/teams/tba_teams_page0.json`` and
``tba_teams_page1.json`` are **verbatim, live-captured** TBA
``/api/v3/teams/{page}`` records (captured 2026-08-28, re-fetched
directly against ``https://www.thebluealliance.com/api/v3`` -- see
this ticket's own commit for the capture script), not hand-authored --
ticket 011-003's original fixture was hand-authored with every record
using the ``"CA"`` abbreviation, which is exactly why its test suite
never caught the defect this reopened ticket fixes: TBA's real API
mostly reports the *full* state name (``"California"``), and the
original filter only ever matched the bare abbreviation. Ticket
011-003's original fixture also simulated the issue's then-measured 59
San-Diego-County records; the real total is **78** (see
``sources/tba.py``'s module docstring), and this reopened ticket
deliberately captures a small, curated *subset* of real records rather
than all 78 -- the point of this corpus is exercising the extraction
and filter logic against genuine API output, not asserting an exact
production count (that belongs to a live run, not a fixture).

Nine records were selected from the live capture into
``tba_teams_page0.json``:

- ``1622`` (Poway, "California") and ``3128`` (San Diego/Canyon Crest
  Academy, "California") -- both real dual-program schools whose FTC
  counterpart also appears in ``ftcscout_search.json``, so
  ``tests/teams/test_pipeline.py``'s cross-league merge tests still
  exercise a genuine link.
- ``2984`` (La Jolla) and ``2827`` (Coronado) -- two more real,
  currently-competing "California"-labeled records.
- ``2029`` (Ramona, "California", ``school_name`` null) -- a real
  record proving the "California" full-name form and the
  no-reported-school/``org_type: "unknown"`` case are independent of
  each other.
- ``1125`` (San Diego) and ``5488`` (Chula Vista) -- both real,
  currently-``state_prov: "CA"`` (abbreviated) records. **These are
  this ticket's regression fixture**: under the pre-fix filter
  (``state_prov != "CA"``, no normalization) these already passed
  coincidentally, so the real regression proof is the "California"
  records above being accepted, not these -- both groups are asserted
  together in ``TestStateNameNormalization`` below.
- ``100`` (Woodside, "California", not a San Diego County city) --
  real noise proving the city allowlist still excludes a same-state
  team outside the county.
- ``8353`` (**San Diego, Texas** -- a real Texas town that happens to
  share San Diego's own city name, "San Diego High School" and all) --
  real noise proving the state check is still load-bearing: dropping
  it and filtering on city alone would wrongly admit this team.

``tba_teams_page1.json`` is, as in the original fixture, entirely
out-of-state/international noise: ``1554`` (Oceanside, **New York**)
and ``3679``/``3723`` (San Marcos, TX / Spring Valley, MN) are three
more real same-city-name collisions (proving the state check's
necessity is not a one-off), plus ``188`` (Toronto, Ontario, Canada)
and ``118`` (Houston, TX, the real "Robonauts") as plain non-colliding
noise. ``tests/teams/test_pipeline.py`` and this module both still see
``tba_status.json``'s ``max_team_page: 1`` (2 pages) -- a deliberately
small, synthetic pagination count kept from the original fixture so
this remains a *representative* corpus, not all 24 of TBA's real
pages; only the pagination metadata is synthetic, every team record
within the two pages is real. ``tba_teams_malformed.json`` reuses two
of the same real records (``1622``, ``2827``) plus one
still-hand-authored broken record (no ``team_number`` -- there is no
way to "capture" a malformed record from a well-formed API), matching
``ftcscout_search_malformed.json``'s convention.

Every test drives the source through a fixture Fetcher returning these
canned bodies -- no test here opens a real network socket.
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
from partner_scrape.teams.sources.tba import (
    SD_COUNTY_CITIES,
    TBASource,
    _auth_headers,
    _clean_city,
    _normalize_state,
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

    def test_raises_credential_error_specifically_when_key_is_unset(self, monkeypatch):
        # Sprint 023 ticket 001: this propagates config.get_tba_api_key()'s
        # own CredentialError, not just any RuntimeError.
        monkeypatch.delenv("TBA_KEY", raising=False)
        with pytest.raises(CredentialError):
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

    def test_missing_key_raises_credential_error_specifically(self, monkeypatch):
        # Sprint 023 ticket 001 AC.
        monkeypatch.delenv("TBA_KEY", raising=False)
        source_obj = TBASource()
        fetcher = _full_fetcher()

        with pytest.raises(CredentialError):
            source_obj.discover(_source(), fetcher)

    def test_401_status_raises(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("{}", status=401)})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_401_status_raises_credential_error_specifically(self):
        # Sprint 023 ticket 001 AC: the 401 branch, and only the 401
        # branch, raises the dedicated CredentialError subclass.
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("{}", status=401)})

        with pytest.raises(CredentialError):
            source_obj.discover(_source(), fetcher)

    def test_non_200_non_401_status_raises(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("", status=500)})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_non_200_non_401_status_raises_plain_runtime_error_not_credential_error(self):
        # Sprint 023 ticket 001 AC: every non-401 probe failure stays a
        # plain RuntimeError, not the new CredentialError subclass.
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("", status=500)})

        with pytest.raises(RuntimeError) as exc_info:
            source_obj.discover(_source(), fetcher)
        assert not isinstance(exc_info.value, CredentialError)

    def test_unparseable_status_body_raises(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("not json {")})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_unparseable_status_body_raises_plain_runtime_error_not_credential_error(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response("not json {")})

        with pytest.raises(RuntimeError) as exc_info:
            source_obj.discover(_source(), fetcher)
        assert not isinstance(exc_info.value, CredentialError)

    def test_missing_max_team_page_raises(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response('{"current_season": 2026}')})

        with pytest.raises(RuntimeError):
            source_obj.discover(_source(), fetcher)

    def test_missing_max_team_page_raises_plain_runtime_error_not_credential_error(self):
        source_obj = TBASource()
        fetcher = FixtureFetcher({STATUS_URL: _response('{"current_season": 2026}')})

        with pytest.raises(RuntimeError) as exc_info:
            source_obj.discover(_source(), fetcher)
        assert not isinstance(exc_info.value, CredentialError)

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
    """This fixture is a deliberately small, curated subset of the real
    78 San-Diego-County FRC records (see this module's own docstring
    and ``sources/tba.py``'s) -- 7 of the 9 real records in
    ``tba_teams_page0.json`` pass the filter (``100`` and ``8353`` are
    real noise, dropped by design; see ``TestCaAndSanDiegoCountyFilter``),
    and all 5 records in ``tba_teams_page1.json`` are noise. These
    counts describe this fixture's own small corpus, not a production
    total."""

    def test_produces_seven_san_diego_county_teams(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert len(teams) == 7

    def test_every_team_id_is_unique_and_frc_prefixed(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        team_ids = [t.team_id for t in teams]
        assert len(set(team_ids)) == 7
        assert all(tid.startswith("frc-") for tid in team_ids)

    def test_every_team_has_league_and_program_set(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.league == "FRC" for t in teams)
        assert all(t.program == "FIRST Robotics Competition" for t in teams)

    def test_every_team_carries_tba_provenance(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.sources == ["tba"] for t in teams)

    def test_measured_field_coverage(self, monkeypatch):
        # Measured directly against this fixture's 7 real surviving
        # records: website 6/7 (5488's is null), postal_code 7/7,
        # organization (school_name) 4/7 (2029/1125/5488 report no
        # school), rookie_year 7/7, nickname (Team.name) 7/7.
        teams = _extract_real_fixture(monkeypatch)

        assert sum(1 for t in teams if t.website) == 6
        assert sum(1 for t in teams if t.postal_code) == 7
        assert sum(1 for t in teams if t.organization) == 4
        assert sum(1 for t in teams if t.rookie_year is not None) == 7
        assert sum(1 for t in teams if t.name) == 7


class TestCaAndSanDiegoCountyFilter:
    def test_non_california_records_are_dropped(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        # 1554 (Oceanside, New York), 3679 (San Marcos, Texas), 3723
        # (Spring Valley, Minnesota), 188 (Toronto, Ontario), 118
        # (Houston, Texas) -- all real, all out-of-state/international.
        assert all(t.number not in (1554, 3679, 3723, 188, 118) for t in teams)

    def test_california_but_not_san_diego_records_are_dropped(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        # 100: real, "California", Woodside -- not a San Diego County city.
        assert all(t.number != 100 for t in teams)

    def test_san_diego_named_texas_city_is_dropped_despite_the_name_match(
        self, monkeypatch
    ):
        # 8353: real, "Botqueros 2 the FUTURE!", "San Diego High School",
        # city "San Diego" -- but state_prov is "Texas". Proves the
        # state check remains load-bearing even when city alone would
        # match SD_COUNTY_CITIES -- exactly the failure mode a
        # city-only filter would miss.
        teams = _extract_real_fixture(monkeypatch)

        assert all(t.number != 8353 for t in teams)

    def test_out_of_state_page_contributes_zero_teams(self, monkeypatch):
        monkeypatch.setenv("TBA_KEY", "fixture-test-key")
        fetcher = FixtureFetcher(
            {PAGE1_URL: _response(_read_fixture("tba_teams_page1.json"))}
        )
        source_obj = TBASource()

        raw = source_obj.fetch(TeamRef(url=PAGE1_URL), fetcher)
        teams = list(source_obj.extract(raw, _source()))

        assert teams == []


class TestStateNameNormalization:
    """Regression coverage for the defect this reopened ticket fixes:
    the original filter compared ``state_prov`` to the literal string
    ``"CA"`` only, so a record reporting the full name "California"
    (the majority of TBA's real live data -- 59 of 78 San Diego County
    records) was silently dropped. This is the test that was missing
    -- ``tba_teams_page0.json``'s original hand-authored fixture used
    ``"CA"`` for every record, so it could never have caught this."""

    def test_full_state_name_california_is_accepted(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        # 1622, 3128, 2984, 2827, 2029, 100 are all real records with
        # state_prov == "California" in the raw fixture; the first
        # five are San Diego County cities and must survive extraction
        # (100 is Woodside, correctly dropped for city, not state).
        numbers = {t.number for t in teams}
        assert {1622, 3128, 2984, 2827, 2029}.issubset(numbers)

    def test_abbreviated_state_ca_is_still_accepted(self, monkeypatch):
        # 1125 and 5488 report the bare "CA" abbreviation in the raw
        # fixture -- these already passed under the pre-fix filter, so
        # this asserts the fix does not regress the abbreviated form.
        teams = _extract_real_fixture(monkeypatch)

        numbers = {t.number for t in teams}
        assert {1125, 5488}.issubset(numbers)

    def test_normalize_state_maps_full_name_to_abbreviation(self):
        assert _normalize_state("California") == "CA"
        assert _normalize_state("california") == "CA"
        assert _normalize_state("  California  ") == "CA"

    def test_normalize_state_passes_through_an_existing_abbreviation(self):
        assert _normalize_state("CA") == "CA"
        assert _normalize_state("ca") == "CA"

    def test_normalize_state_normalizes_other_recognized_state_names(self):
        # Not just California -- the ticket's own instruction was to
        # normalize generally, not special-case one state.
        assert _normalize_state("Texas") == "TX"
        assert _normalize_state("New York") == "NY"
        assert _normalize_state("Minnesota") == "MN"

    def test_normalize_state_handles_none_and_empty(self):
        assert _normalize_state(None) == ""
        assert _normalize_state("") == ""
        assert _normalize_state("   ") == ""

    def test_normalize_state_passes_through_an_unrecognized_name_uppercased(self):
        # An unrecognized full name (e.g. a non-US province spelled
        # out) must never accidentally collide with "CA" -- it is
        # uppercased and left as-is, which will simply fail the "CA"
        # comparison like any other non-California value.
        assert _normalize_state("Ontario") == "ONTARIO"


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
        assert spyder.website == "http://www.teamspyder.org"


class TestUnknownOrganizationTeam:
    """A community/no-school FRC team (no TBA ``Family/Community``
    sentinel exists -- TBA simply reports a null ``school_name``) --
    org_type "unknown", organization "", the same "never group" bucket
    teams.merge.py gives FTCScout's Family/Community sentinel. Team
    2029 ("Neo-Tech Robotics", Ramona) is real and live-captured, with
    a null ``school_name`` despite ``state_prov`` being the full
    "California" -- proving the state-name form and the
    no-reported-school case are independent of each other."""

    def test_null_school_name_maps_to_empty_organization(self, monkeypatch):
        teams = _extract_real_fixture(monkeypatch)

        neo_tech = next(t for t in teams if t.number == 2029)
        assert neo_tech.organization == ""
        assert neo_tech.org_type == "unknown"


class TestTbaIsNotAGeocodingSource:
    """TBA's lat/lng/address/location_name/gmaps_place_id are
    documented in its own OpenAPI spec as "Will be NULL, for future
    development" -- confirmed NULL for all 78 real SD teams (measured
    live; see ``sources/tba.py``'s module docstring), including every
    record in this fixture. This source must never read them,
    present-but-null or otherwise; Team.latitude/longitude stay at
    their dataclass default (None) here."""

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
